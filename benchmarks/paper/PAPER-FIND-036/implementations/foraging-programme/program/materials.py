"""Exact independently admitted common paper and relevant author-source exposure."""
from common import *

def admit(v,bodies,budget):
    d=v['paper_material_admission'];a=parse(read(d['path'],d,budget,v['metadata_cap_bytes']))
    need(a['schema']=='foraging_complete_common_paper_admission_v1' and a['task_id']==TASK and a['doi']=='10.7554/eLife.93994.4','exact same-edition paper admission')
    need(a['independently_reviewed']is True and a['admitted_by_root']is True and a['narrative_methods_figures_captions_complete']is True and a['unresolved_required_materials']==[],'complete common paper/material qualification; HTML alone insufficient')
    binding=parse(bodies['BINDING.json']);need(a['static_condition']==binding['common_static_condition']and descriptor(a['independent_static_review'])==binding['common_static_review']and descriptor(a['static_proposal'])==binding['common_static_proposal'],'exact independently reviewed static-paper condition');rows=a['materials'];need(type(rows)is list and 2<=len(rows)<=256,'explicit complete paper-material inventory')
    names=set()
    for row in rows:
        n=row['target'];need(type(n)is str and n.startswith('paper/') and not Path(n).is_absolute() and '..'not in Path(n).parts and n not in names,'unique ordinary common paper path');names.add(n);descriptor(row)
        need(row['source_kind']in('publisher_html','publisher_pdf','publisher_figure','publisher_supplement','publisher_media'),'authentic publisher paper material')
    need([{k:x[k]for k in ('target','bytes','sha256')}for x in rows]==binding['common_static_paper_materials'],'all five exact common paper materials, no substitute or omitted file')
    need(a['external_media']==binding['external_media']and a['out_of_scope_review_materials']==binding['out_of_scope_review_materials'],'explicit static article-body scope; no universal media claim')
    article=next((x for x in rows if x['target']==binding['article']['target']),None);need(article and descriptor(article)==descriptor(binding['article']),'mandatory exact held article narrative')
    need(any(x['source_kind']in('publisher_pdf','publisher_figure')for x in rows),'figure-bearing paper material required')
    # Authentic completeness is an externally reviewed assertion, not inferred
    # from these structural checks or the mere presence of a PDF filename.
    return a,rows,binding

def visible(common,binding,role):
    return [{k:r[k]for k in ('target','bytes','sha256')}for r in common]+(binding['author_files']if role=='B'else [])

def stage(common,binding,role,bodies,view,budget):
    files={}
    for r in common:files[r['target']]=copy(r['path'],view/r['target'],r,budget)
    if role=='B':
        for r in binding['author_files']:
            need(pin(bodies[r['target']])==descriptor(r),'exact held author source');files[r['target']]=write(view/r['target'],bodies[r['target']],budget)
    files['CANDIDATE_ABI.md']=write(view/'CANDIDATE_ABI.md',bodies['CANDIDATE_ABI.md'],budget)
    return files
