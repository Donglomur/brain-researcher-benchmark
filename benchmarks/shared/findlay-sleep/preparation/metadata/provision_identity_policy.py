"""Reconstruct the fixed private policy from three exact official source files.

Static parsing only. No author code execution, observations or network access.
The output is private metadata and must remain outside a public source tree.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat

PINS = {
    'core': (14837, '17ec540c87f59583e868865202e3741fe68c9ea4d183597f7132a1603d466e9c'),
    'loader': (7075, '0268b48a7857d65cf5676df13142e9380287fb3280d1f80de1b36e7742a67b4b'),
    'exporter': (6014, '2556a97a5b71ec5d31992e9e2096051347e82c0e192241d1375243fe1e852460'),
}
OUTPUT_PIN = (935, '4879ce87b72c06d88a67149c990f876ffca8254bfcfc659229a72e0ebd569ab2')
PROVENANCE = {
    'family_rules_sha256': '099c182250d5610a4f9aea3c58e9897fae96157eb464c5c24f327eb60a35d2f4',
    'ordinary_policy_sha256': 'd9ef897d0387fa3785ea46f94730e886b429a38ca5e589e89e82134fa1725b01',
    'input_ledger_sha256': 'd2756c791ccdedf22de2ef5e2949b43d804c0232c1aeddcb6ff25411ddaafed1',
    'family_ledger_sha256': 'e6602394041e2a6f448db374ffccbf06856f262e13df468003a901ae4fa2eced',
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def unique(pairs):
    value = {}
    for key, item in pairs:
        need(key not in value, 'Duplicate key')
        value[key] = item
    return value


def authenticated_file(path, pin):
    """Bound ordinary-file capture, no symlink/FIFO following or pathname reopen."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_size == pin[0], 'Exact source extent')
        chunks = []; remaining = pin[0] + 1
        while remaining:
            part = os.read(fd, remaining)
            if not part:
                break
            chunks.append(part); remaining -= len(part)
        after = os.fstat(fd)
        need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
             == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
             'Source changed during capture')
    finally:
        os.close(fd)
    body = b''.join(chunks)
    need((len(body), hashlib.sha256(body).hexdigest()) == pin, 'Exact source identity')
    return body


def assignment(tree, name):
    nodes = [n.value for n in tree.body if isinstance(n, ast.Assign)
             and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
             and n.targets[0].id == name]
    need(len(nodes) == 1, 'Exactly one selected assignment required')
    return nodes[0]


def literal(node):
    """Small literal grammar; Exps names are tokens, never evaluated imports."""
    if isinstance(node, ast.Constant) and type(node.value) is str:
        return node.value
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'Exps':
        need(node.attr in ('NOD', 'COW', 'CTN'), 'Unknown experiment token')
        return node.attr
    if isinstance(node, (ast.List, ast.Tuple)):
        return [literal(x) for x in node.elts]
    if isinstance(node, ast.Dict):
        return unique((literal(k), literal(v)) for k, v in zip(node.keys, node.values))
    raise ValueError('Nonliteral source expression')


def derive(core_body, loader_body, notebook_body):
    """Pure derivation for generated controls; production authenticates first."""
    core = ast.parse(core_body)
    manifest = assignment(core, 'MANIFEST')
    need(isinstance(manifest, ast.Call) and isinstance(manifest.func, ast.Name)
         and manifest.func.id == 'MappingProxyType' and len(manifest.args) == 1
         and not manifest.keywords, 'Literal source roster required')
    roster = literal(manifest.args[0])
    experiments = literal(assignment(core, 'EXPERIMENT_DISPLAY_NAMES'))
    need(experiments == {'NOD': 'Novelty', 'COW': 'Locomotion', 'CTN': 'Dual'}, 'Exact experiment meanings')
    need(len(roster) == 16 and sum(map(len, roster.values())) == 29
         and all(len(v) == len(set(v)) and set(v) <= set(experiments) for v in roster.values()),
         'Complete sixteen-animal twenty-nine-session roster')
    loader = loader_body.decode('utf-8') if isinstance(loader_body, bytes) else loader_body
    matches = re.findall(r'dual_subjects\s*<-\s*c\(([^)]*)\)', loader)
    need(len(matches) == 1, 'Exactly one official balanced-cohort literal')
    # A complete quoted-string vector, not a partial regex extraction.
    balanced = json.loads('[' + matches[0] + ']')
    need(type(balanced) is list and len(balanced) == 5 and all(type(x) is str for x in balanced)
         and len(set(balanced)) == 5 and all(x in roster and {'NOD', 'CTN'} <= set(roster[x]) for x in balanced),
         'Five distinct balanced subjects with both protocols')
    nb = json.loads(notebook_body, object_pairs_hook=unique)
    need(type(nb) is dict and type(nb.get('cells')) is list, 'Notebook structure')
    source = []
    for cell in nb['cells']:
        need(not cell.get('outputs'), 'Source-only notebook required')
        if cell.get('cell_type') == 'code':
            lines = cell.get('source')
            need(type(lines) is list and all(type(x) is str for x in lines), 'Notebook code lines')
            source.append(''.join(lines))
    tree = ast.parse('\n'.join(source))
    exclusions = literal(assignment(tree, 'exclusions'))
    columns = literal(assignment(tree, 'contrast_display_names'))
    need(len(exclusions) == 6 and len(columns) == 27 and len(set(columns.values())) == 27,
         'Complete six source exclusions and twenty-seven columns')
    selected = []
    seen = set()
    for row in exclusions:
        need(type(row) is list and len(row) == 3, 'Exclusion tuple')
        subject, experiment, fragments = row
        need(subject in roster and experiment in roster[subject] and type(fragments) is list
             and fragments and all(type(x) is str and x for x in fragments), 'Source exclusion identity')
        need((subject, experiment) not in seen, 'Duplicate exclusion identity')
        seen.add((subject, experiment))
        affected = sorted(display for raw, display in columns.items()
                          if any(fragment in raw for fragment in fragments))
        if affected:
            selected.append({'subject': subject, 'experiment': experiments[experiment], 'columns': affected})
    need(len(selected) == 1 and selected[0]['experiment'] == 'Novelty'
         and len(selected[0]['columns']) == 13, 'One thirteen-column declared exclusion')
    return {'schema': 'findlay-private-identity-policy/v1',
            'balanced_subjects': sorted(balanced), 'ordinary_exclusion': selected[0],
            'provenance': dict(PROVENANCE)}


def encode(policy):
    return (json.dumps(policy, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def provision(paths):
    bodies = {role: authenticated_file(paths[role], pin) for role, pin in PINS.items()}
    body = encode(derive(bodies['core'], bodies['loader'], bodies['exporter']))
    need((len(body), hashlib.sha256(body).hexdigest()) == OUTPUT_PIN,
         'Derivation differs from the frozen policy; no replacement admitted')
    return body


def write_exclusive(path, body):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(body); stream.flush(); os.fsync(stream.fileno())
    except BaseException:
        # Preserve any failed partial output; never replace or unlink operator files.
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for role in PINS:
        parser.add_argument('--' + role, required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    body = provision({role: getattr(args, role) for role in PINS})
    write_exclusive(args.output, body)
    print(json.dumps({'schema': 'findlay-policy-provisioned/v1', 'bytes': len(body),
                      'sha256': hashlib.sha256(body).hexdigest(),
                      'metadata_only': True, 'scientifically_qualified': False}, sort_keys=True))


if __name__ == '__main__':
    main()
