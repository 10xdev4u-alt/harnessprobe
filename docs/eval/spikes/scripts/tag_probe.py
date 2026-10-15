"""R5 spike: does a wrapt.ObjectProxy sentinel tag survive common harness hops?

Run: /tmp/hp-eval/venvs/r5/bin/python /tmp/hp-eval/artifacts/r5/tag_probe.py
Prints a markdown matrix. Exit code 0 always (findings, not failures).
"""

import asyncio
import copy
import json
import statistics
import timeit
import uuid

import wrapt
from pydantic import BaseModel

try:
    from openai.types.chat import ChatCompletion, ChatCompletionMessage
    from openai.types.chat.chat_completion_message_tool_call import (
        ChatCompletionMessageToolCall,
        Function as OpenAIFunction,
    )

    OPENAI_TYPES_AVAILABLE = True
    OPENAI_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - environment dependent
    OPENAI_TYPES_AVAILABLE = False
    OPENAI_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------- local models
# Mimic openai chat completion: choice.message + message.tool_calls.


class LocalFunction(BaseModel):
    name: str
    arguments: str


class LocalToolCall(BaseModel):
    id: str
    type: str = "function"
    function: LocalFunction


class LocalMessage(BaseModel):
    role: str
    content: str | None = None
    tool_calls: list[LocalToolCall] = []


# ------------------------------------------------------------ tagging machinery


class TaggedProxy(wrapt.ObjectProxy):
    """ObjectProxy carrying a sentinel tag on the proxy itself.

    tag is required: a default would silently mask non-propagation.
    """

    def __init__(self, wrapped, tag):
        super().__init__(wrapped)
        self._self_hp_tag = tag


class TagPreservingProxy(TaggedProxy):
    """Same, but copy/deepcopy keep the tag (mitigation variant)."""

    def __copy__(self):
        return TagPreservingProxy(copy.copy(self.__wrapped__), self._self_hp_tag)

    def __deepcopy__(self, memo):
        return TagPreservingProxy(
            copy.deepcopy(self.__wrapped__, memo), self._self_hp_tag
        )


