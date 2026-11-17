"""Real generated-file publication under077; no Docker or Provider instance."""
from pathlib import Path
import errno, hashlib, os, stat, sys, tempfile, time, unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
from vendor_transport import bounds

class PublicationModes(unittest.TestCase):
    def setUp(self):
        self.saved_umask=os.umask(0o077)
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name).resolve()
        self.private=self.root/'private';self.private.mkdir(mode=0o700)
        self.meter=bounds.Meter(65536,65536,time.monotonic()+10)
    def tearDown(self):
        self.temp.cleanup();os.umask(self.saved_umask)
    def test_public_request_and_policy_are_0444_before_fsync_under_077(self):
        real_sync=os.fsync;observed=[]
        def sync(fd):
            info=os.fstat(fd)
            if stat.S_ISREG(info.st_mode):observed.append(stat.S_IMODE(info.st_mode))
            return real_sync(fd)
        with patch.object(bounds.os,'fsync',side_effect=sync):
            for name,raw in (('REQUEST.json',b'{"request":"generated"}\n'),('POLICY.json',b'{"policy":"generated"}\n')):
                target=self.private/name
                result=bounds.publish(target,raw,self.meter,mode=0o444)
                self.assertEqual(result,{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
                self.assertEqual(target.read_bytes(),raw)
                self.assertEqual(stat.S_IMODE(target.stat().st_mode),0o444)
                bounds.native_readable(target.stat())
        self.assertEqual(observed,[0o444,0o444])
        self.assertEqual(stat.S_IMODE(self.private.stat().st_mode),0o700)
    def test_private_default_stays_0600_and_guard_refuses_65534(self):
        target=self.private/'PRIVATE.json'
        with patch.object(bounds.os,'fchmod',side_effect=AssertionError('private file must not be chmodded')):
            bounds.publish(target,b'private generated metadata',self.meter)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode),0o600)
        self.assertEqual(stat.S_IMODE(self.private.stat().st_mode),0o700)
        if os.getuid()!=65534 and os.getgid()!=65534:
            with self.assertRaisesRegex(ValueError,'container UID/GID65534'):bounds.native_readable(target.stat())
    def test_failed_public_fchmod_preserves_primary_and_removes_owned_output(self):
        target=self.private/'REQUEST.json'
        failure=PermissionError(errno.EPERM,'generated fchmod refusal')
        with patch.object(bounds.os,'fchmod',side_effect=failure):
            with self.assertRaises(PermissionError) as seen:bounds.publish(target,b'complete generated body',self.meter,mode=0o444)
        self.assertIs(seen.exception,failure)
        self.assertFalse(target.exists())
        self.assertEqual(stat.S_IMODE(self.private.stat().st_mode),0o700)
    def test_existing_unowned_file_is_never_chmodded_or_replaced(self):
        target=self.private/'REQUEST.json';target.write_bytes(b'preexisting')
        target.chmod(0o600)
        with patch.object(bounds.os,'fchmod',side_effect=AssertionError('unowned fd must not be chmodded')):
            with self.assertRaises(FileExistsError):bounds.publish(target,b'replacement',self.meter,mode=0o444)
        self.assertEqual(target.read_bytes(),b'preexisting')
        self.assertEqual(stat.S_IMODE(target.stat().st_mode),0o600)

if __name__=='__main__':unittest.main(verbosity=2)
