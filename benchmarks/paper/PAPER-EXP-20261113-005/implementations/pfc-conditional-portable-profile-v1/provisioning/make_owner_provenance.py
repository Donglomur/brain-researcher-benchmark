"""Materialize inert owner-local lineage metadata, without any scientific files.

The existing PFC deployment reads this descriptor, checks the nine identities,
and never follows their paths. Locator labels are deliberately not a claim
that the original prepared scientific files are present. This is not the
historical preparation selection and grants no execution authority.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_packet_release import decode, need, read_exact

LINEAGE_BYTES = 3783
LINEAGE_SHA256 = 'ddd3152dd547a80a31708a6f350bf817c49b38fb8f7ec85a4cee1b36c907e6d3'
ROLES = {'lineage', 'linkage', 'cohort', 'order', 'gao_units', 'data_units', 'gao_stats', 'data_stats', 'hierarchy'}


def ordinary_absolute(value):
    value = str(value)
    need(not any(c in value for c in '\0\r\n,'), 'ordinary path syntax')
    p = Path(value)
    need(p.is_absolute() and '..' not in p.parts and
         not any(x.is_symlink() for x in (p, *p.parents)), 'ordinary absolute path')
    return p


def load_lineage():
    p = Path(__file__).absolute().with_name('PUBLIC_LINEAGE.json')
    return decode(read_exact(p, LINEAGE_BYTES, LINEAGE_SHA256))


def materialize(output, locator_root):
    lineage = load_lineage()
    need(lineage['schema'] == 'PFC_PUBLIC_PREPARED_INPUT_IDENTITIES_V1' and
         set(lineage['prepared_inputs']) == ROLES and
         sum(v['bytes'] for v in lineage['prepared_inputs'].values()) == lineage['total_encoded_bytes'] == 22183624,
         'complete frozen public lineage')
    output, locator_root = ordinary_absolute(output), ordinary_absolute(locator_root)
    need(output.parent.is_dir(), 'output parent must already exist')
    need(not output.exists() and output != locator_root, 'fresh metadata output')
    inputs = {role: {'path': str(locator_root / (role + '.identity-only')), **identity}
              for role, identity in lineage['prepared_inputs'].items()}
    body = (json.dumps({'schema': 'PFC_FULL99_CONDITIONAL_INPUT_SELECTION_V1',
             'inputs': inputs, 'total_encoded_bytes': 22183624,
             'provenance_identity': {'bytes': LINEAGE_BYTES, 'sha256': LINEAGE_SHA256},
             'packet_identity': lineage['packet'], 'scope': 'owner-only provenance metadata',
             'input_paths_are_inert_locator_labels': True, 'input_file_presence_claimed': False,
             'scientific_preparation_selection': False, 'execution_authority': False},
             sort_keys=True, indent=2) + '\n').encode()
    need(len(body) <= 16384, 'bounded metadata')
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        # Preserve any partial exclusive output as a failed operation; never retry.
        raise
    return {'path': str(output), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--locator-root', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(materialize(args.output, args.locator_root), sort_keys=True))


if __name__ == '__main__':
    main()
