#!/usr/bin/env python3
"""Explicit source successor; reuse the original Hierarchy25A executor and grader."""
import argparse
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LEGACY = ROOT / 'authoring/next-two-unbuilt-papers-20261103/hierarchy-bounded-task-v1/runtime-v1'
MEMBERS = {'components/hierarchy25a-original/run_program.py',
           'components/hierarchy25a-original/accounting.py'}


def admit_successor(review, files):
    value = review.get('source_successor')
    files.need(type(value) is dict and set(value) == {'freeze', 'source_reviews'},
               'Explicit successor source identity and independent source review')
    freeze = value['freeze']
    files.need(type(freeze) is dict and freeze.get('path') ==
               'components/hierarchy25a-original/SOURCE_FREEZE.json', 'Fixed successor freeze location')
    frozen = files.descriptor(freeze, 32768)
    files.need(frozen.get('schema') == 'hierarchy25a_single_program_source_successor_v1'
               and frozen.get('candidate_id') == files.ID
               and frozen.get('ancestry_freeze_sha256') == review.get('freeze_sha256') ==
               '40d4b1bcf8b62cfdeef1b4ff1d519445b534c87f4a101b548500a116aec781fc'
               and set(frozen.get('files', {})) == MEMBERS,
               'Exact two-file successor and unchanged 44-member ancestry')
    for relative, pin in frozen['files'].items():
        files.descriptor({'path': relative, **pin}, 32768, decode=False)
    reports = value['source_reviews']
    files.need(type(reports) is list and 1 <= len(reports) <= 4, 'Bounded source reviews')
    for item in reports:
        report = files.descriptor(item, 65536)
        files.need(report.get('status') == 'passed' and report.get('findings') == []
                   and report.get('source_freeze_sha256') == freeze['sha256'],
                   'Independent source review binds successor, not historical native qualification')
    return freeze


def bind_legacy():
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(LEGACY))
    import files
    sys.path.insert(0, str(HERE))
    import accounting
    # Install only the reviewed administrative adapter before the original
    # admission module binds it. No producer, engine, scorer or metric changes.
    files.accounting = accounting.accounting
    spec = importlib.util.spec_from_file_location('_hierarchy25a_original_run', LEGACY / 'run_program.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return files, runner


def bind_review(runner, files, review_path, raw):
    """Use the same captured bytes for admission and the source-commit pin."""
    review_path = Path(review_path).absolute()
    original_read = runner.read
    admission_globals = runner.admit.__globals__
    original_json_read = admission_globals['json_read']

    def captured_read(source, cap=250000):
        if Path(source).absolute() == review_path:
            files.need(0 < len(raw) <= cap, 'Bounded captured review')
            return raw
        return original_read(source, cap)

    def captured_json_read(source, cap=250000):
        if Path(source).absolute() == review_path:
            return files.strict_json(captured_read(source, cap))
        return original_json_read(source, cap)

    runner.read = captured_read
    admission_globals['json_read'] = captured_json_read


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--program', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--review', required=True, type=Path)
    parser.add_argument('--other-reserve-bytes', required=True, type=int)
    args = parser.parse_args()
    files, runner = bind_legacy()
    # Original START/WORK clocks already include the source-successor checks.
    raw_review = files.read(args.review, 131072)
    review = files.strict_json(raw_review)
    admit_successor(review, files)
    bind_review(runner, files, args.review, raw_review)
    return runner.main()


if __name__ == '__main__':
    raise SystemExit(main())
