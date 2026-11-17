#!/usr/bin/env python3
"""Invented source controls only: no released SWCs, private answers or Docker.

The mock transport proves ordering in boundary.py, not container isolation.
Invented scalar tables exercise the unchanged scorer and are not science data.
"""
import base64
import copy
import csv
import datetime as dt
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
for name in ('common', 'durable_evidence', 'schema', 'bundle', 'numeric_score', 'docker_owner', 'boundary', 'bridge'):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod
    spec.loader.exec_module(mod)
import common as C
import schema as S
import bundle
import numeric_score as N
import docker_owner as D
import boundary as B
import bridge


def invented_files(*, branch_error=0, caliber_error=0, omit_last=False):
    """Arbitrary identical unit values; no source-derived geometry or answers."""
    output = {}
    for name, spec in S.TABLES.items():
        stream = io.StringIO(newline='')
        writer = csv.DictWriter(stream, spec['columns']); writer.writeheader()
        for cell in S.CELLS[:-1] if omit_last else S.CELLS:
            row = {k: '1' for k in spec['columns']}
            row['cell_id'] = cell
            if name == 'cells.csv': row['species'] = 'mouse' if cell.startswith('Mse') else 'human'
            if name == 'branches.csv':
                row['length_um'] = str(1 + branch_error)
                row['mean_edge_diameter_um'] = str(1 + caliber_error)
            writer.writerow(row)
        output[name] = stream.getvalue().encode()
    output['summary.json'] = b'{"invented_unit_control":1}\n'
    return output


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='purkinje-invented-')).resolve()
        self.budget = C.Budget(time.monotonic() + 20, 8 * 1024 ** 2, 8 * 1024 ** 2)

    def tearDown(self):
        for p in self.tmp.rglob('*'):
            if p.is_dir() and not p.is_symlink(): p.chmod(0o700)
        shutil.rmtree(self.tmp)

    def write(self, name, body):
        path = self.tmp / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return {'path': str(path), **C.pin(body)}

    def json(self, name, value):
        return self.write(name, C.encode(value))

    def admit_fixture(self):
        zero = '0' * 64
        inputs = {'TASK.md': self.write('input-source/task', b'invented input')}
        refs = {name: self.write('refs/' + name, body) for name, body in invented_files().items()}
        pins = {role: {k: {p: e[p] for p in ('bytes', 'sha256')} for k, e in rows.items()}
                for role, rows in (('public_inputs', inputs), ('references', refs))}
        runtime = {'image': B.IMAGE, 'docker': str(self.tmp / 'docker'), 'docker_physical': [1] * 7,
                   'daemon_socket': str(self.tmp / 'socket'), 'daemon_guard': {}}
        source = {'status': 'passed', 'task_id': B.ID, 'source_lock_sha256': zero,
                  'independent_whole_source': True, 'public_leak_review': True, 'findings': []}
        native = {'status': 'passed', 'task_id': B.ID, 'image': B.IMAGE, 'source_lock_sha256': zero,
                  'runtime': runtime, 'profile': 'purkinje-portable-program-v1',
                  'candidate_boundary_verified': True, 'findings': []}
        cap = {'schema': 'purkinje-root-admitted-capacity/v1',
               'observed_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'normal_pressure': True,
               'available_bytes': 8 * 1024 ** 3, 'host_reserved_bytes': 512 * 1024 ** 2,
               'VM_reserved_bytes': 3 * 1024 ** 3, 'other_reserved_bytes': 0, 'margin_bytes': 1024 ** 3,
               'swap_growth_bytes': 0, 'pageout_growth_bytes': 0, 'complete_roster': True,
               'free_disk_bytes': 100 * 1024 ** 3,
               'evidence_pins': [self.write('invented-observer', b'invented; no dispatch authority')]}
        history = {'schema': 'purkinje-root-admitted-history/v1', 'task_id': B.ID, 'closed': True,
                   'known_charged_seconds': 1167.2520854590086, 'consumed_attempt_ids': []}
        request = {'schema': 'purkinje-portable-program-request/v1', 'task_id': B.ID,
                   'selected': True, 'attempt_id': 'invented-only', 'source_lock_sha256': zero,
                   'program': self.write('candidate.py', b'raise RuntimeError("invented only")\n'),
                   'public_inputs': inputs, 'references': refs, 'runtime': runtime,
                   'reviews': {'source': self.json('review-source', source), 'runtime': self.json('review-native', native)},
                   'capacity': self.json('capacity', cap), 'history': self.json('history', history),
                   'output_root': str(self.tmp / 'future-output')}
        return request, pins, cap, history, source, native

    def admit(self, request, pins):
        # Fabricated capacity is confined to this source control, never production.
        with patch.object(B.shutil, 'disk_usage', return_value=shutil._ntuple_diskusage(2**40, 0, 2**40)):
            return B.admit(request, pins, '0' * 64, self.budget)


