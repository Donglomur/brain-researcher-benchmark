"""Participant adapter for the two frozen released author models, never training."""
import argparse
from pathlib import Path
import runpy
import sys
import tempfile
from reference_core import (ACCESS, body, decode, encode, method_plan, need,
                            path, pin, read, validate_job, write_new)


def invoke_author(helper_root, selected, input_root, output, scratch, *, cpu_seconds):
    """Only scientific boundary. No caller-supplied program or callable is accepted."""
    old_argv, old_path = sys.argv, list(sys.path)
    try:
        sys.path.insert(0, str(helper_root))
        sys.argv = [str(helper_root / 'author_predict.py'),
                    '--source', str(input_root / 'official_source'),
                    '--inputs', str(input_root / 'inputs'), '--arm', selected['arm'],
                    '--mode', 'predict', '--report', str(scratch / 'author_report.json'),
                    '--output', str(output / 'offline.h5'),
                    '--cpu-seconds-remaining', str(cpu_seconds)]
        runpy.run_path(str(helper_root / 'author_predict.py'), run_name='__main__')
    finally:
        sys.argv, sys.path[:] = old_argv, old_path
    return read(scratch / 'author_report.json')


def validate_author_report(report, selected):
    need(type(report) is dict and report.get('schema') == 'smc_native_attempt_v1'
         and report.get('mode') == 'predict' and report.get('arm') == selected['arm']
         and report.get('seed') == selected['seed'] and report.get('particles') == 192
         and report.get('source_requested_repeats') == 32 and report.get('smooth') is False
         and report.get('complete_source_prediction') is True,
         'Completed original selected author inference report')
    return report


def run(plan_path, execution_path, source_path, bindings_path, helper_root, input_root, output):
    plan_raw, job_raw = body(plan_path), body(execution_path)
    binding_raw = body(bindings_path)
    bindings, plan, job = decode(binding_raw), decode(plan_raw), decode(job_raw)
    program_pin, binding_pin = pin(body(source_path)), pin(binding_raw)
    selected = validate_job(plan, job, program_pin, binding_pin)
    need(job['declaration_sha256'] == pin(plan_raw)['sha256'], 'Actual frozen declaration bytes')
    helper_root, input_root, output = map(path, (helper_root, input_root, output))
    need(bindings['schema'] == 'smc_author_reference_bindings_v1', 'Exact helper binding schema')
    expected_helpers = {'author_predict.py', 'prepare.py', 'memory_reduction.py',
                        'particle_reduction.patch', 'scorer.py', 'source_manifest.json', 'reference_panel.json'}
    need(set(bindings['helpers']) == expected_helpers, 'Exact original helper closure')
    for name, expected in bindings['helpers'].items():
        body(helper_root / name, expected)
    need(output.is_dir() and not any(output.iterdir()), 'Fresh private participant output')
    # No TEST targets, operator evaluator, or calibration predictions are accepted by this API.
    need(not (input_root / 'inputs/mc_maze/test/eval_target_20ms.h5').exists(),
         'Original TEST target is evaluator-only')
    with tempfile.TemporaryDirectory(prefix='smc-author-reference-') as temporary:
        report = invoke_author(helper_root, selected, input_root, output, path(Path(temporary).resolve()),
                               cpu_seconds=job['resource_profile']['cpu_seconds'])
        validate_author_report(report, selected)
    need({p.name for p in output.iterdir()} == {'offline.h5'}, 'Only original author prediction output')
    prediction = output / 'offline.h5'
    # Authenticating the complete predictions is performed by the retained output capture
    # and the original freeze validator; no substitute model/scorer is introduced here.
    st = prediction.lstat()
    need(prediction.is_file() and not prediction.is_symlink() and st.st_nlink == 1
         and 0 < st.st_size <= job['max_file_bytes'], 'Bounded original prediction file')
    actual = {'schema': 'smc_author_reference_actual_v2', 'route': plan['route'],
              'role': 'author_calibration', 'phase_id': plan['phase_id'],
              'access_condition': ACCESS, 'recipe': selected,
              'resource_profile': dict(job['resource_profile']),
              'program_sha256': program_pin['sha256'], 'bindings': binding_pin,
              'method_freeze_sha256': job['method_freeze_sha256'],
              'author_report': report, 'training': False, 'adaptation': False,
              'AI_attempt': False, 'scientific_improvement': False}
    write_new(output / 'actual_declaration.json', encode(actual))
    return actual


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('input', 'out', 'outcome', 'declaration', 'selected-artifacts'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args(argv)
    need(vars(args) == {'input': '/materials', 'out': '/output', 'outcome': 'author_reference',
         'declaration': '/declaration.json', 'selected_artifacts': '/selected_artifacts'},
         'Fixed reference-only worker ABI')
    return run(Path(args.declaration), Path('/execution.json'), Path(__file__).resolve(),
               Path('/selected_artifacts/BINDINGS.json'),
               Path('/selected_artifacts/author_reference'), Path(args.input), Path(args.out))


if __name__ == '__main__':
    main()
