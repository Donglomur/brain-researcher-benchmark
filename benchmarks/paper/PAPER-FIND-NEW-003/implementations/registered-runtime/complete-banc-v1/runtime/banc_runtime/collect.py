"""Complete candidate capture precedes any reference capture.

This is an ordering/identity boundary within a process, not a replacement for
external isolation, protected mounts and independently qualified references.
"""
from dataclasses import dataclass
from .codec import need, capture, parse, encode, pin, descriptor, finite_number
from .metrics import numeric_error, adjusted_rand, embedding_distances


@dataclass(frozen=True)
class Seal:
    program_identity: str
    manifest_bytes: bytes
    payloads: tuple
    identity: str
    products: tuple = ()


def validate_payload(value, panel):
    need(type(value) is dict and set(value)=={'id','kind','support','values','estimand_identity','producer_receipt'},
         'exact complete panel payload')
    need(value['id']==panel['id'] and value['kind'] in ('numeric','cluster','embedding','evidence'), 'known panel artifact')
    need(panel['kind']=='numeric' or value['kind']=='evidence',
         'qualitative/acquisition/interpretation obligations require scientific evidence review')
    need(type(value['support']) is list and value['support'] and len(set(value['support']))==len(value['support']) and
         all(type(x) is str and x for x in value['support']), 'ordered unique scientific support')
    need(type(value['estimand_identity']) is str and len(value['estimand_identity'])==64,
         'operator/annotation/units/test-family identity')
    receipt=value['producer_receipt']
    need(type(receipt) is dict and set(receipt)=={'producer','source_sha256','input_sha256','run_sha256'},
         'source/input/run producer lineage required')
    need(type(receipt['producer']) is str and receipt['producer'], 'named source producer')
    need(all(type(receipt[k]) is str and len(receipt[k])==64 for k in ('source_sha256','input_sha256','run_sha256')),
         'producer hash declarations')
    values=value['values']
    need(type(values) is list and len(values)==len(value['support']), 'complete value support')
    if value['kind']=='numeric':
        need(all(v is None or finite_number(v) for v in values), 'finite numeric values or explicit absence')
    elif value['kind']=='cluster':
        need(all(type(v) in (str,int) for v in values), 'complete discrete labels')
    elif value['kind']=='embedding':
        need(values and type(values[0]) is list and values[0] and
             all(type(v) is list and len(v)==len(values[0]) and all(finite_number(x) for x in v) for v in values),
             'complete finite embedding')
    else:
        need(all(type(v) is str and v for v in values), 'explicit evidence assertions require expert review')
    return value


GRAPH_NULL_GAP = 'original_randomized_graph_producer_unlocated'
STATES = ('produced_unqualified','required_unscorable')


def digest(value):
    need(type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value),
         'lowercase SHA256 identity')


def nonempty(value):
    return type(value) is str and bool(value.strip())


def receipt(value):
    need(type(value) is dict and set(value)=={'producer','source_sha256','input_sha256','run_sha256'},
         'exact producer receipt')
    need(nonempty(value['producer']), 'named producer')
    for k in ('source_sha256','input_sha256','run_sha256'):digest(value[k])


