"""Generated admission, cumulative I/O and partial-output controls only."""
import copy
import hashlib
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from _generated_support import guards as g


class GuardTests(unittest.TestCase):
    def test_cumulative_read_and_unknown_grant_not_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'input'; path.write_bytes(b'abcdefgh')
            fd = os.open(path, os.O_RDONLY)
            try:
                meter = g.ReadMeter(10)
                self.assertEqual(meter.read(fd, 4), b'abcd')
                with patch.object(g.os, 'read', side_effect=InterruptedError('generated interruption')):
                    with self.assertRaises(InterruptedError): meter.read(fd, 5)
                self.assertEqual((meter.charged, meter.known), (9, 4))
                with self.assertRaises(ValueError): meter.read(fd, 2)
            finally: os.close(fd)

    def test_bounded_regular_read_and_symlink_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve()/'input'; path.write_bytes(b'abc')
            meter = g.ReadMeter(32)
            self.assertEqual(g.read_regular(path, 3, meter), b'abc')
            self.assertEqual(meter.known, 3)
            with self.assertRaises(ValueError): g.read_regular(path, 2, meter)
            link = Path(directory).resolve()/'link'; link.symlink_to(path)
            with self.assertRaises(OSError): g.read_regular(link, 3, meter)

    def test_archive_read_seek_identity_and_unbounded_read_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve()/'input'; path.write_bytes(b'abcdefgh')
            meter = g.ReadMeter(32)
            with g.MeteredArchive(path, g.signature(path.stat()), meter) as stream:
                self.assertEqual(stream.read(3), b'abc')
                stream.seek(1)
                target = bytearray(4)
                self.assertEqual(stream.readinto(target), 4)
                self.assertEqual(target, b'bcde')
                self.assertEqual(meter.known, 7)
                with self.assertRaises(ValueError): stream.read(1048577)

    def test_standard_zip_tail_reads_are_bounded_and_metered(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve()/'generated.zip'
            with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED) as archive:
                archive.writestr('fixture.txt', b'a' * 70000)
            meter = g.ReadMeter(300000)
            with g.MeteredArchive(path, g.signature(path.stat()), meter) as source:
                with self.assertRaises(ValueError): source.read()
                with zipfile.ZipFile(source) as archive:
                    with archive.open('fixture.txt') as member:
                        self.assertEqual(member.read(), b'a' * 70000)
            self.assertGreater(meter.known, 70000)

    def test_writer_success_binding_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            budget = g.OutputBudget(directory)
            writer = budget.writer('recording-1.eeg.provisional', 3, binary=True)
            self.assertEqual(writer.write(b'abc'), 3)
            with self.assertRaises(ValueError): writer.binding()
            writer.close()
            binding = writer.binding()
            self.assertEqual(binding['bytes'], 3)
            self.assertEqual(binding['sha256'], hashlib.sha256(b'abc').hexdigest())
            self.assertEqual((budget.charged, budget.known), (3, 3))
            with self.assertRaises(FileExistsError): budget.writer('recording-1.eeg.provisional', 3, binary=True)
            with self.assertRaises(ValueError): budget.writer('../escape', 3)

    def test_short_write_preserved_and_not_a_complete_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            budget = g.OutputBudget(directory)
            writer = budget.writer('partial', 10)
            real_write = os.write
            with patch.object(g.os, 'write', side_effect=lambda fd, raw: real_write(fd, raw[:3])):
                self.assertEqual(writer.write(b'abcdef'), 3)
            writer.close()
            self.assertEqual(writer.path.read_bytes(), b'abc')
            self.assertEqual((budget.charged, budget.known, budget.metadata_charged), (6, 3, 6))
            with self.assertRaises(ValueError): writer.binding()

    def test_global_and_sidecar_caps_reserve_failure_room(self):
        with tempfile.TemporaryDirectory() as directory:
            budget = g.OutputBudget(directory)
            budget.charged = budget.total - g.FINAL_RESERVE
            with self.assertRaises(ValueError): budget.charge(1, binary=True, critical=False)
            budget.charge(1, binary=True, critical=True)
            budget.charged = 0
            budget.metadata_charged = budget.metadata - g.METADATA_FINAL_RESERVE
            with self.assertRaises(ValueError): budget.charge(1, binary=False, critical=False)
            budget.charge(1, binary=False, critical=True)

    def test_exact_native_authority_parent_pid_and_integer_scope(self):
        args = SimpleNamespace(protocol=Path('/generated/protocol.json'), protocol_sha256='a'*64,
                               approval_id='generated-admission', native_run_id='generated-run')
        protocol = {'python_executable':'/generated/python', 'producer_path':'/generated/producer.py'}
        binding = {'path':str(args.protocol), 'sha256':args.protocol_sha256}
        command = [protocol['python_executable'],'-I','-S','-B',protocol['producer_path'],
                   '--protocol',str(args.protocol),'--protocol-sha256',args.protocol_sha256,
                   '--approval-id',args.approval_id,'--native-run-id',args.native_run_id]
        ledger = {'approved_native_protocols':[{'id':args.approval_id,'owner':g.OWNER,'approved_by':'/root','protocol':binding}],
                  'reservations':[{'id':g.RESERVATION,'owner':g.OWNER,'kind':'artifact','status':'active',
                                   'reserved_bytes':g.LIMITS['output_bytes'],'destination':str(g.OUTPUT)}],
                  'native_runs':[{'id':args.native_run_id,'owner':g.OWNER,'status':'running','protocol':binding,
                                  'approval_id':args.approval_id,'command':command,'coordinator_pid':10,'child_pid':20,
                                  'requested_threads':1,'declared_max_working_ram_bytes':g.LIMITS['declared_ram_bytes']}]}
        self.assertTrue(g.validate_authority(ledger,args,protocol,pid=20,parent_pid=10))
        for key, value in (('child_pid',21),('coordinator_pid',11),('requested_threads',True),('status','succeeded')):
            changed = copy.deepcopy(ledger); changed['native_runs'][0][key] = value
            with self.assertRaises(ValueError): g.validate_authority(changed,args,protocol,pid=20,parent_pid=10)
        changed = copy.deepcopy(ledger); changed['native_runs'][0]['child_pid'] = None
        self.assertFalse(g.validate_authority(changed,args,protocol,pid=20,parent_pid=10,permit_pending=True))

    def test_unique_json_and_bounded_escaped_encoding(self):
        with self.assertRaises(ValueError): g.unique_json(b'{"a":1,"a":2}')
        with self.assertRaises(ValueError): g.unique_json(b'{"a":NaN}')
        with self.assertRaises(ValueError): g.encode({'value':'\u2603'*20}, 32)
        self.assertEqual(g.encode({'a':1}, 20), b'{"a":1}\n')


if __name__ == '__main__':
    unittest.main()
