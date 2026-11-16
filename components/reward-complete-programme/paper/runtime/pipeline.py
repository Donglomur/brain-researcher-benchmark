"""Whole-programme orchestration, source closure, reporting and public CLI."""
import argparse
import copy
from functools import lru_cache
import html
import json
from pathlib import Path
from reward_common import need,strict_json_loads,canonical_json_bytes,sha256,object_sha256,verify_pin
from observations import prepare,CONDITIONS
from analysis import analyse
from panels import complete_panels,registry
from native import build_native_jobs

CONFIGS=('BEHAVIOR_SCORE_CONTRACT','IMPROVEMENT_POPULATIONS','FIGURE_OBLIGATIONS',
         'MODEL_PROGRAMME','OPERATORS_AND_ESTIMANDS','QUALIFICATION_AND_SCORING',
         'SOURCE_CONFLICTS','SOURCE_CLOSURE','SOURCE_PINS')


@lru_cache(maxsize=4)
def _cached_config(root):
    root=Path(root);pins=strict_json_loads((root/'ACCEPTED_DESIGN_PINS.json').read_bytes())
    out={}
    for pin in pins['copies']:
        rel=Path(pin['copied_to']).name;b=(root/rel).read_bytes()
        need(len(b)==pin['bytes'] and sha256(b)==pin['sha256'],'Exact accepted design copy')
        out[rel.removesuffix('.json')]=strict_json_loads(b)
    need(set(out)==set(CONFIGS),'Complete accepted configuration')
    return out


def load_config(root):
    return copy.deepcopy(_cached_config(str(Path(root).resolve())))


def full_scope(config):
    panels=registry(config['FIGURE_OBLIGATIONS'])
    return {'canonical_id':'PAPER-FIND-044','conditions':list(CONDITIONS),'panels':[p['panel_id'] for p in panels],
            'operators':[o['id'] for o in config['OPERATORS_AND_ESTIMANDS']['operators']],
            'gates':[g['id'] for g in config['QUALIFICATION_AND_SCORING']['gates']],
            'models_sha256':object_sha256(config['MODEL_PROGRAMME']),
            'population_sha256':object_sha256(config['IMPROVEMENT_POPULATIONS']),
            'score_contract_sha256':object_sha256(config['BEHAVIOR_SCORE_CONTRACT'])}


def source_roles(config):
    """Available ordinary bodies only; metadata trees are never executable code."""
    roles={};pins=config['SOURCE_PINS']['pins']
    for pin in pins:
        if '/public/code/' not in pin['path']:continue
        role=pin['path'].split('/public/code/')[1]
        requires=[]
        if role.endswith('Figure1_ExtDataFig12.py'):
            requires=['CODE_figures_and_experimental_analysis/functions/'+n+'.py' for n in
                      ('load_preprocess','lick_photo_functions','figure_functions','default_configs','data_wrangling','stats_functions')]
        roles[role]={'pin':pin,'requires':requires,'captured_ordinary_source':True,
                     'export_adapter_qualified':False}
    return {'roles':roles,'source_only':True}


def build(corpus,config,branch='retrospective_processed',native_exports=()):
    prepared=prepare(corpus,branch);statistics=analyse(prepared)
    figures=complete_panels(config['FIGURE_OBLIGATIONS'],prepared,statistics,native_exports)
    jobs=build_native_jobs(source_roles(config),config['MODEL_PROGRAMME'],
                           {'sha256':corpus['corpus_identity']},None,config['FIGURE_OBLIGATIONS'])
    gates=[dict(g,implementation_status='open: evidence not supplied in source-only build')
           for g in config['QUALIFICATION_AND_SCORING']['gates']]
    gates[0]['implementation_status']='design accepted by independent peer; implementation review pending'
    return {'schema':'reward_full_programme_result_v1','scope':full_scope(config),'prepared':prepared,
            'independent_analysis':statistics,'figures':figures,'native_jobs':jobs,'qualification_gates':gates,
            'supplementary_obligations':config['FIGURE_OBLIGATIONS']['supplementary_obligations'],
            'source_conflicts':config['SOURCE_CONFLICTS'],'scientific_qualification':False,
            'new_canonical_benchmarks':0,'new_independent_datasets':0,'submission_ready':False}


def render_report(result):
    esc=html.escape;rows=[]
    for p in result['figures']['panels']:
        rows.append('<tr><td>'+esc(p['panel_id'])+'</td><td>'+esc(p['status'])+'</td><td>'+
                    esc(p.get('component_status',''))+'</td><td>'+esc(p.get('reason',''))+'</td></tr>')
    gates=''.join('<li>'+esc(g['id']+' '+g['name']+': '+g['implementation_status'])+'</li>' for g in result['qualification_gates'])
    return ('<!doctype html><meta charset="utf-8"><title>Reward-spacing complete programme</title>'
            '<style>body{font:15px system-ui;max-width:1100px;margin:30px auto}td,th{padding:8px;border:1px solid #bbb}'
            'table{border-collapse:collapse}pre{white-space:pre-wrap}</style><h1>Reward-spacing complete programme</h1>'
            '<p>Source implementation / independent components. No scientific qualification or native completion is implied.</p>'
            '<p>One existing corpus. 13 conditions; 166 required panels; 13 qualification gates.</p>'
            '<table><tr><th>Panel</th><th>Full obligation status</th><th>Independent component</th><th>Reason</th></tr>'+
            ''.join(rows)+'</table><h2>Qualification gates</h2><ol>'+gates+'</ol>')


def write_result(result,directory):
    root=Path(directory);need(root.is_dir() and not any(root.iterdir()),'Empty owned output directory')
    (root/'result.json').write_bytes(canonical_json_bytes(result))
    (root/'report.html').write_text(render_report(result))
    (root/'scope.json').write_bytes(canonical_json_bytes(result['scope']))
    return {'result_sha256':sha256((root/'result.json').read_bytes()),'scientific_qualification':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True)
    parser.add_argument('--invented-corpus',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();corpus=strict_json_loads(Path(args.invented_corpus).read_bytes())
    need(corpus.get('engineering_only') is True and all(a['identity_status']=='invented' for a in corpus['animals']),
         'CLI is limited to explicitly invented engineering inputs; science needs separate authority')
    print(json.dumps(write_result(build(corpus,load_config(args.config),'engineering'),args.output)))

if __name__=='__main__':main()
