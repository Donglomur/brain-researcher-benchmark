#!/usr/bin/env python3
"""Actual central NEURAL035 route predicates with bounded RAM-only proposed metadata.

No WORK body, candidate, authentic data, native process or scientific scorer is
read or run. Only capture/enumeration seams are replaced; qualification is real.
"""
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import types
from unittest import mock

REPO = Path(__file__).resolve().parents[6]
LANE = 'authoring/delivery-20261105/common/remaining-builds-wave16/neural035-complete-program/registration'
TASK = 'NEURAL-035'
SOURCE_PINS = {'tools/neurobench_campaign_gate.py': (16326, '11723f00691ef58e7c96b29030c810c98969e0be8411ec48b5bbc56a7874f61d'), 'tools/neurobench_campaign.py': (26686, 'b17b4317427f83ce28ab7ea5a4fbc42b689870ef2a7144a7e094ecb0bef9e59e'), 'tools/neurobench_condition_campaign.py': (8300, 'e1c54c6fb9e577898e69d7d832d155131c13d82df3148ef1dcd42a35537d7e2f')}
READ_CAP = 1000000
FIXTURE_CAP = 131072
fixture_bytes = 0


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def encode(value):
    global fixture_bytes
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    fixture_bytes += len(raw)
    assert fixture_bytes <= FIXTURE_CAP
    return raw


class SourceCapture:
    def __init__(self):
        self.bytes = 0
        self.pins = {}

    def read(self, relative, cap, expected=None):
        q = Path(relative)
        assert not q.is_absolute() and '..' not in q.parts
        p = REPO / q
        assert p.is_file() and not p.is_symlink()
        n = p.stat().st_size
        assert 0 < n <= cap and self.bytes + n <= READ_CAP
        raw = p.read_bytes()
        self.bytes += len(raw)
        assert len(raw) == n
        actual = pin(raw)
        if expected is not None:
            assert (actual['bytes'], actual['sha256']) == expected, relative
        self.pins[relative] = actual
        return raw


def module(name, relative, raw, base=None):
    m = types.ModuleType(name)
    m.__file__ = str(REPO / relative)
    tree = ast.parse(raw, m.__file__)
    if base is not None:
        removed = [n for n in tree.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'base' for t in n.targets)]
        assert len(removed) == 1
        assert ast.dump(removed[0].value) == ast.dump(ast.parse('_base()', mode='eval').body)
        tree.body = [n for n in tree.body if n not in removed]
        m.base = base
    exec(compile(tree, m.__file__, 'exec'), m.__dict__)
    return m


def refusal(fn, expected):
    try:
        fn()
    except ValueError as error:
        assert str(error) == expected, (str(error), expected)
    else:
        raise AssertionError('Required refusal absent')


class PoisonPath:
    def __fspath__(self):
        raise AssertionError('Unqualified route inspected a candidate/output/review path')

    def __str__(self):
        raise AssertionError('Unqualified route stringified a candidate/output/review path')


