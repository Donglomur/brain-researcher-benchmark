"""Source-only exact finite-cost successor of the preserved f778 publication.

No authentic input is copied and no runtime is launched. Nested locators in the
root adoption are documentary: only the seven fixed, pinned evidence roles are
read and copied. A finite known subtotal is not current native authority.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import stat
import types

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
BASE_PATH = Path('benchmarks/neural/NEURAL-034/implementations/runtime-prerequisite-v1/configure.py')
BASE_PIN = {'bytes': 12052, 'sha256': '96efeaac37ca63317571d41a3ec37a9c6e6945a5f543959a23816162e22a613d'}
LOCAL = 'authoring/glial-context-v1/ordinary-completion-v1/'
ADMISSION = LOCAL + 'admission.py'
FREEZE = LOCAL + 'SOURCE_FREEZE.json'
ARCHIVE = 'predecessor-finite-cost-v1/'
EVIDENCE = 'operator-cost/neural034-finite-supplement-v1/'
PREFIX = 'authoring/task-capacity-successors-20261102/astrocyte/'
PREDECESSOR_MANIFEST = {'bytes': 9102, 'sha256': 'b0a286c91e4d7b314b3fb17f257692d88ed3c73aca79aa65be5eede2d1935b9a'}
PREDECESSOR_FREEZE = {'bytes': 5723, 'sha256': '1546d0711d94c6d17e6ff86f1560a3ef3e15eadfef8d16d204bbf59dc492e9ba'}
PREDECESSOR_ADMISSION = {'bytes': 11294, 'sha256': '3cef3dce573d992610387307947f6be5bcaa92c6e20d12bf6a294effc9ec7984'}
COPY_CAP = 384 * 1024
EVIDENCE_PINS = {
    'root_adoption': {'path': EVIDENCE + 'root_adoption.json', 'bytes': 8125,
                      'sha256': 'def0088f596d55a554fce6b7b744b2d05e2d92c0a930da0bb3f7585b3a9b5d97'},
    'prior_ordinary': {'path': EVIDENCE + 'prior_ordinary.json', 'bytes': 15712,
                       'sha256': '0c8f8af501d5c1e4c6b3baded8aa56f19608645ae1f3f3d8a67f093b8fc86f72'},
    'prefix_adoption': {'path': PREFIX + 'ROOT_COST_RECONCILIATION_ADOPTION.json', 'bytes': 875,
                        'sha256': '943e17c5407fbf91b1038eb7bae63ec891356119f96f790641e8f9912d7a9968'},
    'prefix_proposal': {'path': PREFIX + 'COST_RECONCILIATION.proposed.json', 'bytes': 22993,
                        'sha256': '72e7a103e4ca159c9d2403c9a18fdeb9b7a38e5a4b4d34ccc6b059e2a6c46199'},
    'prerequisite_result': {'path': EVIDENCE + 'prerequisite_result.json', 'bytes': 7448,
                            'sha256': '205fe028e79da3d6beba9b9c4cc427ce98c8f6381a2c5284ca4c8f215f397474'},
    'prerequisite_protocol': {'path': EVIDENCE + 'prerequisite_protocol.json', 'bytes': 4880,
                              'sha256': 'b5adf4c9913efac24ac4e526363a7bc9356b40ead592a3c89e5f61f992df2cfa'},
    'saved_review': {'path': EVIDENCE + 'saved_review.json', 'bytes': 6556,
                     'sha256': '49592ca86fa84ef2b98391520a9856a7b9d7f963d868c49d64c6b90d649a95c0'},
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def plain(path):
    path = Path(path).absolute()
    need('..' not in path.parts and all(not p.is_symlink() for p in (path, *path.parents))
         and not any(c in str(path) for c in '\0\r\n,'), 'Unlinked literal path')
    return path


def base(source_root=ROOT):
    """Load only the exact preserved standard-library publication constructor."""
    path = plain(source_root) / BASE_PATH
    fd = os.open(plain(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == BASE_PIN['bytes'], 'Exact predecessor constructor extent')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(BASE_PIN['bytes'] + 1)
        after, linked = os.fstat(fd), path.lstat()
        keys = ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
        need(pin(body) == BASE_PIN and all(getattr(before, k) == getattr(after, k) == getattr(linked, k)
             for k in keys), 'Stable exact predecessor constructor')
    finally:
        os.close(fd)
    module = types.ModuleType('_neural034_preserved_publication')
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


def authenticate_documents(documents):
    """Fixed seven roles; checksums precede any interpretation or output write."""
    need(type(documents) is dict and set(documents) == set(EVIDENCE_PINS), 'Exactly seven evidence roles')
    for role, expected in EVIDENCE_PINS.items():
        need(type(documents[role]) is bytes and pin(documents[role]) ==
             {k: expected[k] for k in ('bytes', 'sha256')}, 'Exact evidence checksum: ' + role)
    return documents


def evidence(b, locators):
    need(type(locators) is dict and set(locators) == set(EVIDENCE_PINS), 'Exactly seven external evidence locators')
    bodies = {}
    for role, expected in EVIDENCE_PINS.items():
        bodies[role] = b.read(plain(locators[role]), {k: expected[k] for k in ('bytes', 'sha256')})
    return authenticate_documents(bodies)


SUPPLEMENT_HELPER = '''
def finite_cost_supplement(source_pin):
    """One exact root-adopted prior+150; no currentness or execution grant."""
    adopted=pinned(FINITE_COST_PINS['root_adoption'])
    def exact_pin(value,role):
        expected=FINITE_COST_PINS[role]
        need(type(value)is dict and all(value.get(k)==expected[k] for k in('bytes','sha256')),'Exact adopted '+role+' identity')
    def amount(value,expected,label):
        need(type(value)in(int,float) and math.isfinite(value) and value==expected,label)
    def integer(value,expected,label):
        need(type(value)is int and value==expected,label)
    need(adopted.get('schema')=='neural034-root-finite-cost-supplement/v1' and adopted.get('decision')=='adopt_exact_prior_ordinary_plus_generated150_for_source_construction' and adopted.get('cost_family_id')=='astrocyte_source_family','Exact finite root cost decision')
    need(all(adopted.get(k)is False for k in('execution_authority','allocation_authority','historical_lifetime_complete','latest_family_confirmed_for_native_dispatch')),'No native authority/currentness/lifetime promotion')
    original=adopted['original_adopted_prefix']; declared_prior=adopted['prior_ordinary_receipt']; declared_new=adopted['new_typed_supplement']
    exact_pin(original['adoption'],'prefix_adoption');exact_pin(original['proposal'],'prefix_proposal')
    exact_pin(declared_prior,'prior_ordinary')
    for key,role in(('result','prerequisite_result'),('protocol','prerequisite_protocol'),('independent_saved_review','saved_review')):
        exact_pin(declared_new[key],role)
    need(FINITE_COST_PINS['prefix_adoption']==COST,'Original canonical prefix locator preserved')
    # Both calls run the unchanged original branches, including480/closure checks.
    prefix=known_cost(COST,source_pin)
    prior=known_cost(FINITE_COST_PINS['prior_ordinary'],source_pin)
    amount(prefix,BASELINE,'Original adopted baseline')
    amount(prior,prefix+480,'Exact prior ordinary allowance after original validation')
    amount(original['known_source_family_seconds'],prefix,'Adopted prefix amount')
    integer(declared_prior['charged_seconds'],480,'Declared original480 allowance')
    amount(declared_prior['known_seconds_before'],prefix,'Declared original before')
    amount(declared_prior['known_seconds_after'],prior,'Declared original after')
    result=pinned(FINITE_COST_PINS['prerequisite_result']);protocol=pinned(FINITE_COST_PINS['prerequisite_protocol']);review=pinned(FINITE_COST_PINS['saved_review'])
    run_id='neural034-scoped-runtime-prerequisite-01'
    need(declared_new['run_id']==protocol['run_id']==review['native_terminal']['id']==run_id,'One exact supplemental run; never a caller-selected prior')
    need(result['schema']=='neural034-runtime-prerequisite-result/v1' and result['status']=='two_generated_units_closed_pending_independent_review' and result['cost_family_id']=='astrocyte_source_family','Typed generated result, not an ordinary receipt')
    need(review['schema']=='neural034-generated-prerequisite-saved-proof/v1' and review['status']=='two_generated_units_saved_proof_verified_pending_root_scoped_decision','Exact successful saved review')
    need(protocol['schema']=='neural034-scoped-runtime-prerequisite/v1' and protocol['prior_costs_reset']is False,'Exact source-specific protocol')
    need(result['source_commit']==review['source_commit']==declared_new['source_commit']=='f778af151a1cf949619c079dd0fc408192aca123','Original prerequisite source identity')
    exact_pin(review['result'],'prerequisite_result');exact_pin(review['protocol'],'prerequisite_protocol')
    need(result['all_owned_absent']is True and result['controller_reaped']is True,'Supplement resources and controller closed')
    integer(result['controller_returncode'],0,'Successful controller exit')
    need(review['native_terminal']['status']=='succeeded','Native prerequisite terminal success')
    integer(review['native_terminal']['exit_code'],0,'Observed native zero exit')
    need(len(review['group_absence'])==2 and all(r['absence_verified']is True and type(r['signal'])is int and r['signal']==0 for r in review['group_absence']),'Independent two-group absence proof')
    need(not any(k in result for k in('error','recovery_error','finalization_error','recovery_or_receipt_error')) and 'error'not in review,'No hidden failed result/review')
    need(result['prior_costs_reset']is False and result['historical_lifetime_complete']is False and result['cumulative_family_seconds']is None and review['costs']['prior_costs_reset']is False and review['costs']['cumulative_family_seconds']is None,'No reset or invented complete lifetime total')
    for value in(result['charged_wall_allowance_seconds'],protocol['limits']['hard_wall_seconds'],review['costs']['stage_allowance_seconds'],declared_new['charged_wall_allowance_seconds'],adopted['additive_charged_wall_allowance_seconds']):
        integer(value,150,'Exact150 supplement once, never boolean or doubled charge')
    for document in(result,protocol,review):
        for key in('authentic_inputs','model_calls','scientific_scores'):
            integer(document[key],0,'Generated-only cost witness')
    amount(adopted['prior_known_charged_wall_allowance_seconds'],prior,'Adopted prior unchanged')
    total=prior+150
    amount(adopted['included_known_charged_wall_allowance_subtotal_seconds'],total,'Exact finite prior+150 subtotal')
    integer(adopted['next_full_ordinary_allowance_seconds'],SECONDS,'Next original480 allowance retained')
    amount(adopted['conditional_next_subtotal_seconds'],total+SECONDS,'Conditional next full480 subtotal')
    return total

'''


def admission_body(b, predecessor_body):
    """The original function body is unchanged after one exact-pin first branch."""
    need(pin(predecessor_body) == PREDECESSOR_ADMISSION, 'Exact predecessor admission')
    constants = '\nFINITE_COST_PINS=' + repr(EVIDENCE_PINS) + '\n' + SUPPLEMENT_HELPER
    return b.replace_once(predecessor_body, 'def known_cost(pin,source_pin):\n',
        constants + 'def known_cost(pin,source_pin):\n'
        "    if pin==FINITE_COST_PINS['root_adoption']:return finite_cost_supplement(source_pin)\n")


def successor(b, predecessor, documents):
    """Render in memory; no repeated native work or full-copy fixture required."""
    authenticate_documents(documents)
    need(pin(predecessor['SOURCE_MANIFEST.json']) == PREDECESSOR_MANIFEST
         and pin(predecessor[FREEZE]) == PREDECESSOR_FREEZE
         and pin(predecessor[ADMISSION]) == PREDECESSOR_ADMISSION, 'Exact immediate predecessor closure')
    files = dict(predecessor)
    for name in (ADMISSION, FREEZE, 'SOURCE_MANIFEST.json'):
        files[ARCHIVE + name] = predecessor[name]
    for role, body in documents.items():
        name = EVIDENCE_PINS[role]['path']
        need(name not in files, 'No evidence/source collision')
        files[name] = body
    files[ADMISSION] = admission_body(b, predecessor[ADMISSION])
    freeze = b.decode(predecessor[FREEZE])
    freeze['cost_supplement_predecessor_source_freeze'] = {'path': FREEZE, **PREDECESSOR_FREEZE}
    freeze['finite_cost_supplement'] = {'schema': 'neural034-exact-root-cost-adoption/v1',
        'adoption': EVIDENCE_PINS['root_adoption'], 'known_subtotal_seconds': 3309.932040249051,
        'historical_lifetime_complete': False, 'latest_native_family_confirmed': False}
    freeze['files'] = {name: pin(files[name]) for name in freeze['files']}
    freeze['files'].update({row['path']: pin(documents[role]) for role, row in EVIDENCE_PINS.items()})
    files[FREEZE] = b.encoded(freeze)
    old_manifest = b.decode(predecessor['SOURCE_MANIFEST.json'])
    manifest = {'schema': 'neural034-finite-cost-supplement-source/v1', 'task_id': 'NEURAL-034',
        'execution_authority': False, 'native_qualification': False,
        'predecessor_manifest': {'path': ARCHIVE + 'SOURCE_MANIFEST.json', **PREDECESSOR_MANIFEST},
        'predecessor_source_freeze': {'path': FREEZE, **PREDECESSOR_FREEZE},
        'historical_source_freeze': old_manifest['historical_source_freeze'],
        'cost_adoption': EVIDENCE_PINS['root_adoption'],
        'changed_predecessor_members': [ADMISSION, FREEZE],
        'files': {name: pin(body) for name, body in sorted(files.items()) if name != 'SOURCE_MANIFEST.json'}}
    need(1 <= len(manifest['files']) <= 64, 'Portable complete source roster bound')
    files['SOURCE_MANIFEST.json'] = b.encoded(manifest)
    need(sum(map(len, files.values())) <= COPY_CAP, 'Explicit successor source+metadata byte cap')
    receipt = {'schema': 'neural034-finite-cost-configuration/v1', 'execution_authority': False,
        'source_freeze': {'path': FREEZE, **pin(files[FREEZE])},
        'manifest': {'path': 'SOURCE_MANIFEST.json', **pin(files['SOURCE_MANIFEST.json'])},
        'prior_receipt': EVIDENCE_PINS['root_adoption'],
        'source_members': len(files), 'source_bytes': sum(map(len, files.values())),
        'source_byte_cap': COPY_CAP, 'known_subtotal_seconds': 3309.932040249051,
        'historical_lifetime_complete': False, 'latest_family_confirmed_for_native_dispatch': False,
        'authentic_input_bodies_copied': 0}
    return files, receipt


def source_pin(source_root):
    b = base(source_root)
    old = b.source_pin(source_root)
    return {'schema': 'neural034-finite-cost-predecessor/v1', 'constructor': BASE_PIN,
            'publication_predecessor': old, 'immediate_manifest': PREDECESSOR_MANIFEST,
            'immediate_source_freeze': PREDECESSOR_FREEZE, 'fixed_cost_evidence': EVIDENCE_PINS}


def render(source_root, evidence_sources):
    b = base(source_root)
    bodies, current, manifest = b._capture(source_root)
    predecessor = b._render(bodies, current, manifest)
    return successor(b, predecessor, evidence(b, evidence_sources))


def configure(source_root, destination, evidence_sources):
    root, destination = plain(source_root), plain(destination)
    need(root.is_dir() and destination.parent.is_dir() and not destination.exists()
         and root != destination and root not in destination.parents and destination not in root.parents,
         'Fresh separate private source workspace')
    files, receipt = render(root, evidence_sources)
    b = base(root)
    destination.mkdir(mode=0o700)
    for name, body in sorted(files.items()):
        target = destination / b.member(name)
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        b.publish(target, body)
    return receipt


def load(destination):
    """Authenticate all selected source/evidence; other operator files unselected."""
    b, destination = base(), plain(destination)
    need(destination.is_dir() and stat.S_IMODE(destination.stat().st_mode) == 0o700, 'Private configured source root')
    current_body = b.read(destination / b.ARCHIVE / 'CURRENT_SOURCE.json', b.CURRENT_PIN)
    manifest_body = b.read(destination / b.ARCHIVE / 'SOURCE_MANIFEST.json', b.MANIFEST_PIN)
    current = b._metadata(current_body, manifest_body)
    original = {name: b.read(destination / (b.ARCHIVE + name if name in b.CHANGED else name), expected)
                for name, expected in current['files'].items()}
    b._closure(original)
    predecessor = b._render(original, current_body, manifest_body)
    documents = evidence(b, {role: destination / row['path'] for role, row in EVIDENCE_PINS.items()})
    files, receipt = successor(b, predecessor, documents)
    for name, body in files.items():
        path = destination / name
        b.read(path, pin(body))
        need(stat.S_IMODE(path.stat().st_mode) == 0o444, 'Exact selected publication mode')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True)
    parser.add_argument('--evidence-locators', required=True)
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    b = base(args.source_root)
    locators = b.decode(b.read(args.evidence_locators, cap=16384))
    need(type(locators) is dict and set(locators) == set(EVIDENCE_PINS)
         and all(type(value) is str for value in locators.values()), 'Exact seven-role locator JSON')
    receipt = configure(args.source_root, args.destination, locators)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
