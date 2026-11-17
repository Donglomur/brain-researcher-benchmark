"""Fixed A/B paper-source exposure from separately admitted original inputs.

This module only handles ordinary bytes and metadata. It neither imports the
scientific author package nor supplies runtime/exposure/target authority.
"""
import argparse
import hashlib
import importlib
import json
import re
import sys
from pathlib import Path, PurePosixPath

PAPER_PLAN_SHA = "cccfd15ca1108359b92e5b2a24651782c7ca5900752d3565efae530cc7ac4bc1"
SOURCE_PLAN_SHA = "df8d14c665e9156ee2abc1497ff85db382b36cc5aca90e700b8ed713c4144f9e"
CODE_INDEX_SHA = "562a76b7bc6202b02392da3bcdf11d0053e074ed31128b782beaa5e29b5e96d0"
SOURCE_REVISION = '703a10fb43fc7fe0076c9c331e6b52d3195b5e60'
MAX_FILE = 20_000_000
MAX_VIEW = 40_000_000
MAX_ROWS = 2000
ARTICLE_SOURCE = 'public/paper/article.xml'
OWN_ROOT = Path(__file__).resolve().parents[2]

def _distribution():
    """Load the owned distribution helpers, refusing an ambient preloaded copy."""
    package_root = OWN_ROOT / 'c4_distribution'
    for name, module in tuple(sys.modules.items()):
        if name == 'c4_distribution' or name.startswith('c4_distribution.'):
            source = getattr(module, '__file__', None)
            if not source:
                raise ImportError('preloaded distribution module lacks an owned source')
            expected = package_root / ('__init__.py' if name == 'c4_distribution'
                                       else name.split('.', 1)[1].replace('.', '/') + '.py')
            if Path(source).resolve() != expected.resolve():
                raise ImportError('conflicting preloaded distribution module')
    sys.path.insert(0, str(OWN_ROOT))
    try:
        dependencies = importlib.import_module('c4_distribution.dependencies')
        io_core = importlib.import_module('c4_distribution.io_core')
    finally:
        if sys.path and sys.path[0] == str(OWN_ROOT):
            del sys.path[0]
    for module, name in ((dependencies, 'dependencies.py'), (io_core, 'io_core.py')):
        if Path(module.__file__).resolve() != (package_root/name).resolve():
            raise ImportError('distribution import did not resolve to the owned source')
    return dependencies, io_core

