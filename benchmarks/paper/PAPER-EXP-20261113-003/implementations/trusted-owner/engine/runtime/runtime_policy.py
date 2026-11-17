"""Trusted portable runtime admission. No scientific estimator or dispatch."""
import hashlib
import os
from pathlib import Path
import platform
import re

from custody import decode, encoded, need, read_pin
from build_spec import make_plan

DEPENDENCIES_BYTES = 54066  # sealed by the source composer
DEPENDENCIES_SHA256 = 'c14b3cb46b988166263ebe52fa652224c5c5009b77e107ad7dc6e29d3d25ad49'
LEGACY_IMAGE = 'sha256:6ecc77df0c41c473879dc96df669206e40984c01c7e6e2451c5368e465e27a09'
IMAGE_RE = re.compile(r'^sha256:[0-9a-f]{64}$')
FORBIDDEN_ASSET_SHA256S = set({'f39febcc26127e58ccc3d496897cdb15aeffc4e905218a4381a9513c9dad58a8', '9efc751ed817db79efa006574ab105c399c09a481845eb66b996ffba98ef95ee', '2ab0a58d1de17eb205dfd10dd44a4b2e22ed45cc8d259d64d32350fbf85cbda7', '0144f68f1da7e0874ad92a155a1624a102a93bc41bcbbd4c5a40415a6e2e3e80', '797b3a769bd43cd3632a55977d171bb6c6c97bdd48e53f3fc878e0db12fc373d', 'b50a91c8a86b978a6511925b85cd7d728c5bb172fbbd7de907f5fde610d49123', 'daca0cc3b7fbbf9d5f5a3157e6ba19df6df5029d68ca1eedc51bff7af2371788', '1e386fe04e83b0ad46764b8db27e9f291f520d6f1021c7b753cd465617dfca4b', '28cbd720fea8841f40102b1d57fdc882a1c4035bfabf410c197db8811e0d7eb6', 'a5f8449e4811da5929b07cb2132c6798f117f78326b8d70e366f8ef4bee81a01', 'ac953214b1cc52d2d8840fc9e5889ecb24de8df1b5df97e9ba13af7418b7a2e6', 'c291b6652c0d5fd5f563b18a93c0420adccfd54b13cd5f6242ed3a1127d8be1a', '9e0469ba0499da0f9713bbdb08c23c2717323611b1fc45608b1d488b49cc9313', '4901c1ef86ac172e957b6f4a512efaee9015ad3785b7098af74063709901fafe', '0e00876003602d6bcb7852c9faf430eb54c4650548d7451d7bfac1e7228412dd', '5af962908c8f53c687ddee2f094d168918a4dc418777b65f37535c815435e9e2', '5cb413f68196bff8bc2d0508cb2e8ca1a446946c9fba7f846f35683ba90bb433', 'd1d3c6aac411db6cff5e8234d3c1d3829f864e61ff850ea268be59b8aa71fb59', 'b0ca174ff59dc8dcabd2c46aa8d529f47794bc1eaac81639b8a2fc7a3b0e1a5c', 'caa4ac8a0ee84821c19df5fc26c4a7527ef164c6f48f19e2deed3d0a888cd334', '7d8a594c5a1b99f6e810f6faa7ec0b5dad0912c9e28102fcb68dc35536c34070'})
FORBIDDEN_ASSET_SHA256S.update(['e81edc36ab0e5b29a8d93adfdd4b130ed742834a8ad03443f934acf338d55603', '4901c1ef86ac172e957b6f4a512efaee9015ad3785b7098af74063709901fafe', 'a50d003742aab5ec8611d4757c59e8b4a70654825ca47ad9c73d829a9ed0b39f', '045b4ae261e5dfb5e50f527af6ca7f62008112dfe1c3d8c7c84ffe485bc9dccb', 'b6e220d597f2848c83f78c25cd981980888856431701441f426c329e555b9e22', 'c97e06e33d6d40f21fa61178d9c391066dd068ce4b16a468aaa01470a883e5ca', '79b3a6be47c1240ba0f19389da5b03251e86502e91d30b38b1ed25281161f07c', 'e78b3e4050b9af95efb7e006778c11f78c349c7ecf17f41bababd75c8a0d20be', '7d8a594c5a1b99f6e810f6faa7ec0b5dad0912c9e28102fcb68dc35536c34070', 'c291b6652c0d5fd5f563b18a93c0420adccfd54b13cd5f6242ed3a1127d8be1a', '9e0469ba0499da0f9713bbdb08c23c2717323611b1fc45608b1d488b49cc9313', '797b3a769bd43cd3632a55977d171bb6c6c97bdd48e53f3fc878e0db12fc373d', 'caa4ac8a0ee84821c19df5fc26c4a7527ef164c6f48f19e2deed3d0a888cd334', 'f39febcc26127e58ccc3d496897cdb15aeffc4e905218a4381a9513c9dad58a8', '2ab0a58d1de17eb205dfd10dd44a4b2e22ed45cc8d259d64d32350fbf85cbda7', 'ac953214b1cc52d2d8840fc9e5889ecb24de8df1b5df97e9ba13af7418b7a2e6', '28cbd720fea8841f40102b1d57fdc882a1c4035bfabf410c197db8811e0d7eb6', '0e00876003602d6bcb7852c9faf430eb54c4650548d7451d7bfac1e7228412dd', 'daca0cc3b7fbbf9d5f5a3157e6ba19df6df5029d68ca1eedc51bff7af2371788', '0144f68f1da7e0874ad92a155a1624a102a93bc41bcbbd4c5a40415a6e2e3e80', 'a5f8449e4811da5929b07cb2132c6798f117f78326b8d70e366f8ef4bee81a01', '5af962908c8f53c687ddee2f094d168918a4dc418777b65f37535c815435e9e2', '1e386fe04e83b0ad46764b8db27e9f291f520d6f1021c7b753cd465617dfca4b', '9efc751ed817db79efa006574ab105c399c09a481845eb66b996ffba98ef95ee', 'b0ca174ff59dc8dcabd2c46aa8d529f47794bc1eaac81639b8a2fc7a3b0e1a5c'])
FORBIDDEN_ASSET_SHA256S.add('58133c51bb0a290146738a212fe3a0c3b4088f23f4fd077d2b157d4ce2d84040')
POLICY_KEYS = {'schema', 'uid', 'gid', 'image', 'platform', 'mapping', 'image_evidence'}
MAPPING = 'local_linux_conventional_numeric_bind_v1'


