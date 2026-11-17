"""Two independently authored frozen banks, compared on every numerical call."""
import importlib.util
from pathlib import Path
from .validation import sha, need, encoded, decode, digest, close_numbers, integer

BANKS = (
    ('numerical_bank_a', 14745, 'b8abd0ba49b97854200eeb6a5d4f1c02a9276a0e1f923ba21788af7cbe97e14e'),
    ('numerical_bank_b', 16592, '5235c03f9800bca334bd33ed8cae3c149715fe5ee2014eddd913e0924a463d89'),
)
_loaded = None


def banks():
    global _loaded
    if _loaded is None:
        import hashlib
        root = Path(__file__).resolve().parent.parent
        modules = []
        for name, size, expected in BANKS:
            path = root / name / 'bank.py'
            need(not path.is_symlink(), 'regular numerical source')
            raw = path.read_bytes()
            need(len(raw) == size and hashlib.sha256(raw).hexdigest() == expected, 'independent bank source commitment')
            spec = importlib.util.spec_from_file_location('motormint_' + name, path)
            module = importlib.util.module_from_spec(spec)
            exec(compile(raw,str(path),'exec',dont_inherit=True),module.__dict__)
            modules.append(module)
        _loaded = tuple(modules)
    return _loaded


def evaluate(kind, payload, *, maximum_bytes=2 * 1024 * 1024):
    integer(maximum_bytes, 1, 34359738368)
    raw = encoded(payload)
    need(len(raw) <= maximum_bytes, 'operator-selected numerical payload ceiling')
    outputs, errors = [], []
    for bank in banks():
        independent = decode(raw)
        try:
            outputs.append(bank.evaluate(kind, independent)); errors.append(None)
        except ValueError as error:
            outputs.append(None); errors.append(str(error))
        need(encoded(independent) == raw, 'numerical bank must not mutate evaluation inputs')
    if any(errors):
        need(all(errors), 'independent numerical validity disagreement')
        raise ValueError('undefined/invalid metric rejected by both independent banks: ' + '; '.join(errors))
    close_numbers(outputs[0], outputs[1])
    return {'value': outputs[0], 'bank_agreement': True, 'payload_sha256': digest(payload),
            'banks': [row[2] for row in BANKS], 'native_evaluator_equivalence': False}
