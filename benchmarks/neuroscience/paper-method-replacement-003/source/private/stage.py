"""Static normalized-fold A/B view using separately admitted exact source bytes.

Does not execute candidate or author code and does not enforce runtime isolation.
"""
import argparse
import hashlib
import importlib
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
def _own_module(name, directory):
    expected = directory/(name+'.py')
    previous = sys.modules.get(name)
    if previous is not None and Path(getattr(previous, '__file__', '')).resolve() != expected.resolve():
        raise ImportError('conflicting preloaded C4 owned module')
    sys.path.insert(0, str(directory))
    try:
        module = importlib.import_module(name)
    finally:
        if sys.path and sys.path[0] == str(directory):
            del sys.path[0]
    if Path(module.__file__).resolve() != expected.resolve():
        raise ImportError('C4 owned module resolved outside the package')
    return module

paper_access = _own_module('paper_access', BASE/'private')
contract = _own_module('contract', BASE/'public')
prepare = _own_module('prepare', BASE/'private')
# Preserve the exact original fold validator and its source functions.
exact, need, sha, ident = contract.exact, contract.need, contract.sha, contract.ident
TASK, CLASSES, ARMS, REV = contract.TASK, contract.CLASSES, contract.ARMS, contract.REV
features, decode, enc = prepare.features, contract.decode, contract.enc

def fold(v):
    exact(v,('schema','task_id','query_sha256','case','training','query','pretraining_index_sha256','pretraining_unit_ids'));need(v['schema']=='c4_fold_v1' and v['task_id']==TASK,'fold identity');sha(v['query_sha256']);sha(v['pretraining_index_sha256']);ident(v['case']);need(type(v['pretraining_unit_ids']) is list,'pretraining IDs')
    allids=[];cols=None
    for role in ('training','query'):
        need(type(v[role]) is list and 1<=len(v[role])<=20000,'nonempty complete role')
        for row in v[role]:
            exact(row,('unit_id','features','label') if role=='training' else ('unit_id','features'));ident(row['unit_id']);features(row['features']);allids.append(row['unit_id'])
            names=sorted(row['features']['engineered']);need(cols is None or cols==names,'same engineered feature columns');cols=names
            if role=='training':need(row['label'] in CLASSES,'training label')
    need(len(allids)==len(set(allids)) and not set(allids)&set(v['pretraining_unit_ids']),'no test/training/pretraining overlap')
    return v

def stage(packet, packet_sha, arm, out, cap=16_000_000, *,
          article_path=None, dependency_root=None):
    need(arm in ARMS, 'arm')
    sha(packet_sha)
    need(type(cap) is int and cap > 0, 'positive complete view cap')
    body = paper_access.captured(packet, cap)
    need(hashlib.sha256(body).hexdigest() == packet_sha, 'externally trusted fold pin')
    fold(decode(body))
    code_arm = 'A' if arm == ARMS[0] else 'B'
    sources, source_receipt = paper_access.source_files_for_arm(
        BASE, code_arm, article_path=article_path, dependency_root=dependency_root)
    rows = [('public/FOLD.json', body)] + sources
    meta = {
        'schema': 'c4_static_view_external_source_v2', 'arm': arm,
        'packet_sha256': packet_sha, 'isolation_qualified': False,
        'source_revision': REV, 'paper_body_included': True,
        'official_code_members': source_receipt['official_code_members'],
        'source_plan_sha256': source_receipt['source_plan_sha256'],
        'paper_plan_sha256': source_receipt['paper_plan_sha256'],
        'code_index_sha256': source_receipt['code_index_sha256'],
        'rights_clearance': False,
    }
    rows.append(('VIEW.json', enc(meta)))
    need(sum(len(value) for _, value in rows) <= cap, 'whole static view cap before writes')
    publication = paper_access._distribution()[1].publish_tree(
        out, rows, max_files=paper_access.MAX_ROWS+2, max_bytes=cap, max_member_bytes=cap)
    return {**meta, 'publication': publication}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', required=True)
    parser.add_argument('--packet-sha256', required=True)
    parser.add_argument('--arm', choices=ARMS, required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--article-path', required=True)
    parser.add_argument('--dependency-root')
    args = parser.parse_args()
    stage(args.packet, args.packet_sha256, args.arm, args.output,
          article_path=args.article_path, dependency_root=args.dependency_root)
if __name__ == '__main__':
    main()
