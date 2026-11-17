#!/usr/bin/env python3
"""Check local links in the public entry points; no data or receipt reads."""

from pathlib import Path, PurePosixPath
import json
import posixpath
import re
from urllib.parse import unquote, urlsplit

if __package__:
    from .repository_checks import (
        CURRENT_CLOSURES, Reader, artifact_members, checked_path, need, relative_path)
else:
    # Keep the standalone source entry point and isolated fixture imports usable.
    import importlib.util
    _spec = importlib.util.spec_from_file_location(
        "navigation_source_checks", Path(__file__).with_name("repository_checks.py"))
    _checks = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_checks)
    CURRENT_CLOSURES, Reader, artifact_members, checked_path, need, relative_path = (
        _checks.CURRENT_CLOSURES, _checks.Reader, _checks.artifact_members,
        _checks.checked_path, _checks.need, _checks.relative_path)


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
FROZEN_PAGES = FROZEN_PAGES | {
    'benchmarks/neural/NEURAL-095/docs/rights/NEURAL_095_REFERENCE_DATA_NOTICE_20261115.md',
}


def navigation_sources(reader):
    """Discover current guides from explicit public metadata, not source packages."""
    registry, _ = reader.document('benchmarks/registry.json')
    need(isinstance(registry.get('tasks'), list), 'Registry tasks must be a list')
    pages = list(PAGES)
    non_markdown = set()
    seen_tasks = set()
    for row in registry['tasks']:
        identifier, track = row['id'], row['track']
        need(isinstance(identifier, str)
             and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,199}', identifier)
             and identifier.casefold() != 'readme.md'
             and track in ('paper', 'neural'), 'Invalid task navigation identity')
        need(identifier not in seen_tasks, 'Duplicate task navigation identity')
        seen_tasks.add(identifier)
        home = f'benchmarks/{track}/{identifier}'
        need(row['task_directory'] == home, 'Task navigation home does not match identity')
        checked_path(reader.root, home, directory=True)
        pages.append(home + '/README.md')
        documents = row.get('documentation', [])
        need(isinstance(documents, list), 'Task documentation must be a list')
        for item in documents:
            path = item['path']
            relative_path(path)
            need(path.startswith(home + '/docs/'), 'Task documentation is outside its exact owner')
            checked_path(reader.root, path)
            if PurePosixPath(path).suffix.lower() == '.md':
                pages.append(path)
            else:
                # Public descriptors are source targets, not Markdown. Their
                # byte identities are checked by the ownership inventory.
                non_markdown.add(path)
    usage = checked_path(reader.root, 'docs/usage', directory=True)
    for path in sorted(usage.iterdir()):
        if path.suffix.lower() == '.md':
            relative = path.relative_to(reader.root).as_posix()
            checked_path(reader.root, relative)
            pages.append(relative)
    # Current binding guides are current navigation, not frozen package docs.
    # Reuse the source checker's bounded, alias-refusing namespace traversal.
    bindings = artifact_members(reader.root, [{
        'path': CURRENT_CLOSURES, 'id': 'navigation-current-bindings',
    }], binding_metadata_only=True)
    pages.extend(sorted(path for path in bindings if PurePosixPath(path).name == 'README.md'))
    return tuple(dict.fromkeys(pages)), non_markdown


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
    reader = Reader(ROOT)
    try:
        relocation, _ = reader.document('docs/provenance/relocations/2026-11-16.json')
        need(isinstance(relocation.get('files'), list), 'Relocation files must be a list')
        mappings = {}
        for row in relocation['files']:
            old, new = str(relative_path(row['old'])), str(relative_path(row['new']))
            need(old not in mappings, 'Duplicate historical navigation source')
            mappings[old] = new
        pages, non_markdown = navigation_sources(reader)
    except (ValueError, KeyError, TypeError, OSError, UnicodeError, RecursionError) as error:
        print(f'Navigation source refused: {error}')
        return 1
    for name in pages:
        page = ROOT / name
        try:
            _, raw = reader.file(name, capture=True)
            body = raw.decode('utf-8')
        except (ValueError, OSError, UnicodeError) as error:
            failures.append(f'{name}: navigation source refused: {error}')
            continue
        # These curated entry points use inline Markdown links without titles.
        body = re.sub(r"```.*?```", "", body, flags=re.S)
        body = re.sub(r"`[^`\n]*`", "", body)
        for destination in re.findall(r"\]\(([^)]+)\)", body):
            try:
                parsed = urlsplit(destination.strip().strip("<>"))
            except ValueError:
                failures.append(f'{name}: malformed link {destination}')
                continue
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
    print(f"Checked {len(pages)} navigation pages and {checked} current local paths and {historical_resolved} historical references resolved via the relocation ledger; {len(non_markdown)} registered non-Markdown targets; {len(failures)} failures.")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
