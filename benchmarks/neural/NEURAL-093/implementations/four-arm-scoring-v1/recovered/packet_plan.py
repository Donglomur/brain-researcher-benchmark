"""Complete312 operator-only packet plan from fixed source metadata.

No file bodies are copied or decoded here. The protected SESSION descriptor is
kept outside candidate packet descriptors. Historical original paths are never
used as read locations; only exact export inventory targets are admissible.
"""
from pathlib import PurePosixPath
from deps import load

D=load(); c=D['controls']; m=D['comparison']
EXPORT_ROOT='authoring/delivery-20261105/common/exports/neural093/'

def prepare(original_raw,binding_raw,contexts_raw,export_raw):
    binding=c.load_binding(binding_raw)
    for raw,name in ((contexts_raw,'contexts_metadata'),(export_raw,'export')):
        c.need(c.pin(raw)=={k:binding[name][k] for k in ('bytes','sha256')},'exact export/contexts metadata before parsing')
    panel=c.prepare_panel(original_raw,binding_raw)
    return panel,_plan(panel,binding,c.parse(contexts_raw,600000),c.parse(export_raw,300000))

def _plan(panel,binding,contexts,export):
    """Internal pure planner; caller authenticates all three metadata sources."""
    sessions=m._scope(panel)
    c.need(contexts['task_id']=='NEURAL-093' and contexts['required_sessions']==39
        and contexts['required_mice']==10 and contexts['required_queries']==2042
        and contexts['all_contexts_operator_private'] is True,'complete protected contexts')
    c.need(len(contexts['sessions'])==39,'all39 context rows')
    inventory={}
    for row in export['files']:
        target=row['target']; p=PurePosixPath(target)
        c.need(type(target)is str and not p.is_absolute() and '..' not in p.parts
            and str(p)==target and target not in inventory,'canonical unique export member')
        inventory[target]=row
    c.need(len(inventory)==614,'exact complete614 export inventory')
    def join(row):
        c.need(type(row)is dict and set(row)=={'target','original'},'exact original/export join')
        target=row['target']; orig=row['original']; found=inventory.get(target)
        c.need(found is not None and all(found[k]==orig[k] for k in ('bytes','sha256')),'descriptor matches complete export inventory')
        return dict(path=EXPORT_ROOT+target,bytes=orig['bytes'],sha256=orig['sha256'])
    result=[]
    total=0
    for s,ctx,b in zip(sessions,contexts['sessions'],binding['roster']):
        c.need(all(s[k]==ctx[k]==b[k] for k in ('ordinal','session','mouse')),'ordered source session/mouse identity')
        c.need(set(ctx['contexts'])==set(c.ORIGINAL_ARMS),'both original arm contexts')
        packets={}
        for arm in c.ARMS:
            packets[arm]={}
            donor=arm if arm in c.ORIGINAL_ARMS else c.ORIGINAL_ARMS[1]
            for phase in c.PHASES:
                original=ctx['contexts'][donor][phase]
                original_manifest=join(original['manifest'])
                c.need(original_manifest==b['original_manifests'][donor][phase],'source manifest descriptor join')
                raw=(s['original_manifest_bytes'] if arm in c.ORIGINAL_ARMS else s['control_manifest_bytes'])[arm][phase]
                doc=c.parse(raw,c.MAX_MANIFEST)
                files={}
                for name,desc in doc['files'].items():
                    found=join(original['files'][name])
                    c.need(all(found[k]==desc[k] for k in ('bytes','sha256')),'opaque file matches exact allowed public descriptor')
                    files[name]=found
                # This is the only per-arm file list passed to a candidate phase.
                packets[arm][phase]=dict(manifest=c.pin(raw),files=files)
                total+=len(raw)+sum(v['bytes'] for v in files.values())
        result.append(dict(ordinal=s['ordinal'],session_token=s['session_token'],packets=packets,
            private_mapping=join(ctx['private_mapping'])))
    return dict(schema='neural093_four_arm_operator_plan_v1',sessions=result,packet_count=312,
        prediction_count=156,opaque_packet_bytes_if_all_copied=total,
        source_inventory_members=614,binary_contents_validated=False,execution_authority=False)