def dependencies():
    return decode(read_pin({'path': str(Path(__file__).with_name('DEPENDENCIES.json')),
                           'bytes': DEPENDENCIES_BYTES, 'sha256': DEPENDENCIES_SHA256}))


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def numeric_identity(value):
    need(type(value) is int and 1 <= value <= 2147483647, 'runtime_nonroot_numeric_identity')
    return value


def policy_shape(value):
    need(type(value) is dict and set(value) == POLICY_KEYS and
         value['schema'] == 'nider_portable_runtime_policy_v1', 'runtime_policy_schema')
    numeric_identity(value['uid']); numeric_identity(value['gid'])
    need(value['platform'] == 'linux/arm64' and value['mapping'] == MAPPING, 'runtime_platform_mapping')
    need(type(value['image']) is str and IMAGE_RE.fullmatch(value['image']) is not None and
         value['image'] != LEGACY_IMAGE, 'runtime_new_clean_image')
    return value


def user(value):
    policy_shape(value)
    return str(value['uid']) + ':' + str(value['gid'])


def image_observation(obj, expected_image):
    need(type(obj) is list and len(obj) == 1, 'runtime_image_observation')
    item = obj[0]
    need(item['Id'] == expected_image and item['Os'] == 'linux' and item['Architecture'] == 'arm64',
         'runtime_image_platform_identity')
    need(type(item['RootFS']['Layers']) is list and item['RootFS']['Layers'] and
         all(IMAGE_RE.fullmatch(x) for x in item['RootFS']['Layers']), 'runtime_image_layers')
    need(item['Config']['Labels'].get('nider.setup_lock') == DEPENDENCIES_SHA256 and
         item['Config']['Labels'].get('nider.build_kind') == 'clean-offline-dependencies-v2-inert-default',
         'runtime_image_provenance_labels')
    need(item['Config']['Entrypoint'] == ['/bin/false'] and item['Config']['Cmd'] in (None, []) and
         item['Config']['User'] == '65534:65534' and not item['Config'].get('Volumes'),
         'runtime_dependency_image_defaults')
    return item


