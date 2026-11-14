"""Exact A=data+paper+contract, B=identical common bytes+author code staging."""
import hashlib,json,os
from pathlib import Path
from .contract import *

COMMON={'masterTFR_allsubs.mat','paper.xml','IDENTITY.json','NUMERICAL_CONTRACT.md','OUTPUT_SCHEMA.json'}
CODE={'generateFigure2B.m','create_topo.m','PUBLICATION_LICENSE.txt'}

FIXED_SOURCES = {'masterTFR_allsubs.mat': {'bytes': 298290277, 'sha256': '536e9513b13dc721cf60613334ee37ce546e7bf67154d95bd067ddc0f0023a95'}, 'paper.xml': {'bytes': 104532, 'sha256': '9cebeab769cd7bbd674c13cb75686ba774d37e84a6c9cc3dd36a550a08b9e591'}, 'generateFigure2B.m': {'bytes': 1872, 'sha256': '41861a53e44b7e316374515739fff12b80b4f4676b3bc0b8086476357b4b8b1e'}, 'create_topo.m': {'bytes': 2546, 'sha256': 'c62c71d3f96c8399d9cd578c91b9fa6a3a99cdb449e8dbedd683c5c5490c0e23'}, 'PUBLICATION_LICENSE.txt': {'bytes': 11357, 'sha256': 'c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4'}, 'NUMERICAL_CONTRACT.md': {'bytes': 3035, 'sha256': '7a736087f3183f3cbf5f6501dfb8da177a52d39d22e3963ff8dc3a2d47c261d8'}, 'OUTPUT_SCHEMA.json': {'bytes': 11203, 'sha256': '5aa31188f161f8898bed223b0acaceca5812310bc0a03468acf142de54017c79'}}

def admit_sources(selections,budget):
    require(type(selections) is dict and set(selections)==COMMON|CODE,'exact allowed common and code sources')
    for name,row in selections.items():
        keys(row,['path','pin']);pin(row['pin'])
        if name in FIXED_SOURCES:require(row['pin']==FIXED_SOURCES[name],'selected approved source treatment')
    require(selections['IDENTITY.json']['pin']['bytes']<=65536,'bounded common identity')
    identity=json_body(read_pinned(selections['IDENTITY.json']['path'],selections['IDENTITY.json']['pin'],budget))
    metadata(identity)
    require(identity['source']==selections['masterTFR_allsubs.mat']['pin'],'identity-to-staged-master join')
    return identity

def stage_pair(*, selections, roots, budget):
    """Future trusted staging; no execution, grader/reference is ever staged."""
    admit_sources(selections,budget)
    require(type(roots) is dict and set(roots)=={'A','B'},'both fresh views')
    a,b=Path(roots['A']).absolute(),Path(roots['B']).absolute()
    require(a!=b and not a.is_relative_to(b) and not b.is_relative_to(a) and not a.exists() and not b.exists(),'separate fresh arm roots')
    # Authenticate each original before any view is published. The operator must
    # maintain exclusive custody through the second hash-bound streaming copy.
    for name,row in selections.items():
        keys(row,['path','pin']);fd=open_pinned(row['path'],row['pin'],budget);os.close(fd)
    results={}
    for arm in ['A','B']:
        root=Path(roots[arm]);root.mkdir(mode=0o700)
        members={}
        for name in sorted(COMMON|(CODE if arm=='B' else set())):
            row=selections[name];fd=open_pinned(row['path'],row['pin'],budget);h=hashlib.sha256();total=0
            try:
                with os.fdopen(fd,'rb',closefd=False) as source,(root/name).open('xb') as target:
                    while total<row['pin']['bytes']:
                        n=min(65536,row['pin']['bytes']-total);budget.charge(read=n,write=n)
                        body=source.read(n);require(len(body)==n,'short source capture');target.write(body);h.update(body);total+=n
                require(h.hexdigest()==row['pin']['sha256'],'source changed in view copy')
                (root/name).chmod(0o444);members[name]=row['pin']
            finally:os.close(fd)
        body=json.dumps({'schema':'tms_figure2b_view_v1','arm':arm,'members':members},sort_keys=True,separators=(',',':')).encode();budget.charge(write=len(body))
        with (root/'VIEW.json').open('xb') as stream:stream.write(body)
        (root/'VIEW.json').chmod(0o444);root.chmod(0o555)
        results[arm]={'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
    return results
