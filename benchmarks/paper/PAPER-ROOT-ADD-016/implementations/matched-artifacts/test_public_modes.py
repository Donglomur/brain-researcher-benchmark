"""Generated publication controls; no authentic operands or container execution."""
import copy
import importlib.util
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('cardiac_public_modes', HERE / 'paired.py')
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)


class PublicModes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cardiac-public-modes-')
        self.root = Path(self.temp.name).resolve()
        self.operands = self.root / 'operands'
        self.operands.mkdir(mode=0o700)
        self.previous_umask = os.umask(0o077)
        self.addCleanup(os.umask, self.previous_umask)
        data = self.asset('data.csv', b'invented,signal\n1,2\n')
        source = P.decode((HERE / 'PACKET_SPEC.json').read_bytes())
        source['common'] = {'data.csv': data, 'paper.txt': self.asset('paper.txt', b'invented paper\n')}
        source['B_only'] = {'official/code.txt': self.asset('code.txt', b'# invented source\n')}
        source['scope']['input_sha256'] = data['sha256']
        source['reference'] = self.asset('private/reference.json', b'private invented target; never read by build\n')
        self.packet = P.Packet(source, P.REPOSITORY, HERE, self.operands)

    def tearDown(self):
        for parent, _, _ in os.walk(self.root):
            os.chmod(parent, 0o700)
        self.temp.cleanup()

    def asset(self, name, body):
        path = self.operands / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        P.write(path, body)
        return {'root': 'operands', 'path': name, **P.pin(body)}

    def test_restrictive_umask_publishes_only_owned_packet_members(self):
        target = self.operands / 'private/reference.json'
        before = target.read_bytes()
        original_stream = P.F.stream

        def public_stream(path, cap):
            self.assertNotEqual(Path(path), target, 'Build must not open the private target')
            return original_stream(path, cap)

        output = self.root / 'pair'
        with patch.object(P.F, 'stream', side_effect=public_stream):
            self.packet.build(output)
        for condition in ('A', 'B'):
            for name, descriptor in self.packet.members(condition).items():
                member = output / condition / name
                self.assertEqual(stat.S_IMODE(member.stat().st_mode), 0o444, name)
                self.assertEqual(P.pin(member.read_bytes()),
                                 {k: descriptor[k] for k in ('bytes', 'sha256')})
                self.assertEqual(member.stat().st_nlink, 1)
            for directory, _, _ in os.walk(output / condition):
                self.assertEqual(stat.S_IMODE(Path(directory).stat().st_mode), 0o500)
            # Host-only requests keep their pre-existing restrictive publication policy.
            self.assertEqual(stat.S_IMODE((output / (condition + '.request.json')).stat().st_mode), 0o400)
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((output / 'receipt.json').stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(target.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(self.packet.pair(output), self.packet.receipt(self.packet.pair(output)['pair_id']))

    def test_bad_source_digest_never_publishes_public_permissions(self):
        descriptor = copy.deepcopy(self.packet.members('A')['data.csv'])
        descriptor['sha256'] = '0' * 64
        destination = self.root / 'bad-copy'
        with patch.object(P.os, 'fchmod', wraps=os.fchmod) as publication:
            with self.assertRaisesRegex(ValueError, 'Exact complete copied source'):
                self.packet.copy(descriptor, destination)
        publication.assert_not_called()
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o400)
        self.assertFalse((self.root / 'receipt.json').exists())

    def test_existing_and_symlink_destinations_remain_untouched(self):
        descriptor = self.packet.members('A')['data.csv']
        target = self.root / 'existing'
        P.write(target, b'private pre-existing contents\n')
        symlink = self.root / 'symlink'
        symlink.symlink_to(target)
        for destination in (target, symlink):
            with self.subTest(destination=destination.name):
                with self.assertRaises(FileExistsError):
                    self.packet.copy(descriptor, destination)
                self.assertEqual(target.read_bytes(), b'private pre-existing contents\n')
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertTrue(symlink.is_symlink())


if __name__ == '__main__':
    unittest.main(verbosity=2)
