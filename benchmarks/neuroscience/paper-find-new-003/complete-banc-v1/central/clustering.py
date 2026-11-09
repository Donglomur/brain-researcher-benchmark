"""Source-owned pre-label quantities are the only fresh clustering scores.

The four primary panel measurements are explicit. Full PCA/preprocessing,
partition/embedding products remain in mandatory pre-label D09/D13 family
products. Other original panels/consumers retain their fixed-annotation or
other-original-quantity regime; they cannot claim fresh cluster/embedding credit.
"""
from banc_runtime.codec import need,encode,parse,pin
from banc_runtime.collect import validate_payload,admit_retained,product_slots
from .io import exact_fields,read,write,digest

MAP={'F3d':('an_dn_partition','cluster','D09'),
     'ED6a':('an_dn_embedding','embedding','D09'),
     'F6a':('cns_partition','cluster','D13'),
     'ED10a':('cns_embedding','embedding','D13')}
POLICY={'schema':'banc_source_owned_prelabel_binding_v2',
 'fresh_panels':{p:{'quantity':q,'kind':kind,'family':family} for p,(q,kind,family) in MAP.items()},
 'fresh_family_product_id':'prelabel-clustering','fresh_family_product_owners':['D09','D13'],
 'other_panels':'fixed_original_annotations_or_other_original_quantities_not_fresh_clustering',
 'qualitative_embedding_views':'must retain the prelabel embedding identity; evidence still requires independent scientific review',
 'required_full_family_products':'Complete original PCA/preprocessing/partition/embedding products remain required; no sampling or family-scope reduction.'}

def policy_identity():return pin(encode(POLICY))['sha256']

def artifact(raw,contracts,program_identity):
    doc=parse(raw);exact_fields(doc,('schema','program_identity','quantities','family_products'),'complete prelabel artifact')
    need(doc['schema']=='banc_complete_prelabel_artifact_v2' and doc['program_identity']==program_identity,'prelabel programme identity')
    need(type(doc['quantities']) is dict and set(doc['quantities'])=={v[0] for v in MAP.values()},'all four complete fresh quantities')
    need(type(doc['family_products']) is dict and set(doc['family_products'])=={'D09','D13'},'full original fresh family products')
    panels={x['id']:x for x in contracts['OBLIGATIONS']['rows']}
    receipt={'producer':'prelabel-artifact-validation-only','source_sha256':'0'*64,'input_sha256':'0'*64,'run_sha256':pin(raw)['sha256']}
    for panel,(quantity,kind,family) in MAP.items():
        need(panels[panel]['workflow_family']==family,'source-owned original panel family')
        q=doc['quantities'][quantity];exact_fields(q,('state','kind','support','values','estimand_identity','reason'),'prelabel quantity')
        need(q['kind']==kind,'source-owned fresh quantity kind')
        if q['state']=='required_unscorable':
            need(q['support']==[] and q['values']==[] and q['estimand_identity'] is None and type(q['reason']) is str and q['reason'],'explicit missing complete fresh quantity')
        else:
            need(q['state']=='produced_unqualified' and q['reason'] is None,'unqualified complete prelabel quantity')
            validate_payload({'id':panel,**{k:q[k] for k in ('kind','support','values','estimand_identity')},'producer_receipt':receipt},panels[panel]);digest(q['estimand_identity'])
    for family,product in doc['family_products'].items():
        exact_fields(product,('state','support','content','reason'),'complete prelabel family product')
        if product['state']=='required_unscorable':need(product['support']==[] and product['content']=={} and type(product['reason']) is str and product['reason'],'explicit missing fresh family')
        else:need(product['state']=='produced_unqualified' and product['reason'] is None and type(product['support']) is list and product['support'] and len(set(product['support']))==len(product['support']) and all(type(x) is str and x for x in product['support']) and type(product['content']) is dict and product['content'],'complete full family product')
    encode(doc);return doc

def capture_prelabel(root,d,inventory,contracts,program_identity,meter,cap):
    need(inventory.get(d['path'])==d,'prelabel artifact belongs to frozen complete first-phase inventory')
    raw=read(root,d,meter,cap);artifact(raw,contracts,program_identity)
    return {'descriptor':d,'artifact_identity':pin(raw),'phase_inventory_identity':pin(encode(inventory))['sha256'],
      'source_owned_policy_sha256':policy_identity(),'program_identity':program_identity}

def bind(candidate,raw,phase,contracts,program_identity,fixed_annotation_bindings,cap):
    # Complete candidate admission must have happened before this source-owned
    # semantic join; no candidate producer string can substitute for it.
    bundle=admit_retained(candidate.manifest_bytes,candidate.payloads,candidate.products,contracts,program_identity=program_identity,cap=cap)
    original=artifact(raw,contracts,program_identity)
    need(pin(raw)==phase['artifact_identity'] and phase['source_owned_policy_sha256']==policy_identity() and phase['program_identity']==program_identity,'exact original prelabel artifact and owned policy')
    rows={r['id']:r for r in bundle['panels']};bodies=dict(candidate.payloads);bindings=[]
    for panel,(quantity,kind,family) in MAP.items():
        q=original['quantities'][quantity];row=rows[panel]
        need(row['state']==q['state'],'downstream cannot replace an absent prelabel quantity:'+panel)
        if q['state']=='produced_unqualified':
            value=parse(bodies[panel])
            need(all(value[k]==q[k] for k in ('kind','support','values','estimand_identity')),'post-label fresh quantity substitution:'+panel)
        bindings.append({'panel':panel,'quantity':quantity,'state':q['state'],'prelabel_quantity_sha256':pin(encode(q))['sha256']})
    for panel,body in candidate.payloads:
        if body is not None and panel not in MAP:need(parse(body)['kind'] not in ('cluster','embedding'),'fresh clustering/embedding credit restricted to source-owned prelabel map')
    products={key:parse(raw_product) for key,raw_product in candidate.products}
    familyrows={r['id']:r for r in bundle['families']}
    for family in ('D09','D13'):
        original_product=original['family_products'][family]
        if familyrows[family]['state']=='produced_unqualified':
            need(original_product['state']=='produced_unqualified','missing prelabel family cannot become a produced family after labels')
            key='families:'+family+':prelabel-clustering';need(key in products,'produced family must retain full original prelabel product')
            need(products[key]['support']==original_product['support'] and products[key]['content']==original_product['content'],'prelabel full family product substitution')
    proof={'schema':'banc_scored_prelabel_binding_v2','policy_sha256':policy_identity(),'candidate_seal':candidate.identity,
      'artifact_identity':pin(raw),'cluster_phase_inventory_identity':phase['phase_inventory_identity'],
      'downstream_phase_inventory_identity':phase['downstream_phase_inventory_identity'],'panel_bindings':bindings,
      'fixed_original_annotation_bindings':fixed_annotation_bindings,'fixed_regime_sha256':pin(encode({'policy':POLICY,'fixed':fixed_annotation_bindings}))['sha256'],
      'qualitative_or_derived_claims_automatically_qualified':False,'scientific_qualification':False}
    return proof
