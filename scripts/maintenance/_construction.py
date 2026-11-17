"""Explicit external inputs and staging outputs for historical reconstruction."""
from pathlib import Path
import hashlib

PUBLIC_ROOT = Path(__file__).resolve().parents[2]


def arguments(parser):
    parser.add_argument('--construction-root', help='Original-layout construction input tree (outside this public repository)')
    parser.add_argument('--output-directory', help='Explicit staging directory, outside both input and public repository trees')


def paths(args, parser):
    if not args.construction_root or not args.output_directory:
        parser.error('--construction-root and --output-directory are required; private construction inputs are not included in this public repository')
    source = Path(args.construction_root).absolute()
    output = Path(args.output_directory).absolute()
    for path in (source, output):
        if '..' in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
            parser.error('Construction and output paths must be ordinary paths without symlinks or traversal')
    source, output = source.resolve(), output.resolve()
    if not source.is_dir():
        parser.error('Construction input root does not exist')
    if (source == PUBLIC_ROOT or source.is_relative_to(PUBLIC_ROOT)
            or PUBLIC_ROOT.is_relative_to(source)):
        parser.error('Construction inputs must be an explicit external original-layout tree')
    if (output == PUBLIC_ROOT or output.is_relative_to(PUBLIC_ROOT)
            or PUBLIC_ROOT.is_relative_to(output)
            or output == source or output.is_relative_to(source) or source.is_relative_to(output)):
        parser.error('Output must be a separate staging directory, not a public repository or construction-input ancestor/descendant')
    if output.exists() and not output.is_dir():
        parser.error('Output must be a directory')
    return source, output


def generator(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return {'path': path.relative_to(PUBLIC_ROOT).as_posix(), 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest(), 'scope': 'current_public_repository'}
