"""Deferred protected evaluator API. Never called by collection or registration.

An operator must first admit the full external observer and seal its baseline
panel pin. This module is not an access-control boundary or a qualification tool.
"""
import builtins
import hashlib
import importlib.util
import json
from pathlib import Path
import types
from common import need,parse,pin
import outputs


def load_sources(root):
    spec=importlib.util.spec_from_file_location('_visual_alpha_spatial_grading',root/'spatial/grading.py')
    spatial=importlib.util.module_from_spec(spec);spec.loader.exec_module(spatial)
    raw=(root/'grading_sources/spectral_contract.py').read_bytes()
    expected=json.loads((root/'grading_sources/LOCK.json').read_bytes())
    need(pin(raw)=={k:expected[k] for k in ('bytes','sha256')},'exact unchanged original spectral arithmetic')
    real_import=builtins.__import__
    def imports(name,globals=None,locals=None,fromlist=(),level=0):
        if name=='interface' and level==0:return spatial.C.S.interface
        return real_import(name,globals,locals,fromlist,level)
    spectral=types.ModuleType('_visual_alpha_original_spectral_arithmetic')
    spectral.__dict__['__builtins__']={**vars(builtins),'__import__':imports}
    exec(compile(raw,str(root/'grading_sources/spectral_contract.py'),'exec'),spectral.__dict__)
    return spatial,spectral


def grade_complete(candidate_raw,design,*,capture_sealed_baseline,expected_baseline_pin,load_person,load_spectral_targets,modules):
    """Six complete candidate outputs before any operator baseline/private callback.

    modules are exact captured evaluator sources within authenticated operator
    custody. Baseline pin comes from admitted all85-context collection, never a
    candidate-supplied score or artifact path. All unsupported results survive.
    """
    need(type(candidate_raw)is dict and set(candidate_raw)=={'spectral_A','spectral_B','reproduction_A','reproduction_B','corrected_A','corrected_B'},'all6 complete candidate outputs')
    spectrals={name:outputs.spectral(candidate_raw[name],design['spectral_rows'],design['spectral_sha']) for name in ('spectral_A','spectral_B')}
    for name in ('reproduction_A','reproduction_B','corrected_A','corrected_B'):
        outputs.spatial(candidate_raw[name],design['parameter_rows'],design['parameter_sha'])
    spatial,spectral=modules
    spatial_report=spatial.grade_panels({name:candidate_raw[name] for name in spatial.C.PANELS},design['persons'],design['parameter_sha'],capture_operator_baseline=capture_sealed_baseline,expected_baseline_pin=expected_baseline_pin,load_person=load_person)
    # Cache one immutable operator target mapping only after all public outputs
    # and the independent baseline have been admitted; never expose it to solvers.
    targets=load_spectral_targets()
    spectral_reports={name:spectral.score_submission(doc,design['spectral_rows'],design['spectral_sha'],lambda:targets) for name,doc in spectrals.items()}
    return {'schema':'visual_alpha_full_program_report_v1','spectral':spectral_reports,'spatial':spatial_report,'spectral_cross_unit_composite':None,'spectral_maes_paper_reported':False,'source_formula_and_literal_equation_separate':True,'native_gain_branch_may_be_unavailable':True,'portable_comparator_is_author_replay':False,'SOTA_claim':False,'runtime_qualified':False,'scientific_qualified':False,'whole_paper_reproduced':False}
