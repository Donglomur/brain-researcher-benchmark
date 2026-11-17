"""Stdlib framing example: fixed 0.5 is a software control, not a model result."""
import json
import re
import struct
import sys

PREFIX = struct.Struct("!I")


def exact(size):
    out = bytearray()
    while len(out) < size:
        part = sys.stdin.buffer.read(size - len(out))
        if not part:
            raise ValueError("Incomplete input")
        out.extend(part)
    return bytes(out)


def main():
    size = PREFIX.unpack(exact(PREFIX.size))[0]
    if not 0 < size <= 2097152:
        raise ValueError("Input cap")
    prompt = exact(size).decode("utf-8")
    identifiers = set(re.findall(r"development-00[12]-[0-9a-f]{24}", prompt))
    if len(identifiers) != 1:
        raise ValueError("Exactly one query identity")
    body = json.dumps({"trial_id": identifiers.pop(), "target_probability": 0.5}).encode()
    sys.stdout.buffer.write(PREFIX.pack(len(body)) + body)
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