class EnvelopeControls(Base):
    def test_roundtrip_all_required(self):
        self.assertEqual(bundle.decode(bundle.encode(invented_files())), invented_files())

    def test_optional_prose_is_opaque(self):
        files = invented_files(); files['interpretation.json'] = b'not JSON; unscored'
        self.assertEqual(bundle.decode(bundle.encode(files)), files)

    def test_missing_file_rejected(self):
        files = invented_files(); del files['branches.csv']
        with self.assertRaises(ValueError): bundle.encode(files)

    def test_extra_file_rejected(self):
        files = invented_files(); files['private-reference.csv'] = b'x'
        with self.assertRaises(ValueError): bundle.encode(files)

    def test_hash_tamper_rejected(self):
        body = json.loads(bundle.encode(invented_files())); body['files']['cells.csv']['sha256'] = '0' * 64
        with self.assertRaises(ValueError): bundle.decode(C.encode(body))

    def test_declared_size_tamper_rejected(self):
        body = json.loads(bundle.encode(invented_files())); body['files']['cells.csv']['bytes'] += 1
        with self.assertRaises(ValueError): bundle.decode(C.encode(body))

    def test_duplicate_wire_key_rejected(self):
        with self.assertRaises(ValueError): bundle.decode(b'{"schema":1,"schema":2,"files":{}}')

    def test_nonfinite_wire_rejected(self):
        with self.assertRaises(ValueError): bundle.decode(b'{"schema":NaN,"files":{}}')

    def test_per_file_cap_rejected(self):
        files = invented_files(); files['summary.json'] = b'x' * (S.CAPS['summary.json'] + 1)
        with self.assertRaises(ValueError): bundle.encode(files)


class ScorerControls(Base):
    def test_exact_invented_values_score_zero(self):
        result = N.grade(invented_files(), invented_files)
        self.assertEqual(result['comparison']['metrics']['primary_equal_cell_branch_length_rmse_um'], 0)
        self.assertEqual(result['private_numeric_reference_loads'], 1)
        self.assertFalse(result['full_paper_reproduction'])

    def test_known_native_unit_branch_error(self):
        result = N.grade(invented_files(branch_error=2), invented_files)
        self.assertEqual(result['comparison']['metrics']['primary_equal_cell_branch_length_rmse_um'], 2)

    def test_wrong_caliber_not_hidden_by_primary(self):
        result = N.grade(invented_files(caliber_error=3), invented_files)['comparison']['metrics']
        self.assertEqual(result['primary_equal_cell_branch_length_rmse_um'], 0)
        self.assertEqual(result['tables']['branches.csv']['fields']['mean_edge_diameter_um']['equal_cell_rmse'], 3)

    def test_missing_cell_cannot_be_subset_score(self):
        result = N.grade(invented_files(omit_last=True), invented_files)
        self.assertEqual(result['status'], 'incomplete_numerical_coverage')
        self.assertIsNone(result['comparison']['metrics'])
        self.assertTrue(result['comparison']['no_matched_subset_score'])

    def test_invalid_candidate_does_not_load_reference(self):
        def forbidden(): self.fail('Private loader touched for invalid files')
        result = N.grade({'summary.json': b'{}'}, forbidden)
        self.assertEqual(result['private_numeric_reference_loads'], 0)

    def test_optional_prose_changes_no_metric(self):
        files = invented_files(); files['interpretation.json'] = b'wrong prose'
        self.assertEqual(N.grade(files, invented_files), N.grade(invented_files(), invented_files))


