"""Admit reviewed numerical operands to the unchanged protected DMFC owner.

Only source/metadata are read here. Candidate bytes are never imported or run.
Preparation cannot issue a root request. Live delegation is process replacement.
"""
import argparse
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import types

HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[4]
BASE = 'authoring/delivery-20261105/common/remaining-builds-wave40/dmfc-complete-four-cell-owner-source-20261115-v1'
BASE_FREEZE = {'path': 'authoring/delivery-20261105/common/remaining-builds-wave40/dmfc-complete-four-cell-owner-source-20261115-v1/SOURCE_FREEZE.json', 'bytes': 12385, 'sha256': '4c440b5cf3f100c0370460e4d4d61617bdcf759e1c1c0dd2bdd0d6a7354d5f52'}
CONFIG_SOURCE = {'path': BASE + '/configuration.py', 'bytes': 7650,
                 'sha256': 'f2d3ae850c7ebdf5ef3862038d75387cfb1635adb5e26a4b2a68477bf91dbdf7'}
METHOD_READER = {'path': 'authoring/dmfc-timing/paired-program-cli-v1/admission.py', 'bytes': 1506, 'sha256': '718e2a3bd539223a79a6afbe9c763e370ec36f755832ebc0e2999261b8c9807b'}
CONTRACT = {'path': 'authoring/dmfc-timing/paired-investigation-v1/PUBLIC_CONTRACT.json', 'bytes': 5194,
            'sha256': 'eb332e622e352c72014fbefdaf283c6ad313a90730c2ea110a49a8fbcfcdcb64'}
CHECKS = ('two_stage_numerical_abi', 'training_only_preparation', 'no_query_fitting',
          'same_procedure_across_views', 'allowed_view_specific_changes_reviewed',
          'no_private_assets_or_case_id_shortcuts', 'within_existing_resource_profile')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def _bootstrap_capture(root, pin):
    """Capture the one fixed pure configuration helper before using its reader."""
    import stat
    path = root / pin['path']
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'unlinked bootstrap source')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and a.st_size == pin['bytes'],
             'exact bounded pure helper')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(pin['bytes'] + 1)
        b = os.fstat(fd)
        need(all(getattr(a, k) == getattr(b, k) for k in
                 ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))
             and len(body) == pin['bytes'] and sha(body) == pin['sha256'], 'stable pinned helper')
        return body
    finally:
        os.close(fd)


def support(root):
    root = Path(root).absolute()
    need(root.is_dir() and '..' not in root.parts and
         all(not p.is_symlink() for p in (root, *root.parents)), 'ordinary repository root')
    c = types.ModuleType('_dmfc_candidate_pure_configuration')
    c.__file__ = str(root / CONFIG_SOURCE['path'])
    exec(compile(_bootstrap_capture(root, CONFIG_SOURCE), c.__file__, 'exec'), c.__dict__)
    base = c.decode(c.checked(root, BASE_FREEZE))
    need(len(base['files']) == 45 and base['entrypoint']['path'] == BASE + '/entrypoint.py',
         'exact original owner closure')
    need(sum(x['bytes'] for x in base['files'].values()) <= 1048576, 'bounded original source closure')
    for path, pin in base['files'].items():
        c.checked(root, {'path': path, **pin})
    c.checked(root, CONTRACT)
    reader_body = c.checked(root, METHOD_READER)
    nodes = [n for n in ast.parse(reader_body).body if
             isinstance(n, ast.FunctionDef) and n.name == 'read_method' or
             isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'METHOD_FIELDS' for t in n.targets)]
    need(len(nodes) == 2, 'exact accepted method fields/reader')
    namespace = {'json': json, 'need': need, 'decode': c.decode}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(root / METHOD_READER['path']), 'exec'), namespace)
    return types.SimpleNamespace(root=root, c=c, base=base, read_method=namespace['read_method'],
                                 fields=namespace['METHOD_FIELDS'])


def source_pin(s, path, cap):
    path = Path(path).absolute()
    need(path.is_relative_to(s.root) and '..' not in path.parts, 'project-local reviewed operand')
    body = s.c.capture(path, cap)
    return {'path': path.relative_to(s.root).as_posix(), 'bytes': len(body), 'sha256': sha(body)}, body