def relative(value):
    if type(value) is not str or not value or '\\' in value or '\0' in value:
        raise ValueError('ordinary relative path required')
    p = PurePosixPath(value)
    if (p.is_absolute() or value != p.as_posix() or
            any(x in ('', '.', '..') for x in value.split('/')) or
            any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError('ordinary relative path required')
    return p

def captured(path, cap):
    return _distribution()[1].capture_path(path, cap)

def pairs(items):
    out = {}
    for key, value in items:
        if key in out:
            raise ValueError('duplicate JSON key')
        out[key] = value
    return out

def plan(package, name, expected):
    body = captured(Path(package)/relative(name), 1_000_000)
    if hashlib.sha256(body).hexdigest() != expected:
        raise ValueError('fixed source-plan identity')
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON')))

def _row(row):
    if type(row) is not dict or set(row) != {'source', 'target', 'bytes', 'sha256', 'origin'}:
        raise ValueError('exact exposure row required')
    source, target = str(relative(row['source'])), str(relative(row['target']))
    if not target.startswith('public/') or target.casefold() == 'source_view.json':
        raise ValueError('candidate-only public destination required')
    if type(row['bytes']) is not int or not 0 <= row['bytes'] <= MAX_FILE:
        raise ValueError('bounded source size required')
    if type(row['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', row['sha256']):
        raise ValueError('source digest required')
    if row['origin'] == 'owned_public':
        if not source.startswith('public/') or source == ARTICLE_SOURCE:
            raise ValueError('owned public source boundary')
    elif row['origin'] == 'required_article':
        if source != ARTICLE_SOURCE or target != ARTICLE_SOURCE:
            raise ValueError('exact shared article destination')
    elif row['origin'] == 'verified_original_source':
        if not source.startswith('private/official_code/') or not target.startswith('public/official_code/'):
            raise ValueError('original-source boundary')
        if source.split('private/official_code/', 1)[1] != target.split('public/official_code/', 1)[1]:
            raise ValueError('original logical name changed')
    else:
        raise ValueError('unknown source origin')
    return source, target

def _rows(rows):
    if type(rows) is not list or len(rows) > MAX_ROWS:
        raise ValueError('bounded complete source roster required')
    destinations = set()
    total = 0
    for row in rows:
        _, target = _row(row)
        if target.casefold() in destinations:
            raise ValueError('duplicate source destination')
        destinations.add(target.casefold())
        total += row['bytes']
    if total > MAX_VIEW:
        raise ValueError('complete static source view exceeds bound')

def _code_files(package, dependency_root):
    if dependency_root is None:
        raise ValueError('B requires an explicit verified original-source root')
    index = plan(package, 'private/CODE_INDEX.json', CODE_INDEX_SHA)
    if type(index) is not dict or set(index) != {'revision', 'files'} or index['revision'] != SOURCE_REVISION:
        raise ValueError('fixed original code index required')
    if type(index['files']) is not list or not 1 <= len(index['files']) <= MAX_ROWS:
        raise ValueError('complete bounded original code index')
    expected = {}
    for row in index['files']:
        if type(row) is not dict or set(row) != {'path', 'bytes', 'sha256'}:
            raise ValueError('exact code index row')
        name = str(relative(row['path']))
        if name.casefold() in {x.casefold() for x in expected}:
            raise ValueError('duplicate original source path')
        if type(row['bytes']) is not int or not 0 <= row['bytes'] <= 1048576:
            raise ValueError('ordinary original source member bound')
        if type(row['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', row['sha256']):
            raise ValueError('original source digest')
        expected[name] = row
    verified = _distribution()[0].verify_dependencies(dependency_root)
    files = verified.files
    if set(files) != set(expected):
        raise ValueError('verified dependency root and complete code index differ')
    for name, row in expected.items():
        body = files[name]
        if type(body) is not bytes or len(body) != row['bytes'] or hashlib.sha256(body).hexdigest() != row['sha256']:
            raise ValueError('code index does not bind verified original bytes')
    return files, expected

def _admit(package, rows, article_bytes, code_files):
    _rows(rows)
    files = []
    for row in rows:
        source, target = _row(row)
        if row['origin'] == 'owned_public':
            body = captured(Path(package)/source, row['bytes'])
        elif row['origin'] == 'required_article':
            body = article_bytes
        else:
            key = source.split('private/official_code/', 1)[1]
            if code_files is None or key not in code_files:
                raise ValueError('original code not admitted for this arm')
            body = code_files[key]
        if type(body) is not bytes or len(body) != row['bytes'] or hashlib.sha256(body).hexdigest() != row['sha256']:
            raise ValueError('source bytes do not match the fixed exposure row')
        files.append((target, body))
    return files

def _paper_plan(package):
    value = plan(package, 'private/PAPER_COMMON.json', PAPER_PLAN_SHA)
    if type(value) is not dict or set(value) != {'schema', 'files'} or value['schema'] != 'common_external_primary_paper_files_v2':
        raise ValueError('paper plan schema')
    _rows(value['files'])
    articles = [r for r in value['files'] if r['origin'] == 'required_article']
    if len(articles) != 1 or len(value['files']) != 2:
        raise ValueError('complete article and material-identity pair required')
    other = next(r for r in value['files'] if r['origin'] != 'required_article')
    if (other['origin'], other['source'], other['target']) != (
            'owned_public', 'public/PAPER_MATERIALS.json', 'public/PAPER_MATERIALS.json'):
        raise ValueError('exact paper-material identity document required')
    return value['files']

def common_paper_files(package, *, article_path=None):
    if article_path is None:
        raise ValueError('both arms require an explicit separately admitted article')
    rows = _paper_plan(package)
    article = _distribution()[0].load_required_article(article_path)
    return _admit(package, rows, article, None)

def source_files_for_arm(package, arm, *, article_path=None, dependency_root=None):
    if arm not in ('A', 'B'):
        raise ValueError('A or B arm required')
    if article_path is None:
        raise ValueError('both arms require an explicit separately admitted article')
    package = Path(package).absolute()
    view = plan(package, 'private/SOURCE_VIEW.json', SOURCE_PLAN_SHA)
    if type(view) is not dict or set(view) != {'schema', 'task_id', 'common', 'A_extra', 'B_extra'} or view['schema'] != 'external_paper_source_view_v2':
        raise ValueError('source-view schema')
    if view['task_id'] != 'PAPER-paper-method-replacement-003' or view['A_extra'] != []:
        raise ValueError('fixed task and no author-code A additions required')
    _rows(view['common'])
    _rows(view['B_extra'])
    if any(r['origin'] == 'verified_original_source' for r in view['common']):
        raise ValueError('author code cannot be common to A and B')
    if any(r['origin'] != 'verified_original_source' for r in view['B_extra']):
        raise ValueError('B additions must be the complete original-source roster')
    paper_rows = _paper_plan(package)
    if any(row not in view['common'] for row in paper_rows):
        raise ValueError('the exact same paper must be common to both arms')
    article = _distribution()[0].load_required_article(article_path)
    code_files, index = (None, None)
    if arm == 'B':
        code_files, index = _code_files(package, dependency_root)
        actual = {r['source'].split('private/official_code/', 1)[1]: r for r in view['B_extra']}
        if set(actual) != set(index):
            raise ValueError('B exposure must include every verified original source member')
        for name, row in index.items():
            if any(actual[name][key] != row[key] for key in ('bytes', 'sha256')):
                raise ValueError('B source view and exact code index disagree')
    rows = view['common'] + view[arm+'_extra']
    files = _admit(package, rows, article, code_files)
    receipt = {
        'schema': 'external_paper_source_view_receipt_v2',
        'task_id': view['task_id'], 'arm': arm,
        'paper_body_included': True, 'paper_shipped_in_source_distribution': False,
        'official_code_members': len(code_files) if code_files is not None else 0,
        'scientific_data_mounted': False, 'private_reference_exposed': False,
        'runtime_isolation_verified': False, 'rights_clearance': False,
        'source_plan_sha256': SOURCE_PLAN_SHA, 'paper_plan_sha256': PAPER_PLAN_SHA,
        'code_index_sha256': CODE_INDEX_SHA if arm == 'B' else None,
        'files': [{'path': name, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
                  for name, body in files],
    }
    return files, receipt

def stage_source(package, output, arm, *, article_path=None, dependency_root=None):
    files, receipt = source_files_for_arm(package, arm, article_path=article_path,
                                         dependency_root=dependency_root)
    encoded = (json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False)+'\n').encode()
    publication = _distribution()[1].publish_tree(
        output, files+[('SOURCE_VIEW.json', encoded)], max_files=MAX_ROWS+1, max_bytes=MAX_VIEW)
    return {**receipt, 'publication': publication}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--arm', choices=('A', 'B'), required=True)
    parser.add_argument('--article-path', required=True)
    parser.add_argument('--dependency-root')
    args = parser.parse_args()
    result = stage_source(args.package, args.output, args.arm,
                          article_path=args.article_path, dependency_root=args.dependency_root)
    print(json.dumps({'arm': args.arm, 'files': len(result['files']),
                      'bytes': sum(x['bytes'] for x in result['files'])}))
