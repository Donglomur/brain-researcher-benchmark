"""Separate full-output collector; the accepted legacy2MiB route is unchanged."""
from .strict import require,integer,decode,digest,canonical_bytes
from .collection import admitted_observation
from .arrays import descriptor,validate_stream
from .views import verify_tree
from scientific.json_extent import require_json_product

def collect_full(root,job,condition,observation,*,clock):
    require(job['route']=='prospective_full_scientific_source_v1','separate selected full-source route')
    contract=job['output_contract'];limits=job['producer_limits'];meta=job['metadata_limits']
    for key in('receipt_bytes','json_member_bytes','invocation_bytes'):integer(meta[key],key,1)
    total=integer(limits['output_bytes'],'whole scientific output cap',1)
    require(meta['receipt_bytes']<=meta['json_member_bytes']<=total,'complete metadata limits')
    raw=root.read('result.json',meta['receipt_bytes'],clock=clock);receipt=decode(raw)
    require(receipt.get('schema')=='jaxley_complete_job_output_v1','actual producer receipt')
    effective={**job,'contract_sha256':digest(canonical_bytes(contract))}
    admitted_observation(observation,effective,condition,receipt)
    require(receipt['native_qualification']is False,'child cannot self-issue native qualification')
    expected={r['artifact_id']:r for r in contract['outputs']};rows=receipt['artifacts']
    require(len(rows)==len(expected)and [r['artifact_id']for r in rows]==list(expected),'whole ordered product roster')
    for row in rows:
        wanted=expected[row['artifact_id']]
        for key in('format','dtype','shape','axes','unit','semantic_role','lineage','native_source_pin','extent'):
            require(row[key]==wanted[key],'full source/coordinate/product binding: '+key)
        require(row['bytes']<=wanted['extent']['bytes'],'actual whole product exceeds selected bound')
        if wanted['extent']['kind']=='exact':require(row['bytes']==wanted['extent']['bytes'],'whole output extent changed')
        if row['format']=='json':require(row['bytes']<=meta['json_member_bytes'],'whole JSON extent exceeds explicit limit')
    own={'path':'result.json','bytes':len(raw),'sha256':digest(raw)}
    inventory=verify_tree(root,[own,*rows],byte_cap=total,file_cap=len(rows)+1,clock=clock)
    reads=len(raw)+inventory['authenticated_bytes']
    for row in rows:
        if row['format']=='json':
            body=decode(root.read(row['path'],meta['json_member_bytes'],pin=row,clock=clock));reads+=row['bytes']
            require_json_product(body,expected[row['artifact_id']])
            for unit in job['unit_inverse']:
                selected=unit['product_coordinates'][row['artifact_id']]['selection']
                if selected['kind']!='json_path':continue
                node=body
                for part in selected['path']:
                    require(type(node)is dict and type(part)is str and part in node or type(node)is list and type(part)is int and 0<=part<len(node),'unit inverse absent in actual JSON product')
                    node=node[part]
        else:descriptor(row);reads+=validate_stream(root,row,clock=clock,byte_cap=total)['bytes']
    return {'schema':'jaxley_full_scientific_collection_v1','job_id':job['job_id'],'group':job['group'],'condition':condition,
            'artifacts':rows,'receipt_pin':own,'complete':True,'read_bytes':reads,'output_bytes':inventory['authenticated_bytes'],
            'method_operations':receipt['method_operations'],
            'original_observation':observation['observation_record'],'original_units':job['original_units'],'unit_inverse':job['unit_inverse'],
            'qualified_as_scientific_benchmark':False,'source_only_collection_does_not_close_gates':True}