class TaggedDict(dict):
    def __init__(self, *args, tag=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.hp_tag = tag


def get_tag(obj):
    return getattr(obj, "_self_hp_tag", None)


def make_message(role="assistant", content=None, with_tool_call=True):
    tool_calls = []
    if with_tool_call:
        tool_calls = [
            LocalToolCall(
                id="call_1",
                function=LocalFunction(
                    name="get_weather",
                    arguments=json.dumps({"city": "Lyon", "units": "metric"}),
                ),
            )
        ]
    return LocalMessage(role=role, content=content, tool_calls=tool_calls)


def make_openai_message():
    if not OPENAI_TYPES_AVAILABLE:
        return None
    return ChatCompletionMessage(
        role="assistant",
        content=None,
        tool_calls=[
            ChatCompletionMessageToolCall(
                id="call_1",
                type="function",
                function=OpenAIFunction(
                    name="get_weather",
                    arguments=json.dumps({"city": "Lyon", "units": "metric"}),
                ),
            )
        ],
    )


# ------------------------------------------------------------------ probe rigs

RESULTS = []


def record(case, survives, lost_at, notes):
    RESULTS.append(
        {
            "case": case,
            "survives": survives,
            "lost_at": lost_at,
            "notes": notes,
        }
    )


def new_case_tag(case_id):
    return f"HP-R5:{case_id}:{uuid.uuid4().hex[:8]}"


def probe(label, model_factory, hops, hop_impl, extra_note=""):
    """Generic: tag a model, run hop_impl(tagged) -> object, report tag presence."""
    tag = new_case_tag(label)
    msg = model_factory()
    tagged = TaggedProxy(msg, tag)

    try:
        out = hop_impl(tagged)
    except Exception as exc:
        record(label, False, "raised", f"{type(exc).__name__}: {exc} {extra_note}".strip())
        return None

    got = get_tag(out)
    survives = got == tag
    if survives:
        note = f"same object identity: {out is tagged}; {extra_note}".strip()
        record(label, True, "-", note)
    else:
        note = f"tag={got!r} out_type={type(out).__name__}; {extra_note}".strip()
        record(label, False, "this hop", note)
    return out


# ---------------------------------------------------------------- a) attribute


def case_a_attribute():
    tag = new_case_tag("a")
    msg = make_message()
    tagged = TaggedProxy(msg, tag)
    role = tagged.role
    content = tagged.content
    name = tagged.tool_calls[0].function.name
    nested = tagged.tool_calls[0]
    nested_tag = get_tag(nested)
    survives_top = get_tag(tagged) == tag
    record(
        "a) direct attribute access",
        survives_top,
        "-" if survives_top else "this hop",
        f"read role={role!r} name={name!r} through proxy; nested tool_calls[0] tag={nested_tag!r} (shallow wrap only)"
        if survives_top
        else "tag lost reading attributes",
    )
    record(
        "a2) nested element via attribute",
        nested_tag == tag,
        "never tagged",
        f"tool_calls[0] is raw {type(nested).__name__}; proxy wraps top-level value only",
    )


# ------------------------------------------------------------------ b) 3-hop sync


def _hop1(o):
    return _hop2(o)


def _hop2(o):
    return _hop3(o)


def _hop3(o):
    return o


def case_b_sync():
    probe("b) 3-hop sync pass", make_message, 3, _hop1)


# ----------------------------------------------------------------- c) asyncio


async def _ahop1(o):
    return await _ahop2(o)


async def _ahop2(o):
    return await _ahop3(o)


async def _ahop3(o):
    return o


def case_c_async():
    probe(
        "c) 3-hop async chain",
        make_message,
        3,
        lambda o: asyncio.run(_ahop1(o)),
    )


# ----------------------------------------------------------- d) model_validate


def case_d_validate():
    tag = new_case_tag("d")
    d = TaggedDict(make_message().model_dump(), tag=tag)
    out = LocalMessage.model_validate(d)
    got = get_tag(out)
    record(
        "d) model_validate from tagged dict",
        got == tag,
        "model_validate",
        f"input TaggedDict(tag={tag!r}) -> new {type(out).__name__}, tag={got!r}",
    )

    tag2 = new_case_tag("d3")
    msg = make_message()
    tagged = TaggedProxy(msg, tag2)
    try:
        out2 = LocalMessage.model_validate(tagged)
        got2 = get_tag(out2)
        record(
            "d3) model_validate from tagged instance [extra]",
            got2 == tag2,
            "-" if got2 == tag2 else "model_validate",
            f"returned {'the same proxy' if out2 is tagged else type(out2).__name__}; tag={got2!r}",
        )
    except Exception as exc:
        record(
            "d3) model_validate from tagged instance [extra]",
            False,
            "raised",
            f"{type(exc).__name__}: {exc}",
        )


# ------------------------------------------------------------- e) dump+revalidate


def case_e_dump_revalidate():
    tag = new_case_tag("e")
    tagged = TaggedProxy(make_message(), tag)
    dumped = tagged.model_dump()
    got_dump = getattr(dumped, "_self_hp_tag", None)
    out = LocalMessage.model_validate(dumped)
    got = get_tag(out)
    record(
        "e) model_dump + re-validate",
        got == tag,
        "model_dump",
        f"dump produced plain {type(dumped).__name__} (tag={got_dump!r}); re-validated model tag={got!r}",
    )


# ------------------------------------------------------------------- f) json


def case_f_json():
    tag = new_case_tag("f")
    tagged = TaggedProxy(make_message(), tag)
    try:
        json.dumps(tagged)
        direct = "json.dumps(proxy) worked"
    except Exception as exc:
        direct = f"json.dumps(proxy) raises {type(exc).__name__}"
    payload = json.dumps(tagged.model_dump())
    loaded = json.loads(payload)
    out = LocalMessage.model_validate(loaded)
    got = get_tag(out)
    record(
        "f) json dumps/loads + re-validate",
        got == tag,
        "model_dump",
        f"{direct}; round trip yields {type(loaded).__name__}; final model tag={got!r}",
    )


# ------------------------------------------------------------------- g) copy


def case_g_copy():
    tag = new_case_tag("g")
    tagged = TaggedProxy(make_message(), tag)
    for opname, op in (("copy.copy", copy.copy), ("copy.deepcopy", copy.deepcopy)):
        try:
            out = op(tagged)
            got = get_tag(out)
            record(
                f"g) {opname}",
                got == tag,
                "-" if got == tag else "copy",
                f"out_type={type(out).__name__}, tag={got!r}, out is tagged={out is tagged}",
            )
        except Exception as exc:
            record(
                f"g) {opname}",
                False,
                "raised",
                f"{type(exc).__name__}: {exc}",
            )

    tag2 = new_case_tag("g-mitigation")
    tagged2 = TagPreservingProxy(make_message(), tag2)
    for opname, op in (("copy.copy", copy.copy), ("copy.deepcopy", copy.deepcopy)):
        try:
            out = op(tagged2)
            got = get_tag(out)
            record(
                f"g2) {opname} (mitigation) [extra]",
                got == tag2,
                "-" if got == tag2 else "copy",
                f"TagPreservingProxy.__{opname.split('.')[1]}__; tag={got!r}",
            )
        except Exception as exc:
            record(
                f"g2) {opname} (mitigation) [extra]",
                False,
                "raised",
                f"{type(exc).__name__}: {exc}",
            )


# ------------------------------------------------------------------- h) dict


def case_h_dict():
    tag = new_case_tag("h")
    msg = make_message()
    tagged = TaggedProxy(msg, tag)
    flat = {
        "role": tagged.role,
        "tool_calls": [tc.model_dump() for tc in tagged.tool_calls],
    }
    got = getattr(flat, "_self_hp_tag", None)
    record(
        "h) dict-style passthrough",
        got == tag,
        "flattening",
        f"rebuilt plain dict keys={sorted(flat)}; tag on dict={got!r}",
    )
    try:
        item = tagged["role"]
        item_note = f"proxy['role'] works -> {item!r}"
    except Exception as exc:
        item_note = f"proxy['role'] raises {type(exc).__name__}"
    record(
        "h2) mapping access on proxy [extra]",
        False,
        "n/a (mechanics)",
        item_note,
    )


# ------------------------------------------------------------------- i) list


def case_i_list():
    tag = new_case_tag("i")
    tagged = TaggedProxy(make_message(), tag)
    plain = make_message(content="plain sibling")
    lst = [tagged, plain]
    seen = lst[0]
    record(
        "i) tag inside list element",
        get_tag(seen) == tag,
        "-" if get_tag(seen) == tag else "list hop",
        "list indexing returns the same proxy object",
    )
    shallow = list(lst)
    record(
        "i2) shallow list(list) [extra]",
        get_tag(shallow[0]) == tag,
        "-" if get_tag(shallow[0]) == tag else "list copy",
        "shallow list copy preserves element identity",
    )
    try:
        deep = copy.deepcopy(lst)
        record(
            "i3) deepcopy of list [extra]",
            get_tag(deep[0]) == tag,
            "-" if get_tag(deep[0]) == tag else "deepcopy",
            f"element tag after deepcopy={get_tag(deep[0])!r}",
        )
    except Exception as exc:
        record(
            "i3) deepcopy of list [extra]",
            False,
            "raised",
            f"{type(exc).__name__}: {exc}",
        )
    out = LocalMessage.model_validate([x.model_dump() for x in lst][0])
    record(
        "i4) list element through dump/validate [extra]",
        get_tag(out) == tag,
        "model_dump per element",
        "coercion rebuilds plain models",
    )


# --------------------------------------------------------- openai SDK variants


def case_openai():
    if not OPENAI_TYPES_AVAILABLE:
        record(
            "openai SDK types",
            False,
            "n/a",
            f"import failed: {OPENAI_IMPORT_ERROR}",
        )
        return
    tag = new_case_tag("openai")
    msg = make_openai_message()
    tagged = TaggedProxy(msg, tag)
    role = tagged.role
    nested = tagged.tool_calls[0]
    record(
        "openai) attribute access on real SDK type",
        get_tag(tagged) == tag,
        "-" if get_tag(tagged) == tag else "this hop",
        f"isinstance={isinstance(tagged, ChatCompletionMessage)}; read role={role!r}; nested tag={get_tag(nested)!r}",
    )
    d = TaggedDict(msg.model_dump(), tag=tag)
    out = ChatCompletionMessage.model_validate(d)
    record(
        "openai) model_validate from tagged dict",
        get_tag(out) == tag,
        "model_validate",
        f"new {type(out).__name__}, tag={get_tag(out)!r}",
    )

    tag_copy = new_case_tag("openai-copy")
    tagged2 = TaggedProxy(make_openai_message(), tag_copy)
    try:
        out2 = copy.deepcopy(tagged2)
        record(
            "openai) deepcopy",
            get_tag(out2) == tag_copy,
            "-" if get_tag(out2) == tag_copy else "deepcopy",
            f"tag={get_tag(out2)!r}",
        )
    except Exception as exc:
        record("openai) deepcopy", False, "raised", f"{type(exc).__name__}: {exc}")


# --------------------------------------------------------------------- perf


def perf():
    msg = make_message()
    proxy = TaggedProxy(msg, "perf-tag")
    assert msg.content is None and proxy.content is None
    assert proxy.tool_calls[0].function.name == "get_weather"
    assert get_tag(proxy) == "perf-tag"

    n = 10000
    t_raw = timeit.Timer("m.content", globals={"m": msg})
    t_proxy = timeit.Timer("p.content", globals={"p": proxy})
    t_tag = timeit.Timer("getattr(p, '_self_hp_tag', None)", globals={"p": proxy})
    t_attr = timeit.Timer("getattr(m, 'role')", globals={"m": msg})
    t_attr_proxy = timeit.Timer("getattr(p, 'role')", globals={"p": proxy})

    samples = {"raw_attr": [], "proxy_attr": [], "proxy_tag_read": [], "raw_role": [], "proxy_role": []}
    for _ in range(5):
        samples["raw_attr"].append(t_raw.timeit(number=n))
        samples["proxy_attr"].append(t_proxy.timeit(number=n))
        samples["proxy_tag_read"].append(t_tag.timeit(number=n))
        samples["raw_role"].append(t_attr.timeit(number=n))
        samples["proxy_role"].append(t_attr_proxy.timeit(number=n))

    print("## perf (timeit, n=10000 per sample, 5 interleaved samples per side)")
    print()
    print("| operation | median us per 10k | min | max |")
    print("|---|---|---|---|")
    for name, vals in samples.items():
        us = [v * 1e6 for v in vals]
        print(
            f"| {name} | {statistics.median(us):.0f} | {min(us):.0f} | {max(us):.0f} |"
        )
    print()


# --------------------------------------------------------------------- main


def main():
    print(f"# R5 tag probe run")
    print()
    print(f"- wrapt: {getattr(wrapt, '__version__', 'unknown')}")
    import pydantic

    print(f"- pydantic: {pydantic.__version__}")
    try:
        import openai as _openai

        print(f"- openai: {_openai.__version__}")
    except Exception:
        pass
    print(f"- Python: {__import__('platform').python_version()}")
    print()

    case_a_attribute()
    case_b_sync()
    case_c_async()
    case_d_validate()
    case_e_dump_revalidate()
    case_f_json()
    case_g_copy()
    case_h_dict()
    case_i_list()
    case_openai()

    print("## survivability matrix (only_local = our pydantic models)")
    print()
    print("| case | survives | lost at | notes |")
    print("|---|---|---|---|")
    for r in RESULTS:
        print(
            f"| {r['case']} | {'YES' if r['survives'] else 'NO'} | {r['lost_at']} | {r['notes']} |"
        )
    print()
    perf()


if __name__ == "__main__":
    main()
