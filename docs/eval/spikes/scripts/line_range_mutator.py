"""Line-range operator mutator (R6 Experiment C prototype, libcst).

Mutates binary operators, comparison operators, boolean operators, and `not`
negations only on lines inside [start, end]. Writes a mutated copy; the caller
inspects the diff and deletes it (revert).

Usage:
  python line_range_mutator.py SRC START END OUT
"""

import sys

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

BINARY_SWAPS = {
    cst.Add: cst.Subtract,
    cst.Subtract: cst.Add,
    cst.Multiply: cst.Divide,
    cst.Divide: cst.Multiply,
    cst.Modulo: cst.Multiply,
    cst.Power: cst.Multiply,
    cst.BitAnd: cst.BitOr,
    cst.BitOr: cst.BitAnd,
}

COMPARISON_SWAPS = {
    cst.LessThan: cst.GreaterThan,
    cst.GreaterThan: cst.LessThan,
    cst.LessThanEqual: cst.GreaterThanEqual,
    cst.GreaterThanEqual: cst.LessThanEqual,
    cst.Equal: cst.NotEqual,
    cst.NotEqual: cst.Equal,
    cst.In: cst.NotIn,
    cst.NotIn: cst.In,
    cst.Is: cst.IsNot,
    cst.IsNot: cst.Is,
}

BOOL_SWAPS = {cst.And: cst.Or, cst.Or: cst.And}


class RangeMutator(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, start, end):
        self.start = start
        self.end = end
        self.count = 0
        self.sites = []

    def _in_range(self, node):
        pos = self.get_metadata(PositionProvider, node, None)
        if pos is None:
            return None
        if pos.start.line >= self.start and pos.end.line <= self.end:
            return pos
        return None

    def _record(self, pos, what):
        self.count += 1
        self.sites.append((pos.start.line, what))

    def leave_BinaryOperation(self, original_node, updated_node):
        pos = self._in_range(original_node)
        swap = BINARY_SWAPS.get(type(original_node.operator))
        if pos and swap:
            self._record(pos, f"binary {type(original_node.operator).__name__} -> {swap.__name__}")
            return updated_node.with_changes(operator=swap())
        return updated_node

    def leave_Comparison(self, original_node, updated_node):
        pos = self._in_range(original_node)
        if not pos or pos.start.line != pos.end.line:
            return updated_node
        new_targets = []
        changed = False
        for target in updated_node.comparisons:
            swap = COMPARISON_SWAPS.get(type(target.operator))
            if swap:
                changed = True
                self._record(pos, f"comparison {type(target.operator).__name__} -> {swap.__name__}")
                new_targets.append(target.with_changes(operator=swap()))
            else:
                new_targets.append(target)
        if changed:
            return updated_node.with_changes(comparisons=new_targets)
        return updated_node

    def leave_BooleanOperation(self, original_node, updated_node):
        pos = self._in_range(original_node)
        swap = BOOL_SWAPS.get(type(original_node.operator))
        if pos and swap:
            self._record(pos, f"bool {type(original_node.operator).__name__} -> {swap.__name__}")
            return updated_node.with_changes(operator=swap())
        return updated_node

    def leave_UnaryOperation(self, original_node, updated_node):
        pos = self._in_range(original_node)
        if pos and isinstance(original_node.operator, cst.Not):
            self._record(pos, "not -> removed")
            return updated_node.expression
        return updated_node


def mutate_source(source, start, end):
    module = cst.parse_module(source)
    wrapper = MetadataWrapper(module)
    mutator = RangeMutator(start, end)
    mutated = wrapper.visit(mutator)
    return mutated.code, mutator


def main():
    src_path, start, end, out_path = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    source = open(src_path).read()
    mutated_code, mutator = mutate_source(source, start, end)
    with open(out_path, "w") as fh:
        fh.write(mutated_code)
    print(f"mutation sites in lines [{start},{end}]: {mutator.count}")
    for line, what in mutator.sites:
        print(f"  line {line}: {what}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
