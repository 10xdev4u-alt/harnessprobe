import ast
from pathlib import Path
import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider
import mutmut.configuration as mc
from mutmut.mutation.file_mutation import create_mutations

src = Path("sample_harness.py").read_text()
tree = ast.parse(src)
funcs = sorted(((n.name, n.lineno, n.end_lineno) for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)), key=lambda f: f[1])

with open("pyproject.toml", "w") as fh:
    fh.write('[tool.mutmut]\nsource_paths = ["sample_harness.py"]\npyproject_add = true\ndo_not_mutate_patterns = ["^(?!.*# LDH)"]\n')
# remove accidental bad key
with open("pyproject.toml", "w") as fh:
    fh.write('[tool.mutmut]\nsource_paths = ["sample_harness.py"]\npytest_add_cli_args = ["-q"]\ndo_not_mutate_patterns = ["^(?!.*# LDH)"]\n')
mc.reset_config()
module, mutations, ic, ifn = create_mutations("sample_harness.py", src)
wrapper = MetadataWrapper(module, unsafe_skip_copy=True)
pmap = wrapper.resolve(PositionProvider)
counts = {f[0]: 0 for f in funcs}
for m in mutations:
    pos = pmap.get(m.original_node)
    if pos is None: continue
    for name, a, b in funcs:
        if a <= pos.start.line <= b:
            counts[name] += 1
            break
for name, a, b in funcs:
    if counts[name]:
        print(f"{name}: {counts[name]} mutants")