def review_candidate(s, review_pin):
    need(type(review_pin) is dict and type(review_pin.get('path')) is str
         and review_pin['path'].endswith('.json'), 'review is a frozen JSON operand')
    body = s.c.checked(s.root, review_pin, 32768)
    review = s.c.decode(body)
    fields = {'schema', 'candidate_id', 'decision', 'execution_authority', 'base_owner_freeze',
              'public_contract', 'program', 'method', 'reviewer', 'method_field_findings',
              'checks', 'findings', 'matched_method_proven_by_grader'}
    need(type(review) is dict and set(review) == fields, 'exact explicit candidate-review fields')
    need(review['schema'] == 'dmfc-external-candidate-review/v1' and review['candidate_id'] == 'NEURAL-095'
         and review['decision'] == 'source_and_procedure_reviewed_for_original_contract'
         and review['execution_authority'] is False and review['matched_method_proven_by_grader'] is False,
         'candidate review is not execution authority or automatic matching certification')
    need(review['base_owner_freeze'] == BASE_FREEZE and review['public_contract'] == CONTRACT,
         'same protected owner and original public scientific contract')
    need(type(review['reviewer']) is str and 0 < len(review['reviewer'].strip()) <= 256,
         'explicit review attribution; no claim of cryptographic authorship verification')
    need(type(review['checks']) is dict and set(review['checks']) == set(CHECKS) and
         all(review['checks'][key] is True for key in CHECKS), 'all substantive review checks recorded')
    need(type(review['method_field_findings']) is dict and set(review['method_field_findings']) == set(s.fields)
         and all(type(v) is str and 0 < len(v.strip()) <= 2048 for v in review['method_field_findings'].values()),
         'source/procedure findings for all twelve method fields')
    need(type(review['findings']) is str and 0 < len(review['findings'].strip()) <= 8192,
         'explicit review basis, not only boolean approvals')
    need(type(review['method']) is dict and type(review['method'].get('path')) is str
         and review['method']['path'].endswith('.json'), 'method is a frozen JSON operand')
    program = s.c.checked(s.root, review['program'], 65536)
    method = s.c.checked(s.root, review['method'], 32768)
    need(review['program']['path'].endswith('.py') and b'\0' not in program,
         'one finite Python numerical operand')
    ast.parse(program.decode('utf-8'), filename=review['program']['path'])  # syntax only, never exec
    declaration = s.read_method(method)
    profile = declaration.get('execution_profile')
    need(type(profile) is dict and profile.get('schema') == 'dmfc-prepare-frozen-predict-v1'
         and profile.get('training_only_prepare') is True and profile.get('query_tool_has_no_fit_call') is True
         and type(profile.get('fitted_artifact_cap_bytes')) is int and profile['fitted_artifact_cap_bytes'] == 65536
         and type(profile.get('new_reference_fits')) is int and profile['new_reference_fits'] == 0,
         'declared unchanged training-only fit / frozen prediction ABI')
    for pin in (review_pin, review['program'], review['method']):
        need(pin['path'] not in s.base['files'], 'external operands cannot replace a protected core file')
    need(len({x['path'] for x in (review_pin, review['program'], review['method'])}) == 3,
         'separate review, program and method operands')
    return review


def write_json(s, path, value):
    path = Path(path)
    body = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    need(0 < len(body) <= 262144 and path.is_relative_to(s.root), 'bounded local authored metadata')
    with path.open('xb') as stream:
        need(stream.write(body) == len(body), 'complete metadata write')
        stream.flush(); os.fsync(stream.fileno())
    path.chmod(0o444)
    return source_pin(s, path, 262144)[0]


