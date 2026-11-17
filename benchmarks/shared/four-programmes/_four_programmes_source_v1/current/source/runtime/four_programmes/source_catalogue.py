"""Actual fixed-source inspection, without original module/import execution.

This is an engineering source inspection, never Context/runtime admission.
The two held N098 bodies are excluded before any filesystem operation. The
remaining ordinary sources and all selected API ASTs are captured in full.
"""
import ast
import hashlib
from .common import Store,need,encode,pin,descriptor,integer,bounded_size
from .catalog_pins import CATALOG
from .schema_pins import SCHEMA_TABLE
from .schema import Schemas

HELD=(
 {"path":"authoring/delivery-20261105/neural098/public/COHORT.json","bytes":647,
  "sha256":"b6961cd0331ac924e193a7d2e8df41a79524294d2a1666cd650e15b58cc710f9"},
 {"path":"authoring/delivery-20261105/neural098/public/source/phase3.txt","bytes":453,
  "sha256":"c56cb6c695e6df3594b78c383eafee8c6de47cd8d173134708b7c774c232bd8a"},
)
LABELS={"NEURAL-056":"NEURAL-056","PAPER-FIND-050":"CriticalInit",
        "PAPER-paper-method-replacement-016":"Hundred Models","NEURAL-098":"NEURAL-098"}
ROLE_COUNTS={"NEURAL-056":46,"CriticalInit":72,"Hundred Models":88,"NEURAL-098":60}

def fixed_tables(runtime_store):
    need(type(runtime_store) is Store,"actual anchored source metadata store")
    catalog=runtime_store.document(CATALOG,CATALOG['bytes'])
    tables=runtime_store.document(SCHEMA_TABLE,SCHEMA_TABLE['bytes'])
    need(type(catalog) is dict and set(catalog['programmes'])==set(LABELS),"all four fixed programmes")
    need(len(catalog['original_roles'])==266 and len(catalog['APIs'])==47,"complete fixed source catalogue")
    held=[{k:r['original'][k]for k in ('path','bytes','sha256')}for r in catalog['held']]
    need(held==list(HELD) and all(r['status']=='descriptor_only_no_body_access'for r in catalog['held']),
         "exact two historical held identities; no body-based verification")
    return catalog,Schemas(tables)

def inspect_original_sources(*,repo, runtime_store, meter, programmes=None):
    """Authenticate entire selected ordinary bodies and fixed API joins.

    No accepted request, source inspection report, file hash or AST matching
    grants scientific execution. Original importers/resolvers are never run.
    """
    catalog,schemas=fixed_tables(runtime_store)
    selected=tuple(LABELS) if programmes is None else tuple(programmes)
    need(selected and len(set(selected))==len(selected) and set(selected)<=set(LABELS),
         "explicit whole canonical programme selection")
    labels={LABELS[p]for p in selected};held={r['path']:r for r in HELD}
    originals=Store(repo,meter,forbidden=held)
    bodies={};trees={};rows=[];deferred=[];counts=dict.fromkeys(labels,0)
    try:
        for row in catalog['original_roles']:
            if row['programme'] not in labels:continue
            counts[row['programme']]+=1
            d={k:row[k]for k in ('path','bytes','sha256')};descriptor(d)
            need(d['path'] not in bodies and d['path'] not in {x['path']for x in deferred},
                 "one complete original source role per exact path")
            if row['body_authenticated'] is False:
                need(held.get(d['path'])==d,"only exact held source identities may remain unopened")
                deferred.append(d);continue
            need(row['body_authenticated'] is True and d['path'] not in held,
                 "held identity cannot be promoted by a source role flag")
            # The selected original extent is reserved before any read. These
            # are ordinary source bodies, not authentic data or model artifacts.
            meter.charge('retained_bytes',d['bytes']+1)
            raw=originals.read(d,d['bytes']+1)
            bodies[d['path']]=raw;rows.append(d)
            if d['path'].endswith('.py'):
                meter.charge('work_units',64*len(raw)+4096)
                meter.charge('retained_bytes',32*len(raw)+4096)
                trees[d['path']]=ast.parse(raw,filename=d['path'])
        need(all(counts[label]==ROLE_COUNTS[label]for label in labels),"no omitted source/parent role")
        api_rows=[]
        for name,a in catalog['APIs'].items():
            if a['path'] not in bodies:continue
            d={k:a[k]for k in ('path','bytes','sha256')}
            need(pin(bodies[a['path']])=={k:d[k]for k in ('bytes','sha256')},"API joins exact selected original bytes")
            result={'name':name,'source':d,'definition':a.get('definition'),'AST_sha256':a.get('AST_sha256')}
            if 'AST_sha256'in a:
                need(a['path'] in trees,"fixed source-owned Python API")
                nodes=[n for n in ast.walk(trees[a['path']])if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))
                       and n.lineno==a['line']and n.end_lineno==a['end_line']]
                need(len(nodes)==1,"exact original API source span")
                dumped=ast.dump(nodes[0],include_attributes=False).encode()
                meter.charge('work_units',len(dumped)+4096);meter.charge('retained_bytes',len(dumped))
                need(hashlib.sha256(dumped).hexdigest()==a['AST_sha256'],"exact original API AST")
            api_rows.append(result)
        if selected==tuple(LABELS):
            need(len(rows)==264 and len(deferred)==2 and len(api_rows)==47 and len(trees)==175,
                 "whole four-programme original source and API coverage")
        meter.check()
        return {'schema':'four_original_source_inspection_v1','catalogue':CATALOG,'schemas':SCHEMA_TABLE,
                'programmes':list(selected),'ordinary_sources':rows,'held_descriptor_only':deferred,
                'source_roles':counts,'Python_ASTs_parsed':len(trees),'APIs':api_rows,
                'original_modules_imported':False,'held_bodies_opened':False,
                'Context_admission':False,'scientific_execution_authorized':False,
                'costs':meter.record()}
    except BaseException as error:
        meter.own_error(error,'original_source_inspection');raise
    finally:
        # Retained logical reservations are deliberately not refunded. Actual
        # owned source/AST objects can be released without resetting history.
        trees.clear();bodies.clear()
