"""Explicit cached-source differential check on invented data only.

Run with --author-cache pointing to the separately retained, pinned source.
Nothing is downloaded or vendored. Only named AST definitions are executed;
original top-level scripts, scientific data, models and fits are never loaded.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

import numpy as np

PINS = {
    "models/Models_DN.py": (9398,"a7dd58571db5ed2906d3a19cf70dd8d47237f169419ddd8b830bb9cba4af3ca1"),
    "modelling_utils_fitObjective.py": (7915,"92718166e4b0108e13f648afcda62513e889c9014688d2f37710ddc616762c01"),
    "modelling_utils_paramInit.py": (6718,"ed9d27b842d06545965db2e822fceef128421825f7c7184489cfb46923c6d6fc"),
}


def extract(cache, relative, names, namespace):
    path = cache / relative
    if path.is_symlink() or not path.is_file():
        raise ValueError("regular source file required: " + relative)
    n, expected = PINS[relative]
    with path.open("rb") as stream:
        body = stream.read(n+1)
    if len(body)!=n or hashlib.sha256(body).hexdigest()!=expected:
        raise ValueError("source identity mismatch: " + relative)
    source = ast.parse(body, filename=relative)
    definitions = [node for node in source.body if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in names]
    if {node.name for node in definitions} != set(names):
        raise ValueError("source definitions missing")
    exec(compile(ast.Module(body=definitions,type_ignores=[]),relative,"exec"), namespace)


class GeneratedNumpy:
    """Only original table loading is redirected to generated in-memory tables."""
    def __init__(self, one, two):
        self.tables = {"generated/variables/timepoints_onepulse.txt":one, "generated/variables/timepoints_twopulse.txt":two}
    def __getattr__(self,name):
        return getattr(np,name)
    def loadtxt(self,path,dtype=float):
        if path not in self.tables:
            raise ValueError("source attempted an undeclared file read")
        return np.asarray(self.tables[path],dtype=dtype).copy()


class Info:
    def __init__(self, rows):
        self.rows = rows
        self.loc = self
    def __getitem__(self,key):
        row, field = key
        return self.rows[row][field]


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--author-cache",type=Path,required=True)
    args=parser.parse_args();cache=args.author_cache.resolve(strict=True)
    here=Path(__file__).resolve().parent
    spec=importlib.util.spec_from_file_location("temporal_dn_parity",here/"model.py")
    candidate=importlib.util.module_from_spec(spec);sys.modules[spec.name]=candidate;spec.loader.exec_module(candidate)
    one=np.array([[4,18],[8,35]],dtype=int);two=np.array([[4,18,30,42],[8,35,45,58]],dtype=int)
    namespace={"np":GeneratedNumpy(one,two),"math":math}
    extract(cache,"models/Models_DN.py",{"Models_DN"},namespace)
    extract(cache,"modelling_utils_fitObjective.py",{"model","objective"},namespace)
    extract(cache,"modelling_utils_paramInit.py",{"paramInit"},namespace)
    counts={"parameter_specs":0,"prediction_component_comparisons":0,"scalar_objectives":0}
    rng=np.random.default_rng(271828)
    for scaling in ("none","S","P"):
        a=namespace["paramInit"]("DN",scaling);b=candidate.parameter_spec(scaling)
        if a[0]!=list(b[0]):raise AssertionError("parameter names differ")
        for old,new in zip(a[1:],b[1:]):np.testing.assert_array_equal(old,new)
        counts["parameter_specs"]+=1
        for length in (96,819):
            for category in candidate.CATEGORIES:
                for trial,condition,windows in (("onepulse",0,((4,18),)),("twopulse_repeat",1,((8,35),(45,58)))):
                    p=b[1].copy();p[:6]=[3.9,1.7,.025,1.2,.23,.09]
                    if scaling!="none":p[6:]=rng.uniform(.3,2.5,6)
                    stimulus=candidate.stimulus_timecourse(trial,condition,one,two,length)
                    # Invented nonzero values outside pulse windows distinguish S masking.
                    stimulus[62:65]=-.07
                    expected=namespace["model"]("DN",scaling,stimulus,512,p,"generated/",trial,condition,category,denom=True)
                    actual=candidate.predict(stimulus,p,scaling=scaling,category=category,pulse_windows=windows,components=True)
                    for old,new in zip(expected,(actual["response"],actual["drive"],actual["denominator"])):
                        np.testing.assert_allclose(old,new,rtol=2e-13,atol=2e-13)
                    counts["prediction_component_comparisons"]+=1
        p=b[1].copy();p[0]=0
        X=np.stack([candidate.stimulus_timecourse("onepulse",0,one,two,96),candidate.stimulus_timecourse("twopulse_repeat",1,one,two,96)])
        y=rng.normal(.2,.05,X.shape)
        info=Info([{"trial_type":"onepulse","temp_cond":0,"img_cat":"BODIES"},{"trial_type":"twopulse_repeat","temp_cond":1,"img_cat":"FACES"}])
        expected=namespace["objective"](p,"DN",scaling,X,y,512,"generated/",None,info)
        actual=candidate.objective(p,X,y,scaling=scaling,categories=["BODIES","FACES"],pulse_windows=[((4,18),),((8,35),(45,58))])
        np.testing.assert_allclose(expected,actual,rtol=2e-13,atol=2e-13)
        counts["scalar_objectives"]+=1
    print(json.dumps({"status":"passed","scope":"Generated-input differential checks against three exact cached author source files","source_revision":candidate.SOURCE_REVISION,"counts":counts,"source_files":PINS,"authentic_data_reads":0,"source_top_level_scripts_executed":0,"authentic_fits":0,"historical_runtime_parity":False},sort_keys=True))


if __name__=="__main__":
    main()
