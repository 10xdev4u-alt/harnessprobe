#!/usr/bin/env python3
"""R3: intersect ldh_scope.json (Tier A/B) with coverage.py JSON output.

Per file & tier:
  - scope statement lines = scope lines present in coverage's executable set
    (executed_lines | missing_lines)
  - executed, covered %
  - lines in scope not present in the executable set (docstrings, def lines, ...)
  - branch arcs whose from-line is in scope: executed arcs / total arcs, and
    per-line classification full / partial / missing
Whole-package coverage over browser_use/ files for reference.

Usage: subset_analysis.py <coverage.json> <scope.json> <repo_root> <out_dir>
"""
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

pkg_prefix = "browser_use/"


def load_source_lines(repo_root: Path, rel: str):
    p = repo_root / rel
    try:
        return p.read_text(encoding='utf-8').splitlines()
    except OSError:
        return []


def main() -> None:
    cov_path, scope_path, repo_root, out_dir = (
        Path(sys.argv[1]),
        Path(sys.argv[2]),
        Path(sys.argv[3]),
        Path(sys.argv[4]),
    )
    cov = json.loads(cov_path.read_text())
    scope = json.loads(scope_path.read_text())

    pkg_files = [k for k in cov["files"] if k.startswith(pkg_prefix)]
    pkg_lines = sum(cov["files"][k]["summary"]["num_statements"] for k in pkg_files)
    pkg_exec = sum(cov["files"][k]["summary"]["covered_lines"] for k in pkg_files)
    pkg_br = sum(cov["files"][k]["summary"]["num_branches"] for k in pkg_files)
    pkg_br_exec = sum(cov["files"][k]["summary"]["covered_branches"] for k in pkg_files)

    rows = []
    tier_agg = defaultdict(
        lambda: Counter(
            statements=0, executed=0, not_measured=0, arcs=0, arcs_exec=0,
            lines_with_arcs=0, branch_full=0, branch_partial=0, branch_missing=0,
        )
    )
    uncovered_a = []  # (file, line) samples
    src_cache: dict[str, list[str]] = {}

    for rel, tiers in sorted(scope.items()):
        f = cov["files"].get(rel)
        for tier in ("tierA_lines", "tierB_lines"):
            lines = set(tiers[tier])
            if not lines:
                continue
            if f is None:
                # file never imported/executed at all
                tier_agg[tier]["not_measured"] += len(lines)
                rows.append(
                    dict(file=rel, tier=tier[4], statements=0, executed=0, covered_pct="",
                         not_measured=len(lines), branch_arcs=0, branch_arcs_executed=0,
                         branch_lines_full=0, branch_lines_partial=0, branch_lines_missing=0)
                )
                continue
            exec_set = set(f["executed_lines"])
            stmt_set = exec_set | set(f["missing_lines"])
            in_scope_stmt = lines & stmt_set
            executed = lines & exec_set
            not_measured = lines - stmt_set

            arcs = [tuple(a) for a in f["executed_branches"]] + [
                tuple(a) for a in f["missing_branches"]
            ]
            exec_arcs = {tuple(a) for a in f["executed_branches"]}
            scope_arcs = [a for a in arcs if a[0] in lines]
            scope_arcs_exec = [a for a in scope_arcs if a in exec_arcs]
            by_from = defaultdict(lambda: [0, 0])  # from -> [total, exec]
            for a in scope_arcs:
                by_from[a[0]][0] += 1
                if a in exec_arcs:
                    by_from[a[0]][1] += 1
            full = partial = missing = 0
            for from_line, (tot, ex) in by_from.items():
                if ex == tot:
                    full += 1
                elif ex == 0:
                    missing += 1
                else:
                    partial += 1

            n_stmt = len(in_scope_stmt)
            n_exec = len(executed)
            pct = (100.0 * n_exec / n_stmt) if n_stmt else None
            rows.append(
                dict(file=rel, tier=tier[4], statements=n_stmt, executed=n_exec,
                     covered_pct=f"{pct:.1f}" if pct is not None else "",
                     not_measured=len(not_measured), branch_arcs=len(scope_arcs),
                     branch_arcs_executed=len(scope_arcs_exec), branch_lines_full=full,
                     branch_lines_partial=partial, branch_lines_missing=missing)
            )
            agg = tier_agg[tier]
            agg["statements"] += n_stmt
            agg["executed"] += n_exec
            agg["not_measured"] += len(not_measured)
            agg["arcs"] += len(scope_arcs)
            agg["arcs_exec"] += len(scope_arcs_exec)
            agg["lines_with_arcs"] += len(by_from)
            agg["branch_full"] += full
            agg["branch_partial"] += partial
            agg["branch_missing"] += missing

            if tier == "tierA_lines":
                for line in sorted(lines & stmt_set - exec_set):
                    uncovered_a.append((rel, line))

    # samples
    samples = []
    for rel, line in uncovered_a[:10]:
        src = src_cache.get(rel)
        if src is None:
            src = load_source_lines(repo_root, rel)
            src_cache[rel] = src
        text = src[line - 1].strip() if 0 < line <= len(src) else ""
        samples.append((rel, line, text[:120]))

    with (out_dir / "subset_table.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), dialect="excel-tab")
        w.writeheader()
        w.writerows(rows)

    summary = {
        "whole_package": {
            "files": len(pkg_files),
            "statements": pkg_lines,
            "executed": pkg_exec,
            "line_pct": round(100.0 * pkg_exec / pkg_lines, 1),
            "branches": pkg_br,
            "branches_executed": pkg_br_exec,
            "branch_pct": round(100.0 * pkg_br_exec / pkg_br, 1),
        },
        "tiers": {
            "A": dict(tier_agg["tierA_lines"]),
            "B": dict(tier_agg["tierB_lines"]),
        },
        "uncovered_tierA_samples": [
            {"file": r, "line": l, "source": s} for r, l, s in samples
        ],
        "uncovered_tierA_total": len(uncovered_a),
        "files_in_scope": len(scope),
        "scope_files_without_coverage": sorted(
            rel for rel in scope if rel not in cov["files"]
        ),
    }
    for tier in ("A", "B"):
        t = summary["tiers"][tier]
        if t["statements"]:
            t["covered_pct"] = round(100.0 * t["executed"] / t["statements"], 1)
        if t["arcs"]:
            t["arc_pct"] = round(100.0 * t["arcs_exec"] / t["arcs"], 1)
    (out_dir / "r3_summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