def validate_manifest(raw, contracts, *, program_identity, cap):
    """Complete metadata admission shared by disk capture and retained seals."""
    digest(program_identity)
    need(type(raw) is bytes and len(raw)<=cap, 'bounded immutable retained manifest')
    b=parse(raw)
    need(type(b) is dict and set(b)=={'schema','program_identity','panels','families','legacy','gates','attempts'},
         'complete whole-paper manifest fields')
    need(b['schema']=='banc_complete_output_v2' and b['program_identity']==program_identity,
         'independently selected programme identity and exact output schema')
    definitions=(('panels',contracts['OBLIGATIONS']['rows'],'id'),
                 ('families',contracts['WORKFLOW']['families'],'id'),
                 ('legacy',contracts['WORKFLOW']['legacy_entries'],'entry'),
                 ('gates',contracts['GATES']['gates'],'id'))
    for name,expected,key in definitions:
        rows=b[name]
        need(type(rows) is list and len(rows)==len(expected) and
             all(type(row) is dict for row in rows) and
             tuple(row.get('id') for row in rows)==tuple(row[key] for row in expected),
             'complete ordered '+name+' obligations')
    paths=set()
    def admit_descriptor(value):
        d=descriptor(value)
        need(0<d['bytes']<=cap and d['path'] not in paths, 'bounded unique product/panel descriptor')
        paths.add(d['path'])
    for row,definition in zip(b['panels'],contracts['OBLIGATIONS']['rows']):
        need(set(row)=={'id','family','state','payload','reason'} and row['family']==definition['workflow_family'],
             'exact panel identity/family')
        need(row['state'] in STATES, 'legal panel state')
        if row['state']=='required_unscorable':
            need(row['payload'] is None and nonempty(row['reason']), 'panel absence disposition')
        else:
            need(row['reason'] is None, 'produced panel has no missing reason')
            admit_descriptor(row['payload'])
    for kind,definitions in (('families',contracts['WORKFLOW']['families']),
                             ('legacy',contracts['WORKFLOW']['legacy_entries'])):
        for row,definition in zip(b[kind],definitions):
            fields={'id','state','products','reason','gap_code'}
            if kind=='legacy':fields.add('family')
            need(set(row)==fields and row['state'] in STATES, 'exact '+kind+' disposition schema')
            if kind=='legacy':need(row['family']==definition['mapped_family'], 'legacy source family')
            need(type(row['products']) is list, 'explicit full product list')
            if row['state']=='required_unscorable':
                need(not row['products'] and nonempty(row['reason']) and nonempty(row['gap_code']),
                     'missing family/legacy product requires a named gap')
            else:
                need(row['products'] and row['reason'] is None and row['gap_code'] is None,
                     'produced family/legacy needs actual complete product descriptors')
                names=[]
                for product in row['products']:
                    need(type(product) is dict and set(product)=={'id','payload'}, 'exact product descriptor')
                    name=product['id']
                    need(type(name) is str and 1<=len(name)<=120 and
                         all(c.isascii() and (c.isalnum() or c in '._-') for c in name), 'ordinary product ID')
                    names.append(name);admit_descriptor(product['payload'])
                need(len(names)==len(set(names)), 'unique family/legacy product IDs')
                if kind=='families':
                    need(all(p['state']=='produced_unqualified' for p in b['panels'] if p['family']==row['id']),
                         'produced family cannot conceal a missing required panel')
            if kind=='legacy' and row['id']=='randomized_graph_null_ensemble':
                need(row['state']=='required_unscorable' and row['gap_code']==GRAPH_NULL_GAP,
                     'unlocated original graph null must remain required_unscorable')
    for row in b['gates']:
        need(set(row)=={'id','state','reason'} and row['state']=='open' and nonempty(row['reason']),
             'all16 exact scientific gates remain open with reasons')
    need(type(b['attempts']) is list and b['attempts'], 'whole attempt/failure records')
    ids=[]
    for row in b['attempts']:
        need(type(row) is dict and set(row)=={'id','exit_code','wall_seconds','peak_rss_bytes','output_bytes','failure'},
             'exact attempt receipt')
        need(nonempty(row['id']) and type(row['exit_code']) is int, 'attempt identity/natural completion')
        need(finite_number(row['wall_seconds']) and row['wall_seconds']>=0 and
             all(type(row[k]) is int and row[k]>=0 for k in ('peak_rss_bytes','output_bytes')), 'whole attempt costs')
        need((row['exit_code']==0 and row['failure'] is None) or
             (row['exit_code']!=0 and nonempty(row['failure'])), 'failure/completion agreement')
        ids.append(row['id'])
    need(len(ids)==len(set(ids)), 'unique attempt identities')
    return b


def product_slots(bundle):
    return tuple((kind+':'+row['id']+':'+product['id'],kind,row['id'],product)
                 for kind in ('families','legacy') for row in bundle[kind] for product in row['products'])


def validate_product(raw, slot):
    key,kind,owner,descriptor_row=slot
    value=parse(raw)
    need(type(value) is dict and set(value)=={'schema','kind','owner','id','producer_receipt','support','content'},
         'exact source product body')
    need(value['schema']=='banc_complete_family_product_v1' and value['kind']==kind and
         value['owner']==owner and value['id']==descriptor_row['id'], 'product body/obligation identity')
    receipt(value['producer_receipt'])
    need(type(value['support']) is list and value['support'] and all(nonempty(x) for x in value['support']) and
         len(value['support'])==len(set(value['support'])), 'complete declared product support')
    need(type(value['content']) is dict and value['content'], 'actual source product content')
    # Safe encoding rejects nonfinite floats parsed from e.g. 1e309 as well.
    encode(value)


def seal_identity(raw, payloads, products):
    return pin(encode({'manifest':pin(raw),
        'payloads':[(k,None if v is None else pin(v)) for k,v in payloads],
        'products':[(k,pin(v)) for k,v in products]}))['sha256']


