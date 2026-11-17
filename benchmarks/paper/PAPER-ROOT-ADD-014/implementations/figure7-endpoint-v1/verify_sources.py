"""Verify explicit cached public source files, never recordings or saved fits.

Run through the coordinated lightweight pool. The existing inventories are
provenance evidence, not proof that these commits exactly match paper execution.
"""
import argparse
import hashlib
import json
from pathlib import Path


SOURCES = (
    ('author', 'CODE_INVENTORY.json', 'KenYMB/ECoG_alphaPRF',
     '4321eb4374db782d09f3f43362836f234a4e4f9b', (
         'makeFigures/makeFigure7_7S1.m',
         'scripts/ecog_APRFF_10k1e_checkalpha_bothgaind.m',
         'scripts/ecog_APRFF_INITa_loaddata.m',
         'scripts/ecog_APRFF_INITb_mergedata.m',
         'scripts/ecog_APRFF_INITd_threshold.m',
         'functions/files/ecog_prf_getthreshold.m',
         'functions/Outline/ecog_prf_analyzePRF.m',
         'functions/utils/ecog_channelSelection.m',
         'functions/utils/ecog_rearrangePRF.m',
         'Environment/alphafittype.tsv',
     )),
    ('ecog-utils', 'ECOG_UTILS_INVENTORY.json', 'KenYMB/ECoG_utils',
     '1dd4ea481ff56f1f77db75aa886017ea30eaf940', ('functions/analyzePRF/analyzePRFdog.m',)),
    ('analyzeprf', 'ANALYZEPRF_INVENTORY.json', 'cvnlab/analyzePRF',
     'dca6c752f0d28274d7186b8d3515faf8d4d3d7c7',
     ('utilities/fitnonlinearmodel_helper.m', 'utilities/calccod.m')),
)


def verify(root):
    members, inventories = [], []
    for directory, inventory_name, repository, commit, paths in SOURCES:
        raw = (root / inventory_name).read_bytes()
        inventory = json.loads(raw)
        if inventory['commit'] != commit:
            raise ValueError('source inventory commit mismatch')
        by_path = {r['path']: r for r in inventory['files']}
        if len(by_path) != len(inventory['files']):
            raise ValueError('duplicate source inventory path')
        inventories.append({'repository': repository, 'commit': commit,
                            'inventory_sha256': hashlib.sha256(raw).hexdigest()})
        for path in paths:
            raw_source = (root / directory / path).read_bytes()
            found = {'bytes': len(raw_source), 'sha256': hashlib.sha256(raw_source).hexdigest(),
                     'git_blob_sha1': hashlib.sha1(b'blob ' + str(len(raw_source)).encode()
                                                  + b'\0' + raw_source).hexdigest()}
            if any(by_path[path][k] != v for k, v in found.items()):
                raise ValueError('cached source identity mismatch: ' + path)
            members.append({'repository': repository, 'commit': commit, 'path': path,
                            'url': 'https://github.com/' + repository + '/blob/' + commit + '/' + path,
                            **found})
    return {'schema': 'visual_alpha_figure7_source_lock_v1', 'members': members,
            'inventories': inventories, 'new_download_bytes': 0,
            'historical_paper_execution_version_verified': False,
            'scope': 'existing public author source bytes only; no numerical data, fitted values or targets read'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = verify(args.source_root)
    args.output.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'verified_files': len(output['members']), 'new_download_bytes': 0,
                      'source_bytes_checked': sum(m['bytes'] for m in output['members'])}))