def image_evidence(entry, expected_image):
    """Validate retained observed metadata; never accept an asserted pass flag."""
    value = decode(read_pin(entry))
    keys = {'schema', 'build_plan', 'build_lifecycle', 'image_inspection', 'runtime_inventory',
            'filesystem_audit', 'base_image_inspection', 'image_history', 'setup_lock_sha256', 'image', 'base_manifest'}
    need(type(value) is dict and set(value) == keys and
         value['schema'] == 'nider_clean_dependency_image_evidence_v1', 'runtime_evidence_schema')
    fixed = dependencies()
    need(value['image'] == expected_image and value['setup_lock_sha256'] == DEPENDENCIES_SHA256 and
         value['base_manifest'] == fixed['base'], 'runtime_evidence_identity')
    build = decode(read_pin(value['build_plan']))
    life = decode(read_pin(value['build_lifecycle']))
    observed = image_observation(decode(read_pin(value['image_inspection'])), expected_image)
    base_observation = decode(read_pin(value['base_image_inspection']))
    history = decode(read_pin(value['image_history']))
    need(type(base_observation) is list and len(base_observation) == 1, 'runtime_base_observation')
    base = base_observation[0]
    need(base['Os'] == 'linux' and base['Architecture'] == 'arm64' and fixed['base'] in base['RepoDigests'] and observed['RootFS']['Layers'][:len(base['RootFS']['Layers'])] == base['RootFS']['Layers'], 'runtime_base_layer_lineage')
    def environment(entries):
        need(type(entries) is list and all(type(x) is str and '=' in x for x in entries), 'runtime_image_environment')
        result = dict(x.split('=',1) for x in entries)
        need(len(result) == len(entries), 'runtime_duplicate_environment')
        return result
    expected_env = environment(base['Config']['Env'])
    for i, token in enumerate(build['create_argv']):
        if token == '--env':
            key, val = build['create_argv'][i+1].split('=',1); expected_env[key] = val
    need(environment(observed['Config']['Env']) == expected_env, 'runtime_exact_dependency_environment')
    labels = dict(base['Config'].get('Labels') or {}); labels.update({'nider.setup_lock':DEPENDENCIES_SHA256,'nider.build_kind':'clean-offline-dependencies-v2-inert-default','nider.build_owner':build['owned_name']})
    need(observed['Config']['Labels'] == labels, 'runtime_exact_dependency_labels')
    need(type(history) is list and history and all(type(x) is dict and type(x.get('CreatedBy')) is str for x in history), 'runtime_image_history')
    import json
    text = json.dumps([observed['Config'],history],sort_keys=True)
    need(not any(x in text for x in ('/Users/','neuroscience-benchmark-data','REFERENCE_VALUES.json','ISSUER_KEY.bin','official_source.R','article.pdf')), 'runtime_no_private_config_history')
    inventory = decode(read_pin(value['runtime_inventory']))
    audit = decode(read_pin(value['filesystem_audit'], maximum=8388608))
    need(build['schema'] == 'nider_clean_offline_build_plan_v1' and
         build['setup_lock_sha256'] == DEPENDENCIES_SHA256 and build['base'] == fixed['base'] and
         build['platform'] == 'linux/arm64' and build['network'] == 'none' and
         build['input_scope'] == 'only_locked_dependencies_and_installers' and
         build['acquisition_selected'] is False and build['candidate_inputs_mounted'] == [],
         'runtime_build_plan_join')
    need(build == make_plan(build['staging'], build['owner_root'], build['owned_name'], fixed, DEPENDENCIES_SHA256), 'runtime_complete_build_spec')
    need(life['schema'] == 'nider_clean_offline_build_lifecycle_v1' and
         life['plan_sha256'] == value['build_plan']['sha256'] and life['image'] == expected_image and
         life['attempts'] == 1 and life['exit_code'] == 0 and life['reaped'] is True and
         life['failure'] is None and life['owned_cleanup_verified'] is True and
         set(life['pipe_EOF']) == {'stdout', 'stderr'}, 'runtime_build_actual_join')
    need(type(life['commands']) is list and len(life['commands']) >= 3, 'runtime_build_command_records')
    for record, expected in zip(life['commands'][:3], (build['create_argv'], build['start_argv'], build['commit_argv'])):
        need(record['argv'] == expected and record['exit_code'] == 0 and record['reaped'] is True and set(record['EOF']) == {'stdout','stderr'} and record['truncated'] is False and record['reason'] is None, 'runtime_actual_build_commands')
    need(inventory['schema'] == 'nider_portable_dependency_inventory_v1' and
         inventory['image'] == expected_image and inventory['R_version'] == fixed['R_version'] and
         inventory['platform'] == 'aarch64-unknown-linux-gnu' and
         inventory['R_packages'] == [{'Package': x['Package'], 'Version': x['Version']}
                                     for x in fixed['R_packages']] and
         inventory['OS_packages'] == [{'Package': x['Package'], 'Version': x['Version'],
                                       'Architecture': x['Architecture']} for x in fixed['OS_packages']],
         'runtime_dependency_inventory')
    need(type(inventory['R_home_tree_sha256']) is str and re.fullmatch('[0-9a-f]{64}', inventory['R_home_tree_sha256']) and
         type(inventory['library_tree_sha256']) is str and re.fullmatch('[0-9a-f]{64}', inventory['library_tree_sha256']) and
         type(inventory['compiler']) is dict and set(inventory['compiler']) == {'CC','CXX','FC'} and
         all(type(x) is str and 0 < len(x) <= 4096 and x.strip() and '\x00' not in x for x in inventory['compiler'].values()) and
         type(inventory['BLAS']) is dict and set(inventory['BLAS']) == {'path','sha256'} and
         type(inventory['BLAS']['path']) is str and 0 < len(inventory['BLAS']['path']) <= 4096 and
         Path(inventory['BLAS']['path']).is_absolute() and '\x00' not in inventory['BLAS']['path'] and
         type(inventory['BLAS']['sha256']) is str and re.fullmatch('[0-9a-f]{64}', inventory['BLAS']['sha256']) and
         inventory['library_paths'] == ['/opt/nider/library', '/usr/local/lib/R/library'],
         'runtime_binary_provenance')
    need(audit['schema'] == 'nider_dependency_image_content_audit_v1' and
         audit['image'] == expected_image and audit['setup_lock_sha256'] == DEPENDENCIES_SHA256 and
         audit['build_plan_sha256'] == value['build_plan']['sha256'] and
         type(audit['regular_file_count']) is int and audit['regular_file_count'] > 0 and
         type(audit['regular_file_bytes']) is int and audit['regular_file_bytes'] > 0 and
         re.fullmatch('[0-9a-f]{64}', audit['filesystem_manifest_sha256']) and
         audit['forbidden_asset_digest_matches'] == [] and audit['forbidden_path_matches'] == [] and
         audit['unexpected_build_inputs'] == [] and audit['complete_export'] is True and
         audit['scope'] == 'all_exported_regular_files_plus_build_input_closure_not_universal_backdoor_proof',
         'runtime_dependency_content_audit')
    regular = audit['file_manifest']
    need(type(regular) is list and len(regular) == audit['regular_file_count'] and sum(x['bytes'] for x in regular) == audit['regular_file_bytes'], 'runtime_complete_content_manifest')
    import json
    need(hashlib.sha256(json.dumps(regular, sort_keys=True, separators=(',',':')).encode()).hexdigest() == audit['filesystem_manifest_sha256'], 'runtime_content_manifest_digest')
    need(not any(x['sha256'] in FORBIDDEN_ASSET_SHA256S for x in regular), 'runtime_no_known_asset_bodies')
    need(len({x['path'] for x in regular}) == len(regular) and all(type(x['bytes']) is int and x['bytes'] >= 0 and re.fullmatch('[0-9a-f]{64}',x['sha256']) for x in regular), 'runtime_file_manifest_schema')
    need(set(value[k]['sha256'] for k in ('image_inspection','base_image_inspection','image_history','runtime_inventory','filesystem_audit')).issubset(
         set(life['retained_metadata_sha256'])), 'runtime_evidence_custody')
    return value, observed


