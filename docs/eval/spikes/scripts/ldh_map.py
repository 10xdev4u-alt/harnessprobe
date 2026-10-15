"""LDH -> function map for sample_harness.py (ast-based). R6 Experiment B artifact."""

import ast
import sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "sample_harness.py"


def main():
    src = open(PATH).read()
    lines = src.splitlines()
    marked = {i + 1 for i, line in enumerate(lines) if "# LDH" in line}
    tree = ast.parse(src)
    funcs = [
        (node.name, node.lineno, node.end_lineno)
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    ]
    print(f"file: {PATH}")
    print(f"total lines: {len(lines)}")
    print(f"LDH-marked lines: {len(marked)} ({100 * len(marked) / len(lines):.0f}%)")
    ldh_funcs = []
    for name, start, end in sorted(funcs, key=lambda f: f[1]):
        n_marked = sum(1 for m in marked if start <= m <= end)
        is_ldh = n_marked > 0
        if is_ldh:
            ldh_funcs.append(name)
        print(f"  {'LDH' if is_ldh else '-  '} {name:<20} lines {start}-{end}  marked={n_marked}")
    print(f"LDH functions: {len(ldh_funcs)}/{len(funcs)}")
    print("LDH function set:", ", ".join(ldh_funcs))


if __name__ == "__main__":
    main()
