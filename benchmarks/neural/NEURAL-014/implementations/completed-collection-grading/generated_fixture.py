"""Invented45-session/54-row fixture; no authentic arrays or labels."""
import hashlib

def fixture():
    rows=[]
    for i in range(1,46):
        roles=['train'] if i<=27 else ['development'] if i<=36 else ['calibration','query']
        for role in roles:
            key=hashlib.sha256(f'invented-{i}-{role}'.encode()).hexdigest()
            row=dict(id=key,session=f'session-{i:03}',role=role,steps=1,features=dict(path='arrays/'+key+'.npy',bytes=2176,sha256='a'*64))
            if role=='query':row['permutation']=dict(path='permutations/'+key+'.bin',bytes=16,sha256='b'*64)
            else:row['tokens']=['AA']
            rows.append(row)
    return dict(schema='neural014-program-panel-v1',generation='c'*64,sessions=[dict(session_id=f'session-{i:03}',role='train' if i<=27 else 'development' if i<=36 else 'query') for i in range(1,46)],rows=rows)
