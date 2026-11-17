"""Exact accepted typed fingerprint; unused source-identity census removed."""
import hashlib
import struct

def fingerprint(value, max_elements=250000, max_depth=8):
    """Typed decoded-value digest; no pickle, repr, object coercion or raw hash claim."""
    h = hashlib.sha256(); count = 0; logical = 0
    def visit(x, depth):
        nonlocal count, logical
        count += 1
        if count > max_elements or depth > max_depth:
            raise ValueError('decoded value structural cap')
        if x is None: h.update(b'N'); logical += 1
        elif type(x) is bool: h.update(b'B1' if x else b'B0'); logical += 1
        elif type(x) is int:
            if not -(2**63) <= x < 2**64: raise ValueError('integer outside Arrow64 domain')
            h.update(b'I' + str(x).encode() + b';'); logical += 8
        elif type(x) is float: h.update(b'F' + struct.pack('>d', x)); logical += 8
        elif type(x) is str:
            b = x.encode('utf8'); h.update(b'S' + struct.pack('>Q', len(b)) + b); logical += len(b)
        elif type(x) is bytes:
            h.update(b'Y' + struct.pack('>Q', len(x)) + x); logical += len(x)
        elif type(x) is list:
            h.update(b'L' + struct.pack('>Q', len(x)))
            for item in x: visit(item, depth + 1)
        elif type(x) is dict and all(type(k) is str for k in x):
            h.update(b'D' + struct.pack('>Q', len(x)))
            for key in sorted(x): visit(key, depth + 1); visit(x[key], depth + 1)
        else: raise ValueError('unsupported decoded object type: ' + type(x).__name__)
    visit(value, 0)
    return {'sha256': h.hexdigest(), 'elements': count, 'logical_scalar_bytes': logical}
