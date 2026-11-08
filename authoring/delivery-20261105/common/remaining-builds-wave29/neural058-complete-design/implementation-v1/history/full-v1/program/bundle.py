"""Uncompressed, non-executable artifact container with complete member pins.

One fixed native output contains a variable complete reference state. Dynamic
tree/tensor members never bypass the daemon's exact top-level output inventory.
"""
import os
import stat
from pathlib import Path
from core import need, integer, encoded, parse, pin, relative, capture, publish, describe_sealed, fresh

MAGIC=b'N058B001'


def pack(root,destination,budget,limits):
    root=Path(root);pending=[root];rows=[]
    while pending:
        folder=pending.pop()
        with os.scandir(folder) as scan: entries=sorted(scan,key=lambda x:x.name)
        for entry in entries:
            budget.tick();st=entry.stat(follow_symlinks=False);p=Path(entry.path)
            need(not stat.S_ISLNK(st.st_mode),'no bundle symlinks')
            if stat.S_ISDIR(st.st_mode): pending.append(p);continue
            need(stat.S_ISREG(st.st_mode) and st.st_nlink==1,'ordinary bundle file')
            name=str(p.relative_to(root));relative(name)
            rows.append({'path':name,'pin':describe_sealed(p,limits['member_bytes'],budget)})
            need(len(rows)<=limits['members'],'complete bundle member bound')
    rows.sort(key=lambda r:r['path']);need(rows,'nonempty complete product')
    metadata={'schema':'neural058_artifact_bundle_v1','members':rows}
    budget.reserve_write(limits['metadata_bytes']);head=encoded(metadata)
    need(len(head)<=limits['metadata_bytes'],'bundle header bound')
    size=16+len(head)+sum(r['pin']['bytes'] for r in rows)
    need(size<=limits['bundle_bytes'],'complete bundle, no pruning to fit')
    # The complete buffer and individual captures coexist. Hard memory/storage
    # limits must cover this implementation; this is not a streaming claim.
    budget.reserve_write(size)
    parts=[MAGIC,len(head).to_bytes(8,'little'),head]
    for row in rows:
        raw,_=capture(root/relative(row['path']),row['pin'],limits['member_bytes'],budget,readonly=True)
        parts.append(raw)
    body=b''.join(parts);need(len(body)==size,'exact bundle extent')
    return publish(destination,body,budget,readonly=True)


def unpack(path,expected,destination,budget,limits):
    raw,custody=capture(path,expected,limits['bundle_bytes'],budget,readonly=True)
    need(raw[:8]==MAGIC and len(raw)>=16,'exact non-executable bundle')
    size=int.from_bytes(raw[8:16],'little')
    need(0<size<=limits['metadata_bytes'] and 16+size<=len(raw),'bounded bundle metadata')
    metadata=parse(raw[16:16+size]);need(metadata.get('schema')=='neural058_artifact_bundle_v1','bundle schema')
    rows=metadata['members'];need(type(rows)is list and 0<len(rows)<=limits['members'],'complete member roster')
    need([r['path'] for r in rows]==sorted(set(r['path'] for r in rows)),'unique sorted member names')
    cursor=16+size;captured=[]
    for row in rows:
        budget.tick();relative(row['path']);n=integer(row['pin']['bytes'])
        need(n<=limits['member_bytes'] and cursor+n<=len(raw),'member bounded extent')
        value=raw[cursor:cursor+n];need(pin(value)==row['pin'],'exact per-member body identity')
        captured.append((row,value));cursor+=n
    need(cursor==len(raw),'no unadmitted trailing payload')
    root=fresh(destination,budget);made={root}
    for row,value in captured:
        target=root/relative(row['path'])
        for parent in reversed(target.parents):
            if root in parent.parents and parent not in made: fresh(parent,budget);made.add(parent)
        need(publish(target,value,budget,readonly=True)==row['pin'],'exact bundle-derived member publication')
    budget.tick()
    return {'root':str(root),'source_bundle':expected,'members':rows,'custody':custody,
            'expansion':'stored primitive bytes, no compression or executable deserialization'}
