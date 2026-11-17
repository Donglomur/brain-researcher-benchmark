"""Typed, bounded native arguments; authenticated numeric leaves, never pickle.

The selection's native_abi_jobs is controller-owned and authenticated by the
existing outer selection. A job cannot expand that authority. Construction is
separate from author imports, so the real ABI can be checked without running them.
"""
from .custody import need, read_pin, parse, descriptor
from .guard import integer, real
from .preparation import read_npz

def construct(root, job_id, request, selected_jobs, budget):
    import numpy as np
    need(type(selected_jobs)is dict and job_id in selected_jobs,'controller-selected native ABI job')
    selected=selected_jobs[job_id]
    need(request==selected['request'],'exact selected argument tree and schema')
    need(type(request)is dict and set(request)=={'version','tree','schema'},'exact nested ABI request')
    need(request['version']=='critical-init-nested-native-abi-v1','explicit nested ABI version')
    limits=selected['limits']
    for k in ('nodes','depth','string_bytes','array_bytes','bundle_bytes','metadata_bytes'):
        integer(limits[k],1)
    need(limits['depth']<=64 and limits['nodes']<=100000,'hard constructor recursion/node cap')
    bundles=selected['bundles'];used=set();nodes=0;array_bytes=0
    def inspect(node,schema,depth):
        nonlocal nodes,array_bytes
        nodes+=1;need(nodes<=limits['nodes'] and depth<=limits['depth'],'bounded complete argument tree')
        need(type(node)is dict and type(schema)is dict and node.get('type')==schema.get('type'),'typed argument/schema agreement')
        t=node['type']
        if t=='scalar':
            need(set(node)=={'type','value'}and set(schema)=={'type','python_type'},'exact scalar schema')
            value=node['value'];name=type(value).__name__
            need(name==schema['python_type'] and name in ('NoneType','bool','int','float','str'),'exact scalar type')
            if name=='float':real(value)
            if name=='int':need(value.bit_length()<=64,'bounded scalar integer')
            if name=='str':need(len(value.encode('utf8'))<=limits['string_bytes'] and '\0'not in value,'bounded ordinary scalar string')
        elif t in ('dict','list','tuple'):
            need(set(node)==set(schema)=={'type','items'},'exact container schema')
            x=node['items'];s=schema['items']
            if t=='dict':
                need(type(x)is type(s)is dict and set(x)==set(s),'complete original dictionary keys')
                need(all(type(k)is str and len(k.encode('utf8'))<=limits['string_bytes']for k in x),'bounded dictionary keys')
                for k in x:inspect(x[k],s[k],depth+1)
            else:
                need(type(x)is type(s)is list and len(x)==len(s),'complete original sequence length')
                for a,b in zip(x,s):inspect(a,b,depth+1)
        elif t=='array':
            need(set(node)=={'type','bundle','member'}and set(schema)=={'type','shape','dtype'},'explicit array leaf schema')
            need(type(node['bundle'])is str and type(node['member'])is str and node['bundle']in bundles,'selected numeric bundle')
            bundle=bundles[node['bundle']];member=node['member']
            need(bundle['role']in ('public_input','prepared_input','native_output'),'no candidate or protected evaluator target in native arguments')
            need(member in bundle['schema'] and bundle['schema'][member]=={'shape':schema['shape'],'dtype':schema['dtype']},'full leaf shape/dtype binding')
            shape=schema['shape'];need(type(shape)is list and len(shape)<=32,'bounded numeric rank')
            count=1
            for n in shape:integer(n,0);count*=n
            dtype=np.dtype(schema['dtype']);need(dtype.kind in 'biufc'and dtype.str==schema['dtype'],'nonobject canonical dtype')
            array_bytes+=count*dtype.itemsize
            need(array_bytes<=limits['array_bytes'],'bounded independent mutable array leaves')
            descriptor(bundle['pin'],limits['bundle_bytes']);descriptor(bundle['producer'],limits['metadata_bytes'])
            used.add(node['bundle'])
        else:raise ValueError('unknown native argument node')
    inspect(request['tree'],request['schema'],0)
    need(request['tree']['type']=='dict','native call argument dictionary')
    need(used==set(bundles),'no unused or hidden native input bundle')
    # Admit roles, whole tree, producer identities and all schemas before decoding.
    for name in sorted(used):
        bundle=bundles[name]
        producer=parse(read_pin(root,bundle['producer'],limits['metadata_bytes'],budget))
        need(type(producer)is dict and producer.get('issuer')=='qualified_controller'
             and producer.get('complete')is True and producer.get('role')==bundle['role']
             and producer.get('output')==bundle['pin'],'authenticated complete source producer and exact output identity')
        need(producer.get('scientific_identity')==bundle['scientific_identity'] and bool(bundle['scientific_identity']),
             'qualified original input identity; no guessed data lineage')
    loaded={};reservations=[];leaf_reserved=False
    try:
        budget.reserve_array(array_bytes);leaf_reserved=True
        for name in sorted(used):
            bundle=bundles[name]
            arrays,reserved=read_npz(root,bundle['pin'],bundle['schema'],budget,limits['bundle_bytes'])
            loaded[name]=arrays;reservations.append(reserved)
        def hydrate(node):
            t=node['type']
            if t=='scalar':return node['value']
            if t=='array':return loaded[node['bundle']][node['member']].copy()
            if t=='dict':return {k:hydrate(v)for k,v in node['items'].items()}
            result=[hydrate(v)for v in node['items']]
            return tuple(result)if t=='tuple'else result
        arguments=hydrate(request['tree'])
        loaded.clear();arrays=None
        while reservations:budget.release_array(reservations.pop())
        return arguments,array_bytes
    except BaseException as original:
        loaded.clear();arrays=None
        releases=reservations+([array_bytes]if leaf_reserved else[])
        for reserved in releases:
            try:budget.release_array(reserved)
            except BaseException as cleanup:original.add_note('native ABI cleanup: '+type(cleanup).__name__)
        raise
