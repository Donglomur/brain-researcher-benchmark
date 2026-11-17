"""Operator-only static scorer; validates every candidate query before targets."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import io_utils as io
import order_core


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-root', required=True)
    ap.add_argument('--binding', required=True)
    ap.add_argument('--submission', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    binding = io.strict(io.read(args.binding, 4096))
    io.need(type(binding) is dict and set(binding) == {'schema', 'public_manifest', 'private_targets'}
            and binding['schema'] == 'neural035-grade-binding-v1', 'operator binding')
    public = io.strict(io.captured(args.data_root, binding['public_manifest'], 2000000))
    doc = io.strict(io.read(args.submission, 2000000))
    result = order_core.grade(doc, public,
        lambda: io.strict(io.captured(args.data_root, binding['private_targets'], 16000000)))
    io.write_new(args.output, result, 2000000)


if __name__ == '__main__':
    main()
