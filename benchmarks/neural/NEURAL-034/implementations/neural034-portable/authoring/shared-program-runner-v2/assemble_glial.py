"""Bounded public-only JSON validation/assembly; never loads private targets."""
import hashlib,json,math
from profile import decode,need
MAX=100000


def validate(body,ids):
    need(type(body)is bytes and 0<len(body)<=MAX,'Bounded unit output')
    obj=decode(body);need(type(obj)is dict and set(obj)=={'schema_version','probabilities'}and type(obj['schema_version'])is int and obj['schema_version']==1,'Exact unit schema')
    rows=obj['probabilities'];need(type(rows)is list and len(rows)==len(ids)==20,'Complete activefold20 probabilities')
    got={}
    for row in rows:
        need(type(row)is dict and set(row)=={'query_id','probability'},'Exact unit row fields; fold assigned only by trusted assembler')
        q,p=row['query_id'],row['probability']
        need(type(q)is str and q in ids and q not in got,'Exact unique activefold query ID')
        need(type(p)in(int,float)and math.isfinite(p)and 0<=p<=1,'Finite probability in[0,1]')
        got[q]=p
    need(set(got)==set(ids),'All activefold IDs required')
    return [{'query_id':q,'probability':got[q]}for q in ids]


def assemble(packets,units,program_sha):
    need(len(packets)==len(units)==7,'All seven committed folds; no partial score')
    previous=None;containers=set();rows=[]
    for packet,unit in zip(packets,units):
        need(set(packet)=={'commit_bytes','output_bytes'},'Exact assembly packet')
        commit=decode(packet['commit_bytes']);body=packet['output_bytes']
        need(commit['status']=='removed_producer_output_committed'and commit['candidate_id']=='NEURAL-034'and commit['unit_id']==unit['unit_id'],'Fixed committed unit binding')
        need(commit['program_sha256']==program_sha and commit['previous_commit_sha256']==previous,'Same frozen program and contiguous commitment chain')
        need(commit['all_candidate_holder_volume_absent']is True and commit['producer_removed_before_capture']is True,'Stopped/removed boundary attestation')
        cid=commit['producer']['container_id'];need(type(cid)is str and len(cid)==64 and all(c in'0123456789abcdef'for c in cid)and cid not in containers,'Genuine unique producer container');containers.add(cid)
        need(commit['public_inputs']==unit['public_inputs'],'Exact activefold source identity')
        need(commit['output']['bytes']==len(body)and commit['output']['sha256']==hashlib.sha256(body).hexdigest(),'Immutable committed output bytes')
        typed=validate(body,unit['expected_ids'])
        rows.extend({'fold':unit['fold'],**r}for r in typed)
        previous=hashlib.sha256(packet['commit_bytes']).hexdigest()
    body=(json.dumps({'schema_version':1,'probabilities':rows},separators=(',',':'),allow_nan=False)+'\n').encode()
    need(len(body)<=MAX and len(rows)==140,'Bounded complete final JSON')
    return body
