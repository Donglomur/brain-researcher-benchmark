#!/usr/bin/env python3
"""Check local links in the public entry points; no data or receipt reads."""

from pathlib import Path, PurePosixPath
import json
import posixpath
import re
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[2]
PAGES = (
    'README.md',
    'CONTRIBUTING.md',
    'benchmarks/README.md',
    'benchmarks/paper/README.md',
    'benchmarks/neural/README.md',
    'benchmarks/shared/README.md',
    'docs/README.md',
    'docs/DEVELOPMENT.md',
    'docs/provenance/git/BRANCH_ARCHIVE_20261116.md',
    'docs/provenance/assessments/REPO_QUALITY_20261116.md',
    'docs/provenance/assessments/LEGACY_TASK_RECOVERY_20261116.md',
    'docs/provenance/execution/historical-evidence-v1/README.md',
    'docs/development/source-integrity.md',
    'examples/original-three/CONTRIBUTING.md',
    'docs/provenance/status-snapshots/CONSTRUCTION_STATUS_20261115.md',
    'docs/usage/artifact-grading.md',
    'docs/usage/implementations.md',
    'benchmarks/neural/NEURAL-029/implementations/neural029-programme/README.md',
    'benchmarks/neural/NEURAL-030/implementations/neural030-four-cell/README.md',
    'benchmarks/neural/NEURAL-078/implementations/neural078-deferred-grade/README.md',
    'benchmarks/paper/PAPER-FIND-050/implementations/paper-find050-programme/README.md',
    'benchmarks/paper/PAPER-FIND-050/implementations/paper-find050-programme/PREREQUISITES.md',
    'docs/science/study-design/README.md',
    'src/neurobench/study_binding_validator/README.md',
    'docs/provenance/releases/SOURCE_COMPONENTS_20261116.md',
    'examples/original-three/README.md',
    'examples/original-three/upstream-history/README.md',
    'examples/original-three/upstream-history/RESULTS.md',
    'examples/original-three/upstream-history/INTERN_GUIDE.md',
    'examples/original-three/upstream-history/TASK_BOARD.md',
    'examples/original-three/upstream-history/ASSIGNMENT_QUEUE.md',
    'benchmarks/catalog/README.md',
    'benchmarks/catalog/paper.md',
    'benchmarks/catalog/neural.md',
    'benchmarks/catalog/components.md',
    '.claude/skills/self-evolvable-question-design/SKILL.md',
    '.claude/skills/tb-science-task-authoring/SKILL.md',
    'archive/README.md',
    'benchmarks/neural/NEURAL-DISC-20261114-VOLTRON-SPIKES/docs/data-scope.md',
    'benchmarks/paper/PAPER-paper-method-047/docs/transitive-recovery.md',
    'docs/curation/README.md',
    'docs/curation/worker-contract.md',
    'docs/development/README.md',
    'docs/development/source-queue.md',
    'docs/provenance/README.md',
    'docs/provenance/source-manifests/README.md',
    'docs/science/README.md',
    'docs/science/paired-study-reporting.md',
    'docs/science/task-scope.md',
    'docs/status/README.md',
    'examples/original-three/results/README.md',
    'src/neurobench/curation/contracts/README.md',
)

# Exact historical bodies retain their original links. Their relocation results
# are reported separately and never treated as working current navigation.
FROZEN_PAGES = frozenset(('docs/provenance/git/BRANCH_ARCHIVE_20261116.md', 'docs/provenance/assessments/REPO_QUALITY_20261116.md', 'docs/provenance/assessments/LEGACY_TASK_RECOVERY_20261116.md', 'docs/provenance/execution/historical-evidence-v1/README.md', 'docs/provenance/status-snapshots/CONSTRUCTION_STATUS_20261115.md', 'docs/provenance/releases/SOURCE_COMPONENTS_20261116.md', 'examples/original-three/upstream-history/RESULTS.md', 'examples/original-three/upstream-history/INTERN_GUIDE.md', 'examples/original-three/upstream-history/TASK_BOARD.md', 'examples/original-three/upstream-history/ASSIGNMENT_QUEUE.md'))


def historical_targets(page, destination, mappings):
    """Resolve original logical names through the ledger, never the old tree."""
    originals = [old for old, new in mappings.items() if new == page]
    if len(originals) != 1:
        return []
    logical = posixpath.normpath(posixpath.join(str(PurePosixPath(originals[0]).parent), destination))
    if logical.startswith(('../', '/')) or logical == '..':
        return []
    targets = [mappings[logical]] if logical in mappings else [
        new for old, new in mappings.items() if old.startswith(logical.rstrip('/') + '/')]
    return targets if targets and all((ROOT / path).resolve().is_relative_to(ROOT)
                                     and (ROOT / path).exists() for path in targets) else []


def main():
    failures = []
    checked = 0
    historical_resolved = 0
    relocation = json.loads((ROOT / 'docs/provenance/relocations/2026-11-16.json').read_text())
    mappings = {row['old']: row['new'] for row in relocation['files']}
    task_pages = sorted(
        path.relative_to(ROOT).as_posix()
        for track in ("paper", "neural")
        for path in (ROOT / "benchmarks" / track).glob("*/README.md")
    )
    pages = tuple(dict.fromkeys((*PAGES, *task_pages)))
    for name in pages:
        page = ROOT / name
        if not page.is_file():
            failures.append(f"{name}: missing navigation page")
            continue
        # These curated entry points use inline Markdown links without titles.
        body = re.sub(r"```.*?```", "", page.read_text(encoding="utf-8"), flags=re.S)
        body = re.sub(r"`[^`\n]*`", "", body)
        for destination in re.findall(r"\]\(([^)]+)\)", body):
            parsed = urlsplit(destination.strip().strip("<>"))
            if parsed.scheme in {"http", "https", "mailto"} or destination.startswith("#"):
                continue
            if parsed.scheme or parsed.netloc:
                failures.append(f"{name}: unsupported link {destination}")
                continue
            if name in FROZEN_PAGES:
                if historical_targets(name, unquote(parsed.path), mappings):
                    historical_resolved += 1
                else:
                    failures.append(f"{name}: unresolved historical reference {destination}")
                continue
            target = (page.parent / unquote(parsed.path)).resolve()
            if not target.is_relative_to(ROOT) or not target.exists():
                failures.append(f"{name}: missing or external local path {destination}")
            checked += 1
    for failure in failures:
        print(failure)
    print(f"Checked {len(pages)} navigation pages and {checked} current local paths and {historical_resolved} historical references resolved via the relocation ledger; {len(failures)} failures.")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
