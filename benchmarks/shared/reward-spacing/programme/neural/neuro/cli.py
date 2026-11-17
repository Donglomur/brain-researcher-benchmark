"""Operator CLI. Source preparation and numerical execution require invented input here."""
import argparse
from pathlib import Path
from .base import read_json, write_json, require


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='action', required=True)
    a = sub.add_parser('prepare'); a.add_argument('corpus'); a.add_argument('task'); a.add_argument('output')
    a.add_argument('--view', default='retrospective'); a.add_argument('--endpoint', default='cue')
    a = sub.add_parser('project'); a.add_argument('bank'); a.add_argument('held'); a.add_argument('cell')
    a.add_argument('output'); a.add_argument('--kind', default='animal'); a.add_argument('--prior')
    a = sub.add_parser('begin'); a.add_argument('root'); a.add_argument('plan')
    a = sub.add_parser('stage'); a.add_argument('root'); a.add_argument('job'); a.add_argument('public'); a.add_argument('private')
    a = sub.add_parser('commit-I'); a.add_argument('root'); a.add_argument('job'); a.add_argument('program')
    a = sub.add_parser('produce'); a.add_argument('root'); a.add_argument('job'); a.add_argument('program'); a.add_argument('--timeout', type=float, default=10)
    for name in ('close', 'grade'):
        a = sub.add_parser(name); a.add_argument('root')
    a = sub.add_parser('finish'); a.add_argument('root'); a.add_argument('interpretations')
    a = sub.add_parser('packet'); a.add_argument('cell'); a.add_argument('policy'); a.add_argument('packet'); a.add_argument('rubric'); a.add_argument('output')
    args = p.parse_args()
    if args.action == 'prepare':
        from .prepare import prepare
        corpus = read_json(args.corpus); require(corpus['synthetic'] is True, 'authentic_preparation_paused')
        write_json(args.output, prepare(corpus, args.task, args.view, args.endpoint), True)
    elif args.action == 'project':
        from .prepare import project, split
        bank = read_json(args.bank); require(bank['synthetic'] is True, 'authentic_projection_paused')
        training, query = split(bank, args.held, args.kind)
        public = project(bank, training, query, args.cell,
                         source_prior=read_json(args.prior) if args.prior else None)
        write_json(Path(args.output) / 'input.json', public, True)
        write_json(Path(args.output) / 'operator_targets.json', query, True)
    elif args.action == 'packet':
        from .packet import evaluate
        packet = read_json(args.packet)
        result = evaluate(Path(args.policy).read_bytes(), packet,
                          args.cell, packet['task_id'], read_json(args.rubric))
        write_json(args.output, result, True)
    else:
        from .workflow import Workflow, run_engineering_producer
        w = Workflow(args.root)
        if args.action == 'begin': w.begin(read_json(args.plan))
        elif args.action == 'stage': w.prepare_job(args.job, read_json(args.public), read_json(args.private))
        elif args.action == 'commit-I': w.commit_interactive_program(args.job, args.program)
        elif args.action == 'produce':
            folder = Path(args.root) / 'jobs' / args.job
            receipt = run_engineering_producer(args.program, folder / 'public/input.json', folder / 'outputs', args.timeout)
            w.collect(args.job, receipt)
        elif args.action == 'close': w.close()
        elif args.action == 'grade': w.grade_once()
        elif args.action == 'finish': w.finish(read_json(args.interpretations))


if __name__ == '__main__': main()