def prepare(root, base_config, base_config_sha256, review, review_sha256, bundle_root, output_root):
    """Write only a candidate input bundle/payload; never create an operation root/request."""
    s = support(root)
    template_raw = s.c.capture(base_config)
    need(sha(template_raw) == base_config_sha256, 'exact operator configuration template')
    template = s.c.decode(template_raw)
    need(template['schema'] == 'dmfc-complete-four-cell-config/v1' and
         template['repository_root'] == str(s.root) and template['successor_freeze'] == BASE_FREEZE,
         'template uses the original owner')
    need(template['limits'] == s.c.LIMITS and template['reservation_policy'] == s.c.RESERVATIONS,
         'original complete resource limits')
    review_pin, review_raw = source_pin(s, review, 32768)
    need(sha(review_raw) == review_sha256, 'exact operator-selected candidate review')
    reviewed = review_candidate(s, review_pin)
    out = Path(output_root).absolute(); folder = Path(bundle_root).absolute()
    for p in (out, folder):
        need('..' not in p.parts and all(not x.is_symlink() for x in (p, *p.parents)), 'ordinary fresh namespace')
        need(not p.exists() and p.parent.is_dir(), 'fresh destination with existing ordinary parent')
    need(folder.is_relative_to(s.root) and folder != s.root and
         not folder.is_relative_to(out) and not out.is_relative_to(folder), 'separate input bundle and operation root')
    for key in s.c.CONTEXTS:
        need(len(os.fsencode(out / 'arms' / key / 'arm.sock')) < 100, 'original portable socket bound')
    payload = {k: copy.deepcopy(v) for k, v in template.items() if k != 'request'}
    need(set(payload) == {'schema', 'repository_root', 'output_root', 'successor_freeze', 'runtime_identity',
                         'host_budget', 'limits', 'reservation_policy', 'numerical_tool', 'method', 'actor'},
         'unchanged owner template fields')
    need(type(payload['actor']) is dict and set(payload['actor']) == {'arms'} and
         set(payload['actor']['arms']) == set(s.c.CONTEXTS), 'exact four-context template')
    binding = {'schema': 'dmfc-reviewed-external-operand-binding/v1', 'base_owner_freeze': BASE_FREEZE,
               'review': review_pin, 'program': reviewed['program'], 'method': reviewed['method'],
               'matched_method_proven_by_grader': False, 'execution_authority': False}
    freeze = copy.deepcopy(s.base)
    freeze['external_candidate'] = binding
    extras = [review_pin, reviewed['program'], reviewed['method']]
    payload.update(output_root=str(out), numerical_tool=reviewed['program'], method=reviewed['method'],
                   candidate_admission=binding)
    actor_program = {'path': BASE + '/offline_actor.py', **s.base['files'][BASE + '/offline_actor.py']}
    folder.mkdir(mode=0o700)
    for key in s.c.CONTEXTS:
        actor_config = {'schema': 'dmfc-offline-reference/v1', 'mode': key,
                        'tool_id': 'dmfc_predict@' + reviewed['program']['sha256'],
                        'policy': 'single_frozen_fit_batch/v1'}
        pin = write_json(s, folder / (key + '.json'), actor_config); extras.append(pin)
        payload['actor']['arms'][key] = {'actor_context': key, 'context_dir': str(out / 'actors' / key),
                                        'program': actor_program, 'config': pin}
    for pin in extras:
        need(pin['path'] not in freeze['files'], 'no protected-member shadowing')
        freeze['files'][pin['path']] = {k: pin[k] for k in ('bytes', 'sha256')}
    payload['successor_freeze'] = write_json(s, folder / 'CANDIDATE_FREEZE.json', freeze)
    payload_pin = write_json(s, folder / 'CONFIGURATION_PAYLOAD.json', payload)
    return {'status': 'reviewed_candidate_inputs_prepared', 'payload': payload_pin,
            'payload_sha256_for_root_request': sha(s.c.encode(payload)),
            'candidate_source_imported': False, 'operation_root_created': False,
            'request_created': False, 'execution_authority': False}


def validate(root, config, config_sha256, review_sha256):
    """Accept only seven literal operand additions to the same 45 protected files."""
    s = support(root)
    body = s.c.capture(config)
    need(sha(body) == config_sha256, 'exact selected complete configuration')
    value = s.c.decode(body)
    need(value['schema'] == 'dmfc-complete-four-cell-config/v1' and value['repository_root'] == str(s.root),
         'same operation schema/repository')
    binding = value['candidate_admission']
    need(type(binding) is dict and set(binding) == {'schema', 'base_owner_freeze', 'review', 'program', 'method',
                                                  'matched_method_proven_by_grader', 'execution_authority'},
         'exact candidate binding fields')
    need(binding['schema'] == 'dmfc-reviewed-external-operand-binding/v1'
         and binding['base_owner_freeze'] == BASE_FREEZE and binding['execution_authority'] is False
         and binding['matched_method_proven_by_grader'] is False
         and binding['review']['sha256'] == review_sha256, 'exact explicitly selected review binding')
    reviewed = review_candidate(s, binding['review'])
    need(binding['program'] == reviewed['program'] == value['numerical_tool'] and
         binding['method'] == reviewed['method'] == value['method'], 'same reviewed candidate operands')
    frozen = s.c.decode(s.c.checked(s.root, value['successor_freeze']))
    need(set(frozen) == set(s.base) | {'external_candidate'} and frozen['external_candidate'] == binding,
         'only the reviewed operand binding extends the source declaration')
    for key in s.base:
        if key != 'files': need(frozen[key] == s.base[key], 'protected owner/module/scientific scope unchanged')
    extras = [binding['review'], binding['program'], binding['method']]
    need(set(value['actor']) == {'arms'} and set(value['actor']['arms']) == set(s.c.CONTEXTS), 'all four actor contexts')
    actor_pin = {'path': BASE + '/offline_actor.py', **s.base['files'][BASE + '/offline_actor.py']}
    for key in s.c.CONTEXTS:
        arm = value['actor']['arms'][key]
        need(set(arm) == {'actor_context', 'context_dir', 'program', 'config'} and
             arm['actor_context'] == key and arm['program'] == actor_pin and
             arm['context_dir'] == str(Path(value['output_root']) / 'actors' / key), 'unchanged isolated actor')
        public = s.c.decode(s.c.checked(s.root, arm['config'], 65536))
        need(public == {'schema': 'dmfc-offline-reference/v1', 'mode': key,
                        'tool_id': 'dmfc_predict@' + reviewed['program']['sha256'],
                        'policy': 'single_frozen_fit_batch/v1'}, 'only sanitized tool-hash actor change')
        extras.append(arm['config'])
    need(len({p['path'] for p in extras}) == 7 and all(p['path'] not in s.base['files'] for p in extras),
         'seven distinct external operands, no protected replacement')
    expected_files = {**s.base['files'], **{p['path']: {k: p[k] for k in ('bytes', 'sha256')} for p in extras}}
    need(frozen['files'] == expected_files and len(expected_files) == 52, 'exact core-plus-seven source inventory')
    need(value['limits'] == s.c.LIMITS and value['reservation_policy'] == s.c.RESERVATIONS,
         'unchanged full scientific resource profile')
    request = s.c.decode(s.c.checked(s.root, value['request']))
    payload = {k: v for k, v in value.items() if k != 'request'}
    need(request['configuration_payload_sha256'] == sha(s.c.encode(payload)),
         'existing root request binds candidate, review and complete operation')
    # The owner rechecks source, actual request authority/freshness, capacity,
    # runtime, output and all resource predicates. This gate never fabricates them.
    return [sys.executable, '-I', '-B', str(s.root / s.base['entrypoint']['path']),
            '--config', str(Path(config).absolute()), '--config-sha256', config_sha256], s.root


