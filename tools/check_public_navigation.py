#!/usr/bin/env python3
"""Check local links in the public entry points; no data or receipt reads."""

from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
PAGES = (
    "README.md",
    "CONTRIBUTING.md",
    "benchmarks/README.md",
    "docs/README.md",
    "docs/DEVELOPMENT.md",
    "docs/original-examples-contributing.md",
    "docs/neuroscience-benchmarks/CONSTRUCTION_STATUS.md",
    "docs/neuroscience-benchmarks/ARTIFACT_GRADING.md",
    "docs/history/SOURCE_COMPONENTS_20261116.md",
    "examples/original-three/README.md",
    "benchmarks/catalog/README.md",
    "benchmarks/catalog/paper.md",
    "benchmarks/catalog/neural.md",
    "benchmarks/catalog/components.md",
)


def main():
    failures = []
    checked = 0
    for name in PAGES:
        page = ROOT / name
        if not page.is_file():
            failures.append(f"{name}: missing navigation page")
            continue
        # These curated entry points use inline Markdown links without titles.
        body = re.sub(r"```.*?```", "", page.read_text(encoding="utf-8"), flags=re.S)
        for destination in re.findall(r"\]\(([^)]+)\)", body):
            parsed = urlsplit(destination.strip().strip("<>"))
            if parsed.scheme in {"http", "https", "mailto"} or destination.startswith("#"):
                continue
            if parsed.scheme or parsed.netloc:
                failures.append(f"{name}: unsupported link {destination}")
                continue
            target = (page.parent / unquote(parsed.path)).resolve()
            if not target.is_relative_to(ROOT) or not target.exists():
                failures.append(f"{name}: missing or external local path {destination}")
            checked += 1
    for failure in failures:
        print(failure)
    print(f"Checked {len(PAGES)} navigation pages and {checked} local paths; {len(failures)} failures.")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