def admit_retained(raw, payloads, products, contracts, *, program_identity, cap):
    """No file operation: admit the complete retained closure, not just hashes."""
    b=validate_manifest(raw,contracts,program_identity=program_identity,cap=cap)
    need(type(payloads) is tuple and len(payloads)==len(b['panels']) and
         all(type(x) is tuple and len(x)==2 for x in payloads), 'immutable complete panel bodies')
    def body_pin(body,d):
        need(type(body) is bytes and len(body)<=cap and pin(body)=={'bytes':d['bytes'],'sha256':d['sha256']},
             'retained body exactly joins its manifest descriptor')
    for (name,body),row,panel in zip(payloads,b['panels'],contracts['OBLIGATIONS']['rows']):
        need(name==row['id'], 'retained panel order')
        if row['state']=='required_unscorable':need(body is None, 'absent disposition/body agreement')
        else:
            body_pin(body,row['payload']);value=validate_payload(parse(body),panel)
            digest(value['estimand_identity']);receipt(value['producer_receipt']);encode(value)
    slots=product_slots(b)
    need(type(products) is tuple and len(products)==len(slots) and
         all(type(x) is tuple and len(x)==2 for x in products), 'immutable complete family/legacy bodies')
    for (name,body),slot in zip(products,slots):
        need(name==slot[0], 'retained product order')
        body_pin(body,slot[3]['payload']);validate_product(body,slot)
    return b


def capture_bundle(root, declared, contracts, *, program_identity, meter, cap=1048576):
    raw=capture(root,declared,cap=cap,meter=meter)
    b=validate_manifest(raw,contracts,program_identity=program_identity,cap=cap)
    payloads=tuple((row['id'],None if row['state']=='required_unscorable' else
                    capture(root,row['payload'],cap=cap,meter=meter)) for row in b['panels'])
    products=tuple((slot[0],capture(root,slot[3]['payload'],cap=cap,meter=meter)) for slot in product_slots(b))
    admit_retained(raw,payloads,products,contracts,program_identity=program_identity,cap=cap)
    return Seal(program_identity,raw,payloads,seal_identity(raw,payloads,products),products)


def compare_sealed(candidate, reference_root, reference_descriptor, contracts, *, program_identity, meter, cap=1048576):
    need(type(candidate) is Seal, 'fully admitted immutable candidate seal required')
    digest(program_identity)
    need(candidate.program_identity==program_identity, 'candidate binds independently selected programme')
    admit_retained(candidate.manifest_bytes,candidate.payloads,candidate.products,contracts,
                   program_identity=program_identity,cap=cap)
    need(seal_identity(candidate.manifest_bytes,candidate.payloads,candidate.products)==candidate.identity,
         'candidate seal identity')
    reference=capture_bundle(reference_root,reference_descriptor,contracts,
                             program_identity=program_identity,meter=meter,cap=cap)
    results=[]
    for (name,craw),(_,rraw) in zip(candidate.payloads,reference.payloads):
        if craw is None or rraw is None:
            results.append({'id':name,'state':'required_unscorable','reason':'candidate or independent reference absent'})
            continue
        c=parse(craw);r=parse(rraw)
        need(c['kind']==r['kind'] and c['support']==r['support'] and
             c['estimand_identity']==r['estimand_identity'], 'complete fixed estimand/support equality:'+name)
        if c['kind']=='numeric':
            cm=tuple(v is not None for v in c['values']);rm=tuple(v is not None for v in r['values'])
            need(cm==rm, 'observed support mask equality:'+name)
            if not any(cm):
                results.append({'id':name,'state':'required_unscorable','reason':'no observed numeric support'})
                continue
            metric=numeric_error(tuple(v for v in c['values'] if v is not None),
                                 tuple(v for v in r['values'] if v is not None),meter)
        elif c['kind']=='cluster':
            metric={'adjusted_rand':adjusted_rand(tuple(c['values']),tuple(r['values']),meter)}
        elif c['kind']=='embedding':
            metric=numeric_error(embedding_distances(tuple(map(tuple,c['values'])),meter),
                                 embedding_distances(tuple(map(tuple,r['values'])),meter),meter)
        else: metric={'state':'requires_independent_scientific_review','automatic_credit':False}
        results.append({'id':name,'state':'compared_unqualified','metric':metric})
    return {'candidate_seal':candidate.identity,'reference_seal':reference.identity,
            'panels':results,'biological_units':1,'scientific_qualification':False,
            'reference_qualification_external_required':True,'success_threshold_selected':False,
            'whole_attempt_costs':meter.report()}
