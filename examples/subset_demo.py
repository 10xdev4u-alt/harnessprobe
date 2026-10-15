"""Self-contained demo of scope extraction and coverage subsetting."""

from pathlib import Path
from tempfile import TemporaryDirectory

from harnessprobe import derive_scope, subset_coverage

MODULE = """\
def ask(client):
    response = client.chat.completions.create(model="m")
    return response.content
"""

COVERAGE = {
    "files": {
        "pkg/agent.py": {
            "executed_lines": [2],
            "missing_lines": [3],
            "executed_branches": [],
            "missing_branches": [],
        }
    }
}


def main() -> int:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        package = root / "pkg"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "agent.py").write_text(MODULE, encoding="utf-8")
        scope = derive_scope(root)
        report = subset_coverage(COVERAGE, scope, repo_root=root)
        print(report.render_markdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
