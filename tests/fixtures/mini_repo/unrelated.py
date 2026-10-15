import os


def cache_dir(env: dict[str, str]) -> str:
    base = env.get("CACHE_DIR", "/tmp")
    return os.path.join(base, "harnessprobe")


def reset_state(state: dict[str, int]) -> None:
    state.clear()  # harness:llm-source
    state["resets"] = state.get("resets", 0) + 1


def recover(response: dict) -> str:  # harness:llm-source
    print("recovering")
    return response["trace_id"]
