"""Concrete program entry; describe is source-only, run requires a separate operation."""
import time
BOOT=time.monotonic()
import argparse
import json
from pathlib import Path
from core import BRANCHES, HMM, TASK, native_jobs, held_jobs


def describe():
    return {'task_id': TASK, 'native_branches': list(BRANCHES), 'held_hmm_branches': list(HMM),
            'native_per_role': len(native_jobs('A')), 'held_per_role': len(held_jobs('A')),
            'native_all_roles': 453, 'held_all_roles': 5400,
            'apis': {'prepare': 'prepare.build', 'reference_fit': 'reference.fit',
                     'reference_static': 'reference.static', 'native_run': 'native_run.run',
                     'run_complete_program': 'supervisor.run -> controller.Operations.run', 'native_assemble': 'native.assemble.assemble',
                     'held_score': 'score.held / score.aggregate_folds',
                     'native_score': 'native_compare.compare', 'admission': 'admission.held / admission.native',
                     'evaluation': 'evaluation.evaluate', 'sensitivities': 'diagnostic_bridge.run'},
            'concrete_transport_source': 'transport.Provider', 'external_executor_callback_required': False,
            'separately_qualified_environment_required': True, 'scientific_execution_authorized': False,
            'runtime_registry_installed': False, 'whole_paper_reproduced': False,
            'native_A_dynemo_original_selection_attestation': 'unresolved_training_trajectory',
            'historical_seed_parity': False}


def main():
    parser = argparse.ArgumentParser()
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('describe')
    run=commands.add_parser('run')
    for name in ('operation','operation-sha256','output'):run.add_argument('--'+name,required=True)
    run.add_argument('--operation-bytes',type=int,required=True)
    args=parser.parse_args()
    if args.command=='describe':print(json.dumps(describe(),sort_keys=True,indent=2))
    else:
        from supervisor import run as execute
        receipt=execute(args.operation,{'bytes':args.operation_bytes,'sha256':args.operation_sha256},args.output,BOOT)
        print(json.dumps(receipt,sort_keys=True))


if __name__ == '__main__':
    main()
