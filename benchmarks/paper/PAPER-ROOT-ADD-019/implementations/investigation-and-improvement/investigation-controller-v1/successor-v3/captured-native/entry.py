"""Disabled-by-default native component; qualified operator API is dispatch.run."""
import json
from pathlib import Path
from protocol import decode,canonical_contract,qualify

HERE=Path(__file__).resolve().parent
def installed():
    c=decode((HERE/'CONTRACT.json').read_bytes(),262144)
    q=decode((HERE/'QUALIFICATION.json').read_bytes(),16384)
    return canonical_contract(c),q
def main():
    c,q=installed()
    print(json.dumps(dict(task=c['canonical_id'],roots=37,native_jobs=111,recompute_branches=8,
      source_component=True,execution_enabled=q['execution_enabled'],scientific_qualified=False,
      full_paper_complete=False,missing=c['mandatory_unresolved']),sort_keys=True))
if __name__=='__main__':main()
