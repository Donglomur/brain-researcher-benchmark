"""Compose transport and participant callbacks into the single allowed source.

No method is executed by this builder. Submit the resulting program.py and a
truthful method disclosure through the separately authorized operator route.
"""
import argparse
from pathlib import Path

PROGRAM_CAP = 1_048_576


def bundle(method):
    client = Path(__file__).with_name("client.py").read_bytes()
    if type(method) is not bytes or not 0 < len(method) <= PROGRAM_CAP:
        raise ValueError("nonempty bounded UTF-8 method source")
    text = method.decode("utf8")
    compile(text, "participant_method.py", "exec")
    # Isolate method definitions from transport names. This is ordinary candidate
    # execution, not a security boundary; the host remains the access controller.
    suffix = ("\nif __name__ == '__main__':\n"
              "    import types as _types\n"
              "    _method = _types.ModuleType('participant_method')\n"
              "    _method.__file__ = globals().get('__file__', 'program.py')\n"
              "    sys.modules['participant_method'] = _method\n"
              "    exec(compile(" + repr(text) + ", _method.__file__, 'exec'), _method.__dict__)\n"
              "    entry(_method.fit, _method.start)\n")
    result = client + suffix.encode("utf8")
    if len(result) > PROGRAM_CAP:
        raise ValueError("bundled program exceeds host 1 MiB source limit")
    compile(result, "program.py", "exec")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.method.open("rb") as stream:
        raw = stream.read(PROGRAM_CAP + 1)
    body = bundle(raw)
    with args.output.open("xb") as stream:
        stream.write(body)


if __name__ == "__main__":
    main()