def attach(root, payload_path, payload_sha256, request_path, request_sha256, config_path):
    """Attach an existing request by the accepted bundle.attach_request rule.

    This only constructs metadata. It never creates, refreshes or admits a grant;
    validate and the unchanged owner remain mandatory before live execution.
    """
    s = support(root)
    payload_pin, body = source_pin(s, payload_path, 262144)
    need(payload_pin['sha256'] == payload_sha256, 'exact previously prepared payload')
    payload = s.c.decode(body)
    need('request' not in payload, 'unattached configuration payload')
    request_pin, request_body = source_pin(s, request_path, 262144)
    need(request_pin['sha256'] == request_sha256, 'exact existing operator request')
    request = s.c.decode(request_body)
    need(request['configuration_payload_sha256'] == sha(s.c.encode(payload)),
         'existing request binds the entire candidate configuration')
    destination = Path(config_path).absolute()
    need(destination.is_relative_to(s.root) and '..' not in destination.parts
         and all(not p.is_symlink() for p in (destination, *destination.parents))
         and not destination.exists() and destination.parent.is_dir(), 'fresh ordinary local config destination')
    config = write_json(s, destination, {**payload, 'request': request_pin})
    return {'status': 'existing_request_attached_not_admitted', 'configuration': config,
            'request_created_or_refreshed': False, 'execution_authority': False}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    a = sub.add_parser('prepare')
    for flag in ('base-config', 'base-config-sha256', 'review', 'review-sha256', 'bundle-root', 'output-root'):
        a.add_argument('--' + flag, required=True)
    a.add_argument('--repository-root', type=Path, default=ROOT)
    a = sub.add_parser('attach')
    for flag in ('payload', 'payload-sha256', 'request', 'request-sha256', 'config'):
        a.add_argument('--' + flag, required=True)
    a.add_argument('--repository-root', type=Path, default=ROOT)
    a = sub.add_parser('run')
    for flag in ('config', 'config-sha256', 'review-sha256'): a.add_argument('--' + flag, required=True)
    a.add_argument('--repository-root', type=Path, default=ROOT)
    a.add_argument('--dry-run', action='store_true')
    args = p.parse_args(argv)
    if args.action == 'prepare':
        result = prepare(args.repository_root, args.base_config, args.base_config_sha256,
                         args.review, args.review_sha256, args.bundle_root, args.output_root)
    elif args.action == 'attach':
        result = attach(args.repository_root, args.payload, args.payload_sha256,
                        args.request, args.request_sha256, args.config)
    else:
        command, root = validate(args.repository_root, args.config, args.config_sha256, args.review_sha256)
        if not args.dry_run:
            os.chdir(root); os.execv(command[0], command)
            raise RuntimeError('os.execv unexpectedly returned')
        result = {'argv': command, 'working_directory': str(root), 'executed': False,
                  'owner_admission_performed': False, 'capacity_or_runtime_probed': False,
                  'candidate_source_imported': False, 'matched_method_proven_by_grader': False}
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, SyntaxError) as error:
        print(json.dumps({'status': 'refused', 'reason': str(error)}), file=sys.stderr)
        raise SystemExit(2)