def poison(*args, **kwargs):
    raise AssertionError('Unqualified route reached candidate/runtime-source parsing')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--proposal-manifest', required=True)
    p.add_argument('--alias', required=True)
    args = p.parse_args()
    proposal = Path(args.proposal_manifest)
    assert proposal.as_posix() == LANE + '/proposed/benchmarks/neuroscience/neural-035/manifest.json'
    assert proposal.name == 'manifest.json' and not proposal.is_absolute() and '..' not in proposal.parts
    assert args.alias == 'full14_peak_order'
    cap = SourceCapture()
    sources = {name: cap.read(name, n, (n, digest)) for name, (n, digest) in SOURCE_PINS.items()}
    gate = module('captured_gate', 'tools/neurobench_campaign_gate.py', sources['tools/neurobench_campaign_gate.py'])
    campaign = module('captured_campaign', 'tools/neurobench_campaign.py', sources['tools/neurobench_campaign.py'])
    condition = module('captured_condition', 'tools/neurobench_condition_campaign.py', sources['tools/neurobench_condition_campaign.py'], campaign)
    # Deliberately invented compact WORK/preference metadata, never a claim
    # about the installed registry or current real WORK. Root owns that rejoin.
    receipt={'schema':'root_reviewed_program_source_preference_v1','selected_source_interfaces':{}}
    receipt_raw=encode(receipt)
    pref={'path':LANE+'/RAM_ONLY_PREFERENCE.json',**pin(receipt_raw)}
    work={'latest_construction_state':{'latest_program_source_selection':pref}}
    work_raw=encode(work)
    doc_raw = cap.read(args.proposal_manifest, 131072)
    doc = json.loads(doc_raw)
    assert doc['id'] == TASK
    meta = doc['program_execution']
    assert meta['verification']['status'] != 'passed'
    assert doc['program_conditions'][args.alias] == 'default'
    preferred = meta['preferred_source_interface']
    assert preferred['path'] == LANE
    source_desc = preferred['source']
    assert source_desc['path'] == LANE + '/SOURCE_MANIFEST.json'
    source_raw = cap.read(source_desc['path'], 262144, (source_desc['bytes'], source_desc['sha256']))
    argv = meta['entrypoint']['argv']
    with mock.patch.object(Path, 'exists', return_value=False), mock.patch.object(Path, 'is_symlink', return_value=False), mock.patch.object(Path, 'is_dir', return_value=True):
        index = gate.python_launch(argv)
    wrapper = argv[index]
    assert wrapper == LANE + '/adapter.py'
    wrapper_pin = gate.source_wrapper_pin(json.loads(source_raw), 'adapter.py', wrapper)
    wrapper_raw = cap.read(wrapper, 131072, (wrapper_pin['bytes'], wrapper_pin['sha256']))
    assert meta['entrypoint']['sha256'] == wrapper_pin['sha256']
    registration_relative = proposal.relative_to(LANE + '/proposed').as_posix()
    registration_path = REPO / registration_relative
    calls = []

    def capture(path, limit, expected=None):
        key = Path(path).as_posix()
        assert key in overlay, 'Unexpected metadata/payload capture: ' + key
        raw = overlay[key]
        assert len(raw) <= limit
        if expected is not None:
            assert pin(raw) == expected
        calls.append(key)
        return raw

    overlay = {str(REPO / gate.WORK): work_raw, str(REPO / pref['path']): receipt_raw}
    gate.capture = capture
    original = gate.preferred_route(REPO, TASK, 'run', None, pin(work_raw)['sha256'], None)
    assert original['status'] == 'no_preferred_program_source_for_task'
    assert original['runtime_authorization'] is False and len(calls) == 2
    proposed_receipt = copy.deepcopy(receipt)
    proposed_receipt['selected_source_interfaces'][TASK] = {
        **preferred, 'execution_selected': False, 'runtime_qualified': False, 'scientific_qualification_added': False,
    }
    proposed_receipt_raw = encode(proposed_receipt)
    proposed_work = copy.deepcopy(work)
    proposed_work['latest_construction_state']['latest_program_source_selection'] = {'path': pref['path'], **pin(proposed_receipt_raw)}
    proposed_work_raw = encode(proposed_work)
    overlay = {
        str(REPO / gate.WORK): proposed_work_raw,
        str(REPO / pref['path']): proposed_receipt_raw,
        str(REPO / source_desc['path']): source_raw,
        str(registration_path): doc_raw,
        str(REPO / wrapper): wrapper_raw,
    }
    work_sha = pin(proposed_work_raw)['sha256']
    routes = []
    with mock.patch.object(Path, 'exists', return_value=False), mock.patch.object(Path, 'is_symlink', return_value=False), mock.patch.object(Path, 'is_dir', return_value=True):
        for alias in (None, args.alias):
            calls.clear()
            out = gate.preferred_route(REPO, TASK, 'run', alias, work_sha, (registration_path, doc))
            assert out['status'] == 'preferred_source_bound'
            assert out['runtime_authorization'] is False and out['existing_runtime_qualification_still_required'] is True
            assert out['wrapper'] == wrapper_pin and out['registered_argv'] == argv
            assert len(calls) == 5
            assert out['metadata_read_charge_bytes'] == sum(len(overlay[k]) + 1 for k in calls)
            routes.append({'condition': alias, 'status': out['status'], 'read_charge_bytes': out['metadata_read_charge_bytes']})
        absent = 'Preferred reviewed program interface: ' + LANE + '; central route is absent or stale. Register and independently qualify this exact interface; no launch.'
        refusal(lambda: gate.preferred_route(REPO, TASK, 'run', None, work_sha, None), absent)
        wrong = copy.deepcopy(doc)
        wrong['id'] = 'PAPER-INVENTED-WRONG-ID'
        refusal(lambda: gate.preferred_route(REPO, TASK, 'run', None, work_sha, (registration_path, wrong)), 'captured actual central registration')
        stale = copy.deepcopy(doc)
        stale['program_execution']['preferred_source_interface'] = {'path': LANE + '/stale', 'source': source_desc}
        overlay[str(registration_path)] = encode(stale)
        refusal(lambda: gate.preferred_route(REPO, TASK, 'run', args.alias, work_sha, (registration_path, stale)), absent)
        overlay[str(registration_path)] = doc_raw
    campaign.specifications = lambda repo: ({}, {TASK: {'id': TASK}})
    campaign.runtime_manifests = lambda repo: {TASK: (registration_path, doc)}
    campaign._program_entry = campaign._program_json = campaign._program_pin = poison
    candidate = PoisonPath()
    output = PoisonPath()
    review = PoisonPath()
    assert campaign.verified_program_runtime(registration_path, doc, REPO) is False
    chosen = condition.condition_document(doc, args.alias)
    assert chosen['program_execution'] == meta
    assert campaign.verified_program_runtime(registration_path, chosen, REPO) is False
    refusal(lambda: campaign.run_command(TASK, candidate, output, REPO, review=review, other_reserve_bytes=0),
            'Program runner has no separate passing qualification; score verification is insufficient')
    refusal(lambda: condition.run_command(TASK, args.alias, candidate, output, REPO, review=review, other_reserve_bytes=0),
            'Selected condition has no separate passing qualification')
    refusal(lambda: condition.run_command(TASK, 'invented_unknown', candidate, output, REPO, review=review, other_reserve_bytes=0),
            'Unknown program condition for ' + TASK + ': invented_unknown')
    assert json.loads(receipt_raw) == receipt and json.loads(work_raw) == work
    assert len(proposed_receipt['selected_source_interfaces']) == 1
    print(json.dumps({'status': 'PASS_SOURCE_RAM_ONLY', 'groups': 8, 'routes': routes, 'source_read_bytes': cap.bytes,
        'source_pins': cap.pins, 'invented_metadata_encoded_bytes': fixture_bytes,
        'RAM_fixture_conservative_reserve_bytes': 131072, 'disk_fixture_bytes': 0,
        'authentic_bodies_native_candidate_scoring_calls': 0,
        'baseline_preference_members': len(receipt['selected_source_interfaces']), 'RAM_proposed_preference_members': len(proposed_receipt['selected_source_interfaces']),
        'canonical_count_not_recomputed': True, 'registry_count_not_inferred': True, 'real_WORK_read': False,
        'scope': 'Actual central predicates on fully invented compact WORK/preference plus exact source-bound proposed metadata; no claim about installed state, no installation or qualification.'}, sort_keys=True))


if __name__ == '__main__':
    main()
