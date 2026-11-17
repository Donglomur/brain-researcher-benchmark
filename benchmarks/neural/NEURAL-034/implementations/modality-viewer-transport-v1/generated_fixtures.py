"""Invented fixture helpers; imported by the new tests only, never production."""
import base64
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('neural034_generated_modality_transport', HERE / 'transport.py')
M = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = M
SPEC.loader.exec_module(M)
C, T = M.C, M.T
FRAMEWORK = Path('/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11')
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII=')
CLIENT = (HERE / 'scripted_client.py').read_text()
CLIENT_FUNCTIONS = CLIENT.rsplit("if __name__ == '__main__':", 1)[0]
WRITTEN = 0
RENDER_CALLS = 0
CAP = 7 * 1024**2


class Repeated:
    def __init__(self, value, count):
        self.value, self.count = value, count

    def __getitem__(self, index):
        assert type(index) is int and 0 <= index < self.count
        return self.value


class GuardedArrays(dict):
    def __init__(self, values, excluded):
        super().__init__(values)
        self.excluded = set(excluded)
        self.accesses = []

    def __getitem__(self, key):
        self.accesses.append(key)
        if key in self.excluded:
            raise AssertionError('Excluded modality read before projection')
        return super().__getitem__(key)


class Packet:
    def __init__(self, fold, condition):
        self.fold, self.ids = fold, list(C.IDS[fold])
        self.pin = {'bytes': 0, 'sha256': hashlib.sha256(f'generated-fixture-{fold}'.encode()).hexdigest()}
        excluded = ('train_behavior', 'query_behavior') if condition == 'calcium_only_v1' else (
            ('train_windows', 'query_windows') if condition == 'behavior_only_v1' else ())
        self.arrays = GuardedArrays({
            'train_windows': Repeated([[0.0] * 12] * 300, 120),
            'query_windows': Repeated([[0.0] * 12] * 300, 20),
            'train_behavior': Repeated([0] * 300, 120), 'query_behavior': Repeated([0] * 300, 20),
            'train_labels': [0, 1] * 60,
        }, excluded)

    def observation(self, *args):
        raise AssertionError('Combined unprojected observation was called')


def rendered(record, gain, raster, base, condition):
    global RENDER_CALLS
    expected = {'role', 'index'} | ({'label'} if record['role'] == 'training' else set())
    if 'calcium' in C.select(condition):
        expected.add('windows')
    if 'behavior' in C.select(condition):
        expected.add('behavior')
    assert set(record) == expected
    RENDER_CALLS += 1
    return PNG, []


@contextlib.contextmanager
def generated():
    original = C.T.v.dependencies
    def dependencies():
        raster, renderer, rows, ids = original()
        rows = dict(rows)
        for fold in range(7):
            rows[f'fold-{fold:02d}'] = {**rows[f'fold-{fold:02d}'], **Packet(fold, 'combined_calcium_behavior_v1').pin}
        return raster, renderer, rows, ids
    with patch.object(C.RENDERER, 'render', side_effect=rendered), patch.object(C.T.v, 'dependencies', side_effect=dependencies):
        yield


@contextlib.contextmanager
def guarded_writes(root):
    original = Path.open
    root = Path(root).absolute()
    class Writer:
        def __init__(self, stream):
            self.stream = stream
        def write(self, body):
            global WRITTEN
            size = len(body.encode() if isinstance(body, str) else body)
            if WRITTEN + size > CAP:
                raise RuntimeError('Stop before cumulative generated fixture cap')
            WRITTEN += size
            return self.stream.write(body)
        def __getattr__(self, name):
            return getattr(self.stream, name)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return self.stream.__exit__(*args)
    def opened(path, mode='r', *args, **kwargs):
        stream = original(path, mode, *args, **kwargs)
        candidate = Path(path).absolute()
        opaque_code_copy = (candidate.name == 'client.py' and candidate.parent.name.startswith('neural034-modality-code-')
                            and candidate.parent.parent == Path('/tmp').resolve())
        if (candidate.is_relative_to(root) or opaque_code_copy) and any(flag in mode for flag in ('w', 'x', 'a', '+')):
            return Writer(stream)
        return stream
    with patch.object(Path, 'open', opened):
        yield


def limits(**changes):
    values = {'max_actions': 161, 'max_images': 140, 'max_output_bytes': 64 * 1024**2, 'wall_seconds': 10}
    values.update(changes)
    return T.Limits(**values)


@contextlib.contextmanager
def replaced(path, body):
    original = path.read_bytes()
    path.write_bytes(body)
    try:
        yield
    finally:
        path.write_bytes(original)


def decode(path):
    return T.decode(path.read_bytes())


def pins():
    return {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
            for name in ('transport.py', 'SOURCE_BINDINGS.json', 'scripted_client.py')}
