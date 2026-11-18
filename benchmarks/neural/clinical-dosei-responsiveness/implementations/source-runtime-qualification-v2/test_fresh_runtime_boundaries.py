"""Independent generated custody boundaries; no live adapters or real inputs."""
import copy
import hashlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
PINS = {
    'qualification_cases_v3.py': '47f0fc57df5a797cc049798bb82703cec3d72cfc847822671f933902dd6829d4',
    'fresh_runtime_state_v1.py': '42ac099c1222a0eda499bb7390ab73ac6ccbd03ac3be0a1a7baef4ce006928cb',
    'test_fresh_runtime_state_v1.py': '47c476b97825d84527e0338a42cc45987b3b4d9847a4f7685b2e6bbf3b81d8ef',
}
verified = {}
for filename, expected in PINS.items():
    data = (HERE / filename).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise AssertionError('source pin differs: ' + filename)
    verified[filename] = data
f = types.ModuleType('independent_fresh_runtime_fixture')
f.__file__ = str(HERE / 'test_fresh_runtime_state_v1.py')
sys.modules[f.__name__] = f
exec(compile(verified['test_fresh_runtime_state_v1.py'], f.__file__, 'exec'), f.__dict__)
a = f.adapter


class FreshRuntimeBoundaries(unittest.TestCase):
    def setUp(self):
        def forbidden(*args, **kwargs):
            raise AssertionError('live adapter or historical policy evaluation forbidden')
        for owner, name in ((f.probe.socket, 'socket'), (f.probe.socket, 'if_nameindex'),
                            (f.probe.os, 'open'), (f.probe.os, 'uname'),
                            (f.owned, 'OwnedProcess'), (f.network, 'evaluate')):
            guard = patch.object(owner, name, forbidden)
            guard.start()
            self.addCleanup(guard.stop)

    def test_coherent_command_order_and_inspected_identity_refuse(self):
        # Fixture rebuilds intent, spawn, original receipt and authority hashes.
        for ordinal, tail in ((2, ['container', 'rm', '--force']),
                              (6, ['container', 'inspect'])):
            item = f.Fixture()
            def edit(argv, tail=tail):
                argv[11:] = tail + [item.base.identity]
            item.command_edits[ordinal] = edit
            item.rebuild()
            with self.subTest(command_ordinal=ordinal), self.assertRaises(ValueError):
                item.derive()
        for ordinal in (2, 4, 5):
            item = f.Fixture()
            item.base.edit_inspection(ordinal, lambda value: value.__setitem__('Id', 'e' * 64))
            item.rebuild()
            with self.subTest(inspected_ordinal=ordinal), self.assertRaises(ValueError):
                item.derive()

    def test_effective_inspection_scalar_aliases_refuse(self):
        cases = ((2, 'HostConfig', 'MemorySwap', 536870912.0),
                 (4, 'HostConfig', 'NanoCpus', 1000000000.0),
                 (5, 'HostConfig', 'PidsLimit', 64.0),
                 (2, 'State', 'ExitCode', 0.0),
                 (4, 'State', 'Paused', 0),
                 (5, 'State', 'OOMKilled', 0))
        for ordinal, section, key, value in cases:
            item = f.Fixture()
            item.base.edit_inspection(ordinal, lambda body, s=section, k=key, v=value:
                                      body[s].__setitem__(k, v))
            item.rebuild()
            with self.subTest(ordinal=ordinal, field=key), self.assertRaises(ValueError):
                item.derive()

    def test_final_call_roster_order_uniqueness_and_caller_boundary(self):
        item = f.Fixture()
        provisional = item.derive()
        reordered = copy.deepcopy(item.close)
        reordered['calls'][1], reordered['calls'][2] = reordered['calls'][2], reordered['calls'][1]
        with self.assertRaises(ValueError):
            a.bind_context_close(provisional, a.canonical(reordered), expected_call_bindings=item.calls)
        duplicates = copy.deepcopy(item.calls)
        duplicates[3] = copy.deepcopy(duplicates[2])
        closed = copy.deepcopy(item.close)
        closed['calls'] = duplicates
        with self.assertRaises(ValueError):
            a.bind_context_close(provisional, a.canonical(closed), expected_call_bindings=duplicates)
        wrong_first = copy.deepcopy(item.calls)
        wrong_first[0] = a.binding(b'fictional wrong first runtime call')
        closed['calls'] = wrong_first
        with self.assertRaises(ValueError):
            a.bind_context_close(provisional, a.canonical(closed), expected_call_bindings=wrong_first)
        # The pure join cannot authenticate later call semantics: the trusted
        # driver must validate those calls before supplying their hashes.
        caller_asserted = [copy.deepcopy(item.calls[0])] + [
            a.binding(('fictional later caller assertion ' + str(i)).encode()) for i in range(3)]
        closed['calls'] = copy.deepcopy(caller_asserted)
        final = a.bind_context_close(provisional, a.canonical(closed), expected_call_bindings=caller_asserted)
        self.assertTrue(final['runtime_control_confirmed'])
        self.assertFalse(final['complete_six_control_qualification'])
        self.assertFalse(final['network_qualified'])
        self.assertTrue(provisional['context_closure_pending'])
        self.assertFalse(provisional['runtime_control_confirmed'])


if __name__ == '__main__':
    unittest.main()
