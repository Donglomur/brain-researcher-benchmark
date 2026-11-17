"""A boundary control must be unable to read private inputs or another case."""
import argparse
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--input', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
for path in ('/private', '/comparators', '/source', '/training/raw', '/input/development-002_features.npz'):
    assert not Path(path).exists(), 'Unexpected input access: ' + path
(args.out / 'predictions.npz').write_bytes(b'opaque')
(args.out / 'extra.txt').write_text('This extra artifact must reject before private grading.')