class BridgeControls(Base):
    def create_files(self):
        root = self.tmp / 'output'; root.mkdir()
        for name, body in invented_files().items(): (root / name).write_bytes(body)
        return root

    def test_capture_invented_files(self):
        self.assertEqual(bridge.capture_files(self.create_files()), invented_files())

    def test_symlink_output_rejected(self):
        root = self.create_files(); p = root / 'summary.json'; p.unlink(); p.symlink_to(self.tmp / 'other')
        (self.tmp / 'other').write_bytes(b'{}')
        with self.assertRaises((ValueError, OSError)): bridge.capture_files(root)

    def test_hardlink_output_rejected(self):
        root = self.create_files(); os.link(root / 'summary.json', self.tmp / 'alias')
        with self.assertRaises(ValueError): bridge.capture_files(root)

    def test_directory_output_rejected(self):
        root = self.create_files(); (root / 'summary.json').unlink(); (root / 'summary.json').mkdir()
        with self.assertRaises((ValueError, OSError)): bridge.capture_files(root)

    def test_extra_file_capture_rejected(self):
        root = self.create_files(); (root / 'extra').write_bytes(b'x')
        with self.assertRaises(ValueError): bridge.capture_files(root)

    def test_fixed_sixty_second_contract(self):
        with self.assertRaises(ValueError):
            bridge.execute_program(b'pass', self.tmp, self.tmp / 'new', self.tmp, seconds=1)

    def test_original_input_output_argument_names(self):
        files = invented_files()
        program = ('import argparse\nfrom pathlib import Path\np=argparse.ArgumentParser()\n'
                   'p.add_argument("--input");p.add_argument("--out");a=p.parse_args()\n'
                   'assert Path(a.input).is_dir()\n'
                   'for name,body in ' + repr(files) + '.items(): (Path(a.out)/name).write_bytes(body)\n').encode()
        got = bridge.execute_program(program, self.tmp, self.tmp / 'new-output', self.tmp)
        self.assertEqual(got, files)

    def test_nonzero_candidate_cannot_produce_success(self):
        with self.assertRaisesRegex(ValueError, 'candidate_nonzero'):
            bridge.execute_program(b'raise SystemExit(7)', self.tmp, self.tmp / 'new-output', self.tmp)

    def test_candidate_stdout_bound(self):
        with self.assertRaisesRegex(ValueError, 'candidate_log_limit'):
            bridge.execute_program(b'import sys\nsys.stdout.write("x" * 70000)', self.tmp, self.tmp / 'new-output', self.tmp)


class AdmissionControls(Base):
    def test_invented_complete_binding_passes_only_admission(self):
        req, pins, *_ = self.admit_fixture()
        self.admit(req, pins)
        self.assertFalse(Path(req['output_root']).exists())

    def test_unselected_template_refused(self):
        req, pins, *_ = self.admit_fixture(); req['selected'] = False
        with self.assertRaises(ValueError): self.admit(req, pins)

    def test_changed_public_asset_pin_refused(self):
        req, pins, *_ = self.admit_fixture(); req['public_inputs']['TASK.md']['sha256'] = '1' * 64
        with self.assertRaises(ValueError): self.admit(req, pins)

    def test_omitted_reference_refused(self):
        req, pins, *_ = self.admit_fixture(); del req['references']['branches.csv']
        with self.assertRaises(ValueError): self.admit(req, pins)

    def test_stale_capacity_refused(self):
        req, pins, cap, *_ = self.admit_fixture()
        cap['observed_utc'] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=90)).isoformat()
        req['capacity'] = self.json('capacity-stale', cap)
        with self.assertRaises(ValueError): self.admit(req, pins)

    def test_inadequate_memory_refused(self):
        req, pins, cap, *_ = self.admit_fixture(); cap['available_bytes'] = 1
        req['capacity'] = self.json('capacity-inadequate', cap)
        with self.assertRaises(ValueError): self.admit(req, pins)

    def test_live_pressure_refused(self):
        req, pins, cap, *_ = self.admit_fixture(); cap['swap_growth_bytes'] = 1
        req['capacity'] = self.json('capacity-pressure', cap)
        with self.assertRaises(ValueError): self.admit(req, pins)

    def test_consumed_attempt_refused(self):
        req, pins, cap, history, *_ = self.admit_fixture(); history['consumed_attempt_ids'] = [req['attempt_id']]
        req['history'] = self.json('history-consumed', history)
        with self.assertRaises(ValueError): self.admit(req, pins)

    def test_native_qualification_for_other_source_refused(self):
        req, pins, cap, history, source, native = self.admit_fixture(); native['source_lock_sha256'] = '1' * 64
        req['reviews']['runtime'] = self.json('native-other', native)
        with self.assertRaises(ValueError): self.admit(req, pins)

    def test_native_qualification_for_other_runtime_refused(self):
        req, pins, cap, history, source, native = self.admit_fixture()
        native['runtime'] = {**req['runtime'], 'docker_physical': [2] * 7}
        req['reviews']['runtime'] = self.json('native-other', native)
        with self.assertRaises(ValueError): self.admit(req, pins)

    def test_source_without_leak_review_refused(self):
        req, pins, cap, history, source, native = self.admit_fixture(); source['public_leak_review'] = False
        req['reviews']['source'] = self.json('source-unreviewed', source)
        with self.assertRaises(ValueError): self.admit(req, pins)

    def test_output_clobber_refused(self):
        req, pins, *_ = self.admit_fixture(); Path(req['output_root']).mkdir()
        with self.assertRaises(ValueError): self.admit(req, pins)


