"""Prepare a frozen operator plan without opening any data or using Docker."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source-sha256', 'store-root', 'targets', 'output-root',
                 'docker-binary', 'socket', 'plan-output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    source, _, _ = run.load_sources(args.source_sha256)
    plan = {'schema': 'neural031_full40_fixed_control_plan_v1', 'candidate_id': 'NEURAL-031',
            'kind': 'fixed_ratio_one', 'source_sha256': args.source_sha256,
            'image_id': run.IMAGE, 'docker_binary': args.docker_binary, 'socket': args.socket,
            'output_root': args.output_root, 'store_root': args.store_root,
            'targets': {'path': args.targets, **run.TARGET},
            'image_inventory_review': source['files']['IMAGE_PROFILE.json'],
            'method_review': source['files']['CONTROL_METHOD.md']}
    run.validate_plan(plan, args.source_sha256)
    target = Path(args.plan_output)
    run.need(target.is_absolute() and target.parent.is_dir()
             and not target.exists() and not target.is_symlink(), 'Fresh absolute operator plan path')
    descriptor = run.write(target, plan)
    print(run.encoded({'plan': str(target), **descriptor,
                       'data_opened': False, 'Docker_invoked': False,
                       'execution_authorized': False}).decode(), end='')


if __name__ == '__main__':
    main()