def admit(entry):
    value = policy_shape(decode(read_pin(entry)))
    image_evidence(value['image_evidence'], value['image'])
    return value


def host_observation():
    return {'system': platform.system(), 'machine': platform.machine(),
            'uid': os.geteuid(), 'gid': os.getegid(),
            'docker_environment': {k: os.environ[k] for k in
                ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH') if k in os.environ}}


def _same_image_json(left, right):
    """JSON equality preserving scalar types and ordered arrays."""
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return (all(type(k) is str for k in left) and set(left) == set(right)
                and all(_same_image_json(left[k], right[k]) for k in left))
    if type(left) is list:
        return len(left) == len(right) and all(
            _same_image_json(x, y) for x, y in zip(left, right))
    if type(left) not in (str, int, float, bool, type(None)):
        return False
    if type(left) is float and (left != left or left in (float('inf'), float('-inf'))):
        return False
    return left == right


def _image_config_for_comparison(item, built):
    """Normalize only the observed Docker API representation differences.

    Docker API v1.50 removed these container-only fields from image inspect.
    Moby also emits typed zero defaults for old-API compatibility. A common
    field may differ only when the current value is that documented default;
    arbitrary current nondefault changes remain rejected.
    Cmd must be explicitly present and empty on both sides. No other field,
    unknown key, command, environment, label or image default is discarded.
    Original inspections are never mutated.
    """
    need(type(item) is dict and type(built) is dict, 'runtime_image_config_schema')
    left, right = dict(item), dict(built)
    legacy_types = {
        'Hostname': str, 'Domainname': str, 'Image': str,
        'AttachStdin': bool, 'AttachStdout': bool, 'AttachStderr': bool,
        'Tty': bool, 'OpenStdin': bool, 'StdinOnce': bool,
    }
    for key, kind in legacy_types.items():
        need(all(key not in value or type(value[key]) is kind
                 for value in (left, right)), 'runtime_legacy_image_config_type')
        need(key not in left or key not in right or
             (_same_image_json(left[key], right[key]) or
              _same_image_json(left[key], kind())),
             'runtime_common_legacy_image_config_changed')
        left.pop(key, None)
        right.pop(key, None)
    for value in (left, right):
        need('Cmd' in value and (value['Cmd'] is None or
             (type(value['Cmd']) is list and not value['Cmd'])),
             'runtime_explicit_empty_image_command')
        value['Cmd'] = []
    return left, right


def validate_imported_image(item, built):
    """Require immutable ID/platform/ordered RootFS and semantic image config.

    Preserve both complete inspections. Only nine documented container-only
    field omissions/default projection and empty Cmd null/list representation differ
    across the observed Docker APIs. Non-image storage observations remain
    outside comparison, as before; all other Config values stay exact.
    """
    need(type(item) is dict and type(built) is dict and
         all(key in item and key in built and
             _same_image_json(item[key], built[key])
             for key in ('Id', 'Os', 'Architecture', 'RootFS')),
         'runtime_imported_image_identity_config_layers')
    need('Config' in item and 'Config' in built, 'runtime_image_config_missing')
    left, right = _image_config_for_comparison(item['Config'], built['Config'])
    need(_same_image_json(left, right), 'runtime_imported_image_semantic_config')
    return True

def validate_live(value, host, context, info, image):
    policy_shape(value)
    need(host['system'] == 'Linux' and host['machine'] in ('aarch64','arm64') and
         host['uid'] == value['uid'] and host['gid'] == value['gid'] and
         host['docker_environment'] == {}, 'runtime_actual_owner_host')
    need(type(context) is list and len(context) == 1 and
         context[0]['Endpoints']['docker']['Host'] == 'unix:///var/run/docker.sock' and
         context[0]['Endpoints']['docker'].get('SkipTLSVerify') is False,
         'runtime_local_docker_endpoint')
    need(info['OSType'] == 'linux' and info['Architecture'] in ('aarch64','arm64') and
         type(info['SecurityOptions']) is list and
         not any('rootless' in x.lower() or 'userns' in x.lower() for x in info['SecurityOptions']) and
         not info.get('DockerRootDir','').startswith('/home/'), 'runtime_conventional_mapping')
    item = image_observation(image, value['image'])
    _, admitted = image_evidence(value['image_evidence'], value['image'])
    validate_imported_image(item, admitted)
    return {'schema': 'nider_portable_live_admission_v1', 'runtime_policy_sha256': digest(value),
            'uid': value['uid'], 'gid': value['gid'], 'image': value['image'],
            'host': host, 'context': context, 'docker_info': info, 'image_inspection': image}


def observe_live(value, json_call):
    """Dispatch only via the existing bounded owner command recorder."""
    host = host_observation()
    need(host['system'] == 'Linux' and host['machine'] in ('aarch64','arm64') and
         host['uid'] == value['uid'] and host['gid'] == value['gid'] and host['docker_environment'] == {},
         'runtime_actual_owner_host')
    context = json_call(['docker', 'context', 'inspect'])
    info = json_call(['docker', 'info', '--format', '{{json .}}'])
    image = json_call(['docker', 'image', 'inspect', value['image']])
    return validate_live(value, host, context, info, image)


def owned_files(value, entries):
    for entry in entries:
        p = Path(entry['path']); info = p.stat()
        need(info.st_uid == value['uid'] and info.st_gid == value['gid'], 'runtime_staged_owner_identity')
        need(info.st_mode & 0o077 == 0, 'runtime_staged_private_mode')