class BoundaryControls(Base):
    def exercise(self, *, bad_wire=False, unclosed=False):
        req, pins, *_ = self.admit_fixture()
        root = self.tmp / 'run'; root.mkdir()
        package = {name: (HERE / name).read_bytes() for name in ('bridge.py', 'TASK.md', 'SCHEMA.json')}
        docker = self.tmp / 'docker'; docker.write_bytes(b'invented executable; never run'); docker.chmod(0o500)
        req['runtime']['docker_physical'] = list(C.signature(docker.lstat()))
        events = []; real_read = C.read
        def read(path, expected, budget, **kwargs):
            if str(path).startswith(str(self.tmp / 'refs') + '/'):
                self.assertTrue((root / 'CANDIDATE_CLOSED_COMMIT.json').is_file())
                self.assertTrue((root / 'OUTPUT_FILES_COMMIT.json').is_file())
                self.assertIn('closed', events); events.append('private')
            elif str(path) == req['public_inputs']['TASK.md']['path']:
                self.assertTrue((root / 'PROGRAM_COMMIT.json').is_file()); events.append('public')
            return real_read(path, expected, budget, **kwargs)
        def mocked_candidate(**kwargs):
            self.assertEqual(set(kwargs), {'root', 'input_dir', 'task_dir', 'program', 'budget', 'active_deadline'})
            self.assertNotIn(str(self.tmp / 'refs'), kwargs['program'].read_text())
            events.append('closed')
            if unclosed: return {'candidate_closed': True}
            artifact = self.write('closed-wire', b'{}' if bad_wire else bundle.encode(invented_files()))
            return D.ClosedRun(artifact, {'invented_transport': True}, D._CLOSED_TOKEN)
        with patch.object(D, 'configure_cli', return_value={'invented_transport': True}), \
             patch.object(D, 'run_candidate', side_effect=mocked_candidate), \
             patch.object(C, 'read', side_effect=read):
            result = B.execute(req, package, D, self.budget, root, time.monotonic() + 10)
        return result, events

    def test_program_commit_precedes_payload_and_private_follows_closure(self):
        result, events = self.exercise()
        self.assertEqual(result['status'], 'scored')
        self.assertLess(events.index('public'), events.index('closed'))
        self.assertEqual(events.count('private'), 5)

    def test_invalid_closed_wire_never_loads_reference(self):
        result, events = self.exercise(bad_wire=True)
        self.assertEqual(result['status'], 'invalid_submission'); self.assertNotIn('private', events)

    def test_self_reported_closure_rejected(self):
        with self.assertRaisesRegex(ValueError, 'owned_closed_failed_candidate_required'):
            self.exercise(unclosed=True)

    def test_forged_closed_token_rejected(self):
        with self.assertRaisesRegex(ValueError, 'owned_closed_candidate_required'):
            D.require_closed(D.ClosedRun({}, {}, object()))


class ProfileControls(Base):
    def test_original_profile_and_no_private_mount(self):
        argv = D.create_argv('invented-owner', self.tmp / 'input', self.tmp / 'task', self.tmp / 'program')
        for item in ('--network=none', '--read-only', '--cpus=1.75', '--memory=3g', '--memory-swap=3g',
                     '--pids-limit=64', '--cap-drop=ALL', '--security-opt=no-new-privileges', '--pull=never',
                     '--tmpfs=/work:rw,noexec,nosuid,nodev,size=8388608,nr_inodes=32,mode=1777',
                     '--ulimit=cpu=105:106', '--ulimit=core=0:0'):
            self.assertIn(item, argv)
        self.assertEqual(argv.count('--mount'), 3)
        self.assertEqual(argv[-4:], [B.IMAGE, '-I', '-B', '/candidate/solution.py'])
        self.assertTrue(all('readonly' in argv[i + 1] for i, x in enumerate(argv) if x == '--mount'))
        self.assertEqual(bridge.CAPS, S.CAPS); self.assertEqual(bridge.TOTAL, S.TOTAL_CAP)

    def test_other_image_refused(self):
        with self.assertRaises(ValueError):
            D.create_argv('invented', self.tmp, self.tmp, self.tmp, image='sha256:' + '0' * 64)

    def test_alias_mount_refused(self):
        alias = self.tmp / 'alias'; alias.symlink_to(self.tmp / 'actual')
        with self.assertRaises(ValueError): D.create_argv('invented', alias, self.tmp, self.tmp)

    def test_mount_option_injection_refused(self):
        with self.assertRaisesRegex(ValueError, 'safe_mount_encoding'):
            D.create_argv('invented', self.tmp / 'bad,dst=/secret', self.tmp, self.tmp)


if __name__ == '__main__':
    unittest.main(verbosity=2)
