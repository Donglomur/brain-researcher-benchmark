"""Ten new stdlib-only portability controls; no self-running campaign.

The selected runner supplies the public package, its existing sibling dependency
directory and an owned scratch directory. No numerical module or original MAT
payload is imported/opened. Native spies raise before authentication/preparation;
they never invent successful authentication, arrays, or completion receipts.
"""
import builtins
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import types


CASE_COUNT = 10
FIXTURE_WRITE_CAP = 524288
CONTROL_WRITES_CAP = 491520
CLI_ERROR_RESERVATION = 32768
SOURCE_NAMES = (
    '_core/pairing.py', '_core/reference_pair.py', '_core/session_collector.py',
    '_core/session_export.py', '_core/session_projection.py', '_core/metadata.py',
    '../locked-mat-admission-v2/admission.py',
    '../train-only-decoding-v2/source_condition.py', 'prepare.py', 'adapter.py',
)


def run_controls(package_root, scratch_root, *, dependency_root=None):
    """Prepare one relocated source-only fixture and run ten new control families.

    The caller provides a bounded generated-control environment and an existing
    external scratch directory. The checked-out CLI is the trust anchor, not a new external
    descriptor-authentication framework or malicious-checkout detector.
    """
    package_root = Path(package_root).absolute()
    siblings = Path(package_root.parent if dependency_root is None else dependency_root).absolute()
    scratch = Path(scratch_root).absolute()

    def require(ok, message):
        if not ok:
            raise AssertionError(message)

    for root in (package_root, siblings, scratch):
        require(root.is_dir() and all(not p.is_symlink() for p in (root, *root.parents)),
                'Existing ordinary absolute fixture/source roots required')
    require(not scratch.is_relative_to(package_root.parents[4]) and
            not scratch.is_relative_to(siblings),
            'Generated scratch must remain outside the checked-out source namespace')

    copied_read_bytes = 0
    control_write_bytes = 0
    mat_open_attempts = []
    native_import_attempts = []
    original_source_open_attempts = []
    outcomes = []
    error_receipts = []

    def read_small(path):
        nonlocal copied_read_bytes
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                    0 < info.st_size <= 262144, 'Bounded ordinary source/fixture file required')
            chunks = []
            remaining = info.st_size
            while remaining:
                body = os.read(fd, min(65536, remaining))
                require(bool(body), 'Short bounded fixture read')
                copied_read_bytes += len(body)
                require(copied_read_bytes <= 1048576, 'Fixture-copy/receipt-read allowance exceeded')
                chunks.append(body)
                remaining -= len(body)
            return b''.join(chunks)
        finally:
            os.close(fd)

    def write_fixture(path, body, *, replace=False):
        nonlocal control_write_bytes
        path = Path(os.path.abspath(path))
        require(path.is_relative_to(scratch) and type(body) is bytes,
                'Generated writes must remain inside owned scratch')
        require(all(not p.is_symlink() for p in (path, *path.parents)), 'Fixture symlink overwrite refused')
        require(control_write_bytes + len(body) <= CONTROL_WRITES_CAP,
                'Aggregate generated writes exceed precharged fixture budget')
        control_write_bytes += len(body)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | (os.O_TRUNC if replace else os.O_EXCL)
        fd = os.open(path, flags, 0o600)
        try:
            offset = 0
            while offset < len(body):
                n = os.write(fd, body[offset:offset + 65536])
                require(n > 0, 'Short fixture write')
                offset += n
        finally:
            os.close(fd)

    descriptor_body = read_small(package_root / 'SOURCE.json')
    recipe_body = read_small(package_root / 'RECIPE.json')
    descriptor = json.loads(descriptor_body)
    require(set(descriptor['files']) == set(SOURCE_NAMES), 'Closed source namespace required for fixture copy')
    originals = {'SOURCE.json': descriptor_body, 'RECIPE.json': recipe_body}
    for name in SOURCE_NAMES:
        source = siblings / name[3:] if name.startswith('../') else package_root / name
        body = read_small(source)
        require({'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()} == descriptor['files'][name],
                'Source copy disagrees with public descriptor')
        originals[name] = body
    require({'bytes': len(recipe_body), 'sha256': hashlib.sha256(recipe_body).hexdigest()} ==
            descriptor['recipe'], 'Recipe copy disagrees with descriptor')

    checkout = scratch / 'relocated checkout with spaces'
    relocated = checkout / 'benchmarks/neural/NEURAL-025/implementations/session-preparation-v1'
    for name, body in originals.items():
        write_fixture(relocated / name, body)
    unrelated = scratch / 'unrelated working directory'
    unrelated.mkdir(mode=0o700)
    write_fixture(unrelated / 'source_condition.py', b'raise RuntimeError("cwd shadow imported")\n')
    write_fixture(unrelated / 'h5py.py', b'raise RuntimeError("native shadow imported")\n')
    inputs = scratch / 'private inputs'
    inputs.mkdir(mode=0o700)
    tiny_original = inputs / 'R,cfa24_20220727_160603,thresholded,DLC3.mat'
    wrong_name = inputs / 'wrong_session.mat'
    write_fixture(tiny_original, b'not an authentic MAT payload\n')
    write_fixture(wrong_name, b'not an authentic MAT payload\n')
    outputs = scratch / 'private outputs'
    outputs.mkdir(mode=0o700)

    @contextlib.contextmanager
    def tripwires():
        original_import, original_os_open = builtins.__import__, os.open
        original_builtin_open, original_io_open = builtins.open, io.open
        previous_cwd = Path.cwd()

        def check_path(path):
            if isinstance(path, (str, bytes, os.PathLike)):
                candidate = Path(os.path.abspath(os.fsdecode(path)))
                if candidate.suffix.lower() == '.mat':
                    mat_open_attempts.append(str(candidate))
                    raise AssertionError('A portability control attempted to open a MAT payload')
                if candidate.is_relative_to(package_root) or candidate.is_relative_to(siblings):
                    original_source_open_attempts.append(str(candidate))
                    raise AssertionError('Relocated CLI attempted original checkout/dependency fallback')

        def guarded_import(name, *args, **kwargs):
            if name.split('.')[0] in ('h5py', 'numpy', 'scipy'):
                native_import_attempts.append(name)
                raise AssertionError('Metadata/path control imported a numerical library')
            return original_import(name, *args, **kwargs)

        def guarded_os_open(path, *args, **kwargs):
            check_path(path)
            return original_os_open(path, *args, **kwargs)

        def guarded_builtin_open(path, *args, **kwargs):
            check_path(path)
            return original_builtin_open(path, *args, **kwargs)

        def guarded_io_open(path, *args, **kwargs):
            check_path(path)
            return original_io_open(path, *args, **kwargs)

        builtins.__import__, os.open = guarded_import, guarded_os_open
        builtins.open, io.open = guarded_builtin_open, guarded_io_open
        os.chdir(unrelated)
        try:
            yield
        finally:
            os.chdir(previous_cwd)
            builtins.__import__, os.open = original_import, original_os_open
            builtins.open, io.open = original_builtin_open, original_io_open

    def load_cli():
        module = types.ModuleType('portable_cli_control')
        module.__file__ = str(relocated / 'prepare.py')
        exec(compile(originals['prepare.py'], module.__file__, 'exec'), module.__dict__)
        return module

    def invoke(module, argv, native_runner=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                code = module.main(argv, native_runner=native_runner)
            except SystemExit as exc:
                code = exc.code
        require(len(stdout.getvalue()) <= 8192 and len(stderr.getvalue()) <= 8192,
                'Unexpectedly unbounded CLI diagnostic output')
        return code, stdout.getvalue(), stderr.getvalue()

    def refusal(call, kind):
        try:
            call()
        except kind:
            return
        except Exception as exc:
            raise AssertionError('Wrong refusal type: ' + type(exc).__name__) from exc
        raise AssertionError('Unsupported binding accepted')

    def case(name, action):
        try:
            with tripwires():
                action()
        except Exception as exc:
            outcomes.append({'name': name, 'status': 'failed',
                             'exception_type': type(exc).__name__, 'message': str(exc)[:400]})
        else:
            outcomes.append({'name': name, 'status': 'passed'})

    def help_control():
        module = load_cli()
        code, stdout, _ = invoke(module, ['--help'])
        require(code == 0 and 'prepare' in stdout and 'check' in stdout,
                'Cold stdlib-only help did not expose expected commands')
        require(list(outputs.iterdir()) == [], 'Help created a private output')

    case('cold_help_is_stdlib_only_and_does_not_open_mat_or_create_output', help_control)

    def relocated_check():
        module = load_cli()
        package = module.verify_package()
        require(package['root'] == relocated and package['recipe'] == module.expected_recipe(),
                'Relocated root or fixed recipe changed')
        require(set(package['sources']) == set(SOURCE_NAMES), 'Relocated source namespace differs')
        code, stdout, _ = invoke(module, ['check'])
        receipt = json.loads(stdout)
        require(code == 0 and receipt == {'source_verified': True, 'runtime_probed': False,
                                         'original_opened': False, 'scientific_qualification': False},
                'Check command promoted source-only validation')
        require(list(outputs.iterdir()) == [], 'Source-only check created outputs')

    case('relocated_check_from_unrelated_cwd_uses_only_bound_relative_sources', relocated_check)

    def spy_binding():
        module = load_cli()
        output = outputs / 'spy stops before native intake'
        seen = []

        def spy(plan):
            require(plan['original'] == tiny_original and plan['output'] == output and
                    plan['package']['root'] == relocated, 'CLI silently swapped path bindings')
            require(output.is_dir() and list(output.iterdir()) == [], 'Fresh output not created before boundary')
            seen.append({'original': str(plan['original']), 'output': str(plan['output'])})
            raise ValueError('Generated native boundary stop; no authentication attempted')

        code, stdout, _ = invoke(module, ['prepare', '--original', str(tiny_original),
                                         '--output', str(output)], native_runner=spy)
        require(code == 2 and len(seen) == 1 and not stdout, 'Spy failure was published as success or retried')
        error_path = output / 'CLI_ERROR.json'
        error = json.loads(read_small(error_path))
        error_receipts.append(error_path)
        require(error['completed'] is False and error['scientific_qualification'] is False and
                sorted(p.name for p in output.iterdir()) == ['CLI_ERROR.json'],
                'Boundary failure fabricated a completed result or arrays')
        partial_output = outputs / 'spy leaves a partial artifact'
        partial_body = b'{"completed":false,"generated_partial":true}\n'

        def partial_spy(plan):
            require(plan['original'] == tiny_original and plan['output'] == partial_output and
                    plan['package']['root'] == relocated, 'Partial-failure binding changed')
            write_fixture(partial_output / 'PARTIAL_CONTROL.json', partial_body)
            raise ValueError('Generated boundary partial; no authentication attempted')

        code, stdout, _ = invoke(module, ['prepare', '--original', str(tiny_original),
                                         '--output', str(partial_output)], native_runner=partial_spy)
        require(code == 2 and not stdout and
                sorted(p.name for p in partial_output.iterdir()) == ['PARTIAL_CONTROL.json'] and
                read_small(partial_output / 'PARTIAL_CONTROL.json') == partial_body,
                'CLI added a second diagnostic budget or overwrote/promoted an existing partial artifact')

    case('native_spy_sees_exact_bindings_and_failure_cannot_publish_completion', spy_binding)

    def existing_outputs():
        module = load_cli()
        targets = [outputs / 'existing file', outputs / 'empty directory', outputs / 'nonempty directory']
        write_fixture(targets[0], b'preserve existing file\n')
        targets[1].mkdir(mode=0o700)
        targets[2].mkdir(mode=0o700)
        write_fixture(targets[2] / 'sentinel', b'preserve contents\n')
        for target in targets:
            refusal(lambda p=target: module.bind_paths(tiny_original, p), module.Refusal)
        require(read_small(targets[0]) == b'preserve existing file\n' and
                read_small(targets[2] / 'sentinel') == b'preserve contents\n',
                'Existing destination changed during refusal')
        fresh = outputs / 'fresh helper directory'
        require(module.create_output(fresh) == fresh and fresh.is_dir(), 'Fresh output helper failed')
        refusal(lambda: module.create_output(fresh), module.Refusal)
        refusal(lambda: module.bind_paths(tiny_original, outputs / 'absent parent' / 'child'), module.Refusal)

    case('fresh_output_required_existing_files_directories_and_missing_parent_refused', existing_outputs)

    def alias_and_checkout():
        module = load_cli()
        input_alias = inputs / 'input_alias.mat'
        output_alias = outputs / 'output_alias'
        input_alias.symlink_to(tiny_original)
        output_alias.symlink_to(outputs / 'empty directory', target_is_directory=True)
        refusal(lambda: module.bind_paths(input_alias, outputs / 'alias input result'), module.Refusal)
        refusal(lambda: module.bind_paths(tiny_original, output_alias), module.Refusal)
        refusal(lambda: module.bind_paths(tiny_original, checkout / 'must_not_write_here'), module.Refusal)
        refusal(lambda: module.bind_paths(tiny_original, tiny_original), module.Refusal)
        refusal(lambda: module.bind_paths(tiny_original, tiny_original.parent), module.Refusal)

    case('symlink_checkout_and_original_location_aliases_cannot_rebind_outputs', alias_and_checkout)

    def changed_recipe_identity():
        module = load_cli()
        changed = json.loads(recipe_body)
        changed['session_id'] = 'different-session'
        changed['original']['figshare_file_id'] += 1
        body = (json.dumps(changed, sort_keys=True) + '\n').encode()
        manifest = copy.deepcopy(descriptor)
        manifest['recipe'] = {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
        output = outputs / 'wrong identity must not create'
        calls = []

        def forbidden(plan):
            calls.append(True)
            raise ValueError('Wrong identity reached native boundary')

        try:
            write_fixture(relocated / 'RECIPE.json', body, replace=True)
            write_fixture(relocated / 'SOURCE.json', (json.dumps(manifest) + '\n').encode(), replace=True)
            code, _, _ = invoke(module, ['prepare', '--original', str(tiny_original),
                                         '--output', str(output)], native_runner=forbidden)
            require(code == 2 and not calls and not output.exists(),
                    'Self-consistent metadata rewrite bypassed fixed original identity')
        finally:
            write_fixture(relocated / 'RECIPE.json', recipe_body, replace=True)
            write_fixture(relocated / 'SOURCE.json', descriptor_body, replace=True)

    case('self_consistent_recipe_identity_change_refused_before_output_or_native_boundary', changed_recipe_identity)

    def changed_core():
        module = load_cli()
        name = '_core/pairing.py'
        changed = originals[name] + b'\n# generated tamper witness\n'
        try:
            write_fixture(relocated / name, changed, replace=True)
            refusal(lambda: module.verify_package(), module.Refusal)
            manifest = copy.deepcopy(descriptor)
            manifest['files'][name] = {'bytes': len(changed), 'sha256': hashlib.sha256(changed).hexdigest()}
            write_fixture(relocated / 'SOURCE.json', (json.dumps(manifest) + '\n').encode(), replace=True)
            refusal(lambda: module.verify_package(), module.Refusal)
        finally:
            write_fixture(relocated / name, originals[name], replace=True)
            write_fixture(relocated / 'SOURCE.json', descriptor_body, replace=True)

    case('modified_immutable_helper_and_rewritten_descriptor_cannot_replace_core_pin', changed_core)

    def namespace_escape():
        module = load_cli()
        manifest = copy.deepcopy(descriptor)
        pin = manifest['files'].pop('_core/pairing.py')
        manifest['files']['../../outside_namespace.py'] = pin
        try:
            write_fixture(relocated / 'SOURCE.json', (json.dumps(manifest) + '\n').encode(), replace=True)
            refusal(lambda: module.verify_package(), module.Refusal)
        finally:
            write_fixture(relocated / 'SOURCE.json', descriptor_body, replace=True)

    case('descriptor_cannot_add_or_replace_closed_relative_dependency_paths', namespace_escape)

    def invalid_native_input():
        module = load_cli()
        for index, original in enumerate((tiny_original, wrong_name)):
            output = outputs / ('real admission refusal ' + str(index))
            code, stdout, _ = invoke(module, ['prepare', '--original', str(original), '--output', str(output)])
            require(code == 2 and not stdout, 'Wrong size/name was accepted or announced complete')
            path = output / 'CLI_ERROR.json'
            error = json.loads(read_small(path))
            error_receipts.append(path)
            require(error['completed'] is False and error['error'] == 'PreparationRefusal' and
                    sorted(p.name for p in output.iterdir()) == ['CLI_ERROR.json'],
                    'Wrong input reached authentication/native work or published completion')

    case('real_adapter_rejects_tiny_or_wrong_filename_original_before_open_or_native_import', invalid_native_input)

    def condition_binding():
        module = load_cli()
        package = module.verify_package()
        name = '../train-only-decoding-v2/source_condition.py'
        source = package['sources'][name]
        require(len(source) == 5966 and hashlib.sha256(source).hexdigest() ==
                'c7ce9b2e464c262550e6e224d7d81becb1094306ff5aeedf819068eb8d14ce11',
                'Existing exact v2 condition source changed')
        condition_module = module.module_from('source_condition', relocated / name, source)
        record = condition_module.build_source_condition('smoothed_deconvolved_events')
        digest = condition_module.validate_source_condition(record, 'smoothed_deconvolved_events')
        require(record['schema'] == package['recipe']['source_condition_schema'] ==
                'calcium_processed_input_source_condition_v2' and
                digest == hashlib.sha256(condition_module.canonical(record)).hexdigest() and
                all(value is False for value in record['qualification'].values()),
                'Actual v2 source condition or unknown-exposure qualifications changed')
        retired = copy.deepcopy(record)
        retired['schema'] = 'calcium_processed_input_source_condition_v1'
        refusal(lambda: condition_module.validate_source_condition(retired, 'smoothed_deconvolved_events'), ValueError)
        invented = copy.deepcopy(record)
        invented['qualification']['scientific_qualification'] = True
        refusal(lambda: condition_module.validate_source_condition(invented, 'smoothed_deconvolved_events'), ValueError)

    case('exact_existing_v2_condition_loaded_without_cwd_shadow_or_invented_qualification', condition_binding)

    require(len(outcomes) == CASE_COUNT, 'Frozen portable control count changed')
    error_bytes = sum(path.stat().st_size for path in error_receipts)
    require(error_bytes <= CLI_ERROR_RESERVATION and control_write_bytes + error_bytes <= FIXTURE_WRITE_CAP,
            'Combined fixture/source-tamper/error-receipt write reservation exceeded')
    passed = sum(row['status'] == 'passed' for row in outcomes)
    return {'schema': 'calcium-session-portable-generated-controls-v1',
            'status': 'passed' if passed == CASE_COUNT and not mat_open_attempts and
                      not native_import_attempts and not original_source_open_attempts else 'failed',
            'case_count': CASE_COUNT, 'passed': passed, 'failed': CASE_COUNT - passed,
            'outcomes': outcomes, 'mat_open_attempts': mat_open_attempts,
            'native_import_attempts': native_import_attempts,
            'original_checkout_fallback_open_attempts': original_source_open_attempts,
            'fixture_accounting': {'control_cumulative_write_bytes_including_tamper_restores': control_write_bytes,
                'cli_error_receipt_bytes': error_bytes, 'aggregate_fixture_write_cap_bytes': FIXTURE_WRITE_CAP,
                'fixture_copy_and_receipt_read_bytes': copied_read_bytes,
                'source_verifier_reads_metered_by_this_counter': False,
                'relocated_checkout_count': 1, 'original_array_bytes_read': 0},
            'prior_35_and_18_control_suites_repeated': False,
            'successful_original_authentication_fabricated': False,
            'numerical_pipeline_invocations': 0, 'scientific_qualification': False,
            'trust_scope': 'Trusted checked-out CLI plus its hardcoded immutable pins; descriptor coherence only',
            'malicious_whole_checkout_replacement_detection_claimed': False}


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Run the bounded generated portability controls only.')
    parser.add_argument('--scratch-dir', required=True, type=Path,
                        help='Existing caller-reserved ordinary directory outside the checkout; no automatic temp directory')
    parser.add_argument('--package-root', type=Path, default=Path(__file__).resolve().parent,
                        help='Assembled session-preparation-v1 package; defaults to this script directory')
    args = parser.parse_args()
    result = run_controls(args.package_root, args.scratch_dir)
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result['status'] == 'passed' else 1)
