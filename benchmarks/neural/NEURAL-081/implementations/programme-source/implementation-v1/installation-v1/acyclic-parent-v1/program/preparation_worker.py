"""Ten-worker G0 composition; full protected assembly belongs to worker ten."""
from pathlib import Path
import common as c
import protocol as p
import preparation

def execute(request,access,source,output):
    c.exact(request,('schema','task_id','ordinal','person','source','generation','inventory','release_root','raw_files','key','protocol_source','annotation_authority','environment','release_receipt','earlier_people','output_root'))
    c.need(request['schema']=='neural081_G0_request_v1'and request['task_id']==c.TASK and access.role=='G0'and c.typed_equal(request['source'],source),'explicit exact trusted preparation source/role')
    ordinal=c.integer(request['ordinal'],0,9);person=c.PEOPLE[ordinal]
    c.need(request['person']==person and str(output)==request['output_root'],'exact original person worker/output')
    c.need(type(request['raw_files'])is list and len(request['raw_files'])==11,'all selected raw-release file descriptors')
    inventory=access.json(request['inventory']);raw_files=request['raw_files'];root=c.absolute(request['release_root'])
    c.need([Path(d['path']).name for d in raw_files]==[x+'-raw.fif'for x in c.PEOPLE]+['README.md']and all(Path(d['path']).parent==root for d in raw_files),'exact original release location/order')
    for d in raw_files:c.descriptor(d)
    generation=c.pin(c.encoded({'schema':'neural081_generation_v1','raw_files':raw_files,'inventory':request['inventory'],'key_descriptor':request['key'],'protocol_source':request['protocol_source'],'annotation_authority':request['annotation_authority']}))['sha256']
    c.need(generation==request['generation'],'source-owned complete prepared generation')
    if ordinal==0:
        c.need(request['release_receipt']is None and request['earlier_people']==[],'first source verification has no fabricated predecessor')
        for d in raw_files:access.admit(d)
        actual=preparation.verify_release(root,inventory,access.budget);c.need(c.typed_equal(actual,raw_files),'all actual torrent/file identities match selected complete release')
        release=c.publish_json(output/'RELEASE.json',{'schema':'neural081_verified_release_v1','source':source,'generation':generation,'files':actual,'inventory':request['inventory'],'all3336pieces':True,'actual_complete_read':True},access.budget)
    else:
        release=request['release_receipt'];r=access.json(release);c.exact(r,('schema','source','generation','files','inventory','all3336pieces','actual_complete_read'))
        c.need(r['schema']=='neural081_verified_release_v1'and c.typed_equal(r['source'],source)and r['generation']==generation and c.typed_equal(r['files'],raw_files)and c.typed_equal(r['inventory'],request['inventory'])and r['all3336pieces']is True and r['actual_complete_read']is True,'same first-worker complete release closure')
        access.admit(raw_files[ordinal])
    key=access.read(request['key']);c.need(len(key)==32,'exact private32-byte identity key in G0 only')
    person_result=preparation.prepare_person(person,raw_files[ordinal],key,generation,output/'person',access.budget,request['environment'])
    result={'schema':'neural081_G0_result_v1','ordinal':ordinal,'person':person,'source':source,'generation':generation,'release_receipt':release,'person_protected':person_result,'complete_preparation':None}
    if ordinal==9:
        c.need(type(request['earlier_people'])is list and len(request['earlier_people'])==9,'worker ten alone gets complete prior nine protected person artifacts')
        previous=[]
        for expected,row in zip(c.PEOPLE[:9],request['earlier_people']):
            c.exact(row,('person','protected'));c.need(row['person']==expected,'exact original preceding person order');access.admit(row['protected']);previous.append(row['protected'])
        result['complete_preparation']=preparation.assemble([*previous,person_result],key,generation,output/'complete',request['protocol_source'],[request['inventory']],request['annotation_authority'],access.budget)
    else:c.need(request['earlier_people']==[],'no unrelated protected label roles in earlier preparers')
    del key;access.budget.check_clock();return c.publish_json(output/'RESULT.json',result,access.budget)
