"""Exercise the public CLI against timestamp-valid unselected cached modules."""
import hashlib
import importlib.util
import json
import marshal
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile


def main():
    source = Path(__file__).resolve().parent
    manifest_raw = (source/'SOURCE_MANIFEST.json').read_bytes()
    manifest = json.loads(manifest_raw)
    with tempfile.TemporaryDirectory(prefix='neural029-cache-regression-') as temp:
        root = Path(temp).resolve()/'package'; root.mkdir()
        for name in [*manifest['files'], 'SOURCE_MANIFEST.json']:
            shutil.copyfile(source/name, root/name)
        for name in ('io_utils', 'executor'):
            original = root/(name+'.py'); info = original.stat()
            compiled = compile("raise RuntimeError('UNAUTHENTICATED_CACHE_EXECUTED')", str(original), 'exec')
            raw = importlib.util.MAGIC_NUMBER + struct.pack('<III', 0, int(info.st_mtime), info.st_size) + marshal.dumps(compiled)
            cached = Path(importlib.util.cache_from_source(str(original)))
            cached.parent.mkdir(exist_ok=True); cached.write_bytes(raw)
        (root/'signal.py').write_text("raise RuntimeError('UNAUTHENTICATED_SHADOW_EXECUTED')\n")
        request = Path(temp).resolve()/'invalid-request.json'; request.write_text('{"schema":"invalid"}')
        command = [sys.executable, '-I', '-B', str(root/'run.py'), 'run',
                   '--source-bytes', str(len(manifest_raw)), '--source-sha256',
                   hashlib.sha256(manifest_raw).hexdigest(), '--request', str(request)]
        run = subprocess.run(command, capture_output=True, text=True, timeout=10)
        assert run.returncode != 0 and 'Closed explicit operator request' in run.stderr, run
        assert 'UNAUTHENTICATED_' not in run.stdout + run.stderr, run
        resource = json.loads((source/'RESOURCE_BOUND.json').read_text())
        assert sum(resource['categories_bytes'].values()) == resource['category_total_bytes']
        assert resource['category_total_bytes'] + resource['unallocated_margin_bytes'] == resource['aggregate_reservation_minimum_bytes']
        print(json.dumps({'cached_io_and_executor_ignored': True, 'local_stdlib_shadow_ignored': True,
                          'actual_source_validator_reached': True, 'aggregate_arithmetic_checked': True,
                          'real_Docker_calls': 0, 'authentic_inputs': 0}))


if __name__ == '__main__':
    main()
