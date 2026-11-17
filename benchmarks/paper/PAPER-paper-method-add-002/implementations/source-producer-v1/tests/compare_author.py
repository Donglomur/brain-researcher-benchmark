"""Optional pinned-author comparison using generated numeric controls only.

The caller supplies an existing author-source cache. No downloads, authentic
arrays, repository imports or decomposition fitting occur. This executable
comparison is separate from the ordinary unittest discovery suite.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import numpy as np
import scipy.ndimage as ndi
import sklearn.linear_model

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--author-source-dir',required=True,type=Path,help='existing cache containing SOURCE_MAP.json cache_basename files')
parser.add_argument('--output',required=True,type=Path,help='fresh JSON report path; existing files are refused')
args=parser.parse_args()
COMP=Path(__file__).resolve().parents[2]
CACHE=args.author_source_dir
OUTPUT=args.output
if OUTPUT.exists():raise FileExistsError('output must not exist: '+str(OUTPUT))
spec=importlib.util.spec_from_file_location('producer_review',COMP/'source-producer-v1/producer.py');p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
source_map=json.loads((COMP/'source-endpoints-v1/SOURCE_MAP.json').read_text())
sources={x['cache_basename']:x for x in source_map['sources']}
used=[];checks={}

def selected(basename,names,namespace):
 entry=sources[basename];path=CACHE/basename
 if path.stat().st_size!=entry['bytes']:raise ValueError('source extent differs: '+basename)
 body=path.read_bytes()
 if len(body)!=entry['bytes'] or hashlib.sha256(body).hexdigest()!=entry['sha256']:
  raise ValueError('source hash differs: '+basename)
 tree=ast.parse(body);nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
 if {n.name for n in nodes}!=set(names):raise ValueError('required source functions missing: '+basename)
 code=compile(ast.Module(body=nodes,type_ignores=[]),entry['repository_path'],'exec');exec(code,namespace)
 used.append({'basename':basename,'sha256':entry['sha256'],'functions':names})

ns={'np':np,'sklearn':sklearn}
selected('sliceTCA_paper__figures__Fig2__code__hand_decoding__helper_functions.py',['flatten_mid_dims','split'],ns)
selected('sliceTCA_paper__figures__Fig2__code__hand_decoding__functions.py',['decoding','velocity_decoding','trial_wise_r2','k_fold_cross_validated_r2'],ns)
fig={'np':np,'functions':SimpleNamespace(**{k:ns[k] for k in ['velocity_decoding','trial_wise_r2']})}
selected('sliceTCA_paper__figures__Fig2__code__Fig2.py',['get_movement_avg','get_r2','get_r2_all','sort_by_condition'],fig)
rng=np.random.RandomState(192);x=rng.randn(150,511,3);movement=np.cumsum(rng.randn(150,511,2),axis=0)
angles=np.r_[np.arange(265)%2,2+np.arange(246)%2]
for recipe,alpha in [('paper_ols0',0),('source_code_ridge1',1)]:
 xx=x[:12,:7];yy=movement[:12,:7];model=p.fit_linear(xx,yy,recipe=recipe);w,b=ns['decoding'](xx,yy,regularization=alpha)
 np.testing.assert_allclose(model['weight'],w,rtol=1e-12,atol=1e-12);np.testing.assert_allclose(model['bias'],b,rtol=1e-12,atol=1e-12)
 target,_=ns['velocity_decoding'](xx,yy,regularization=alpha)
 actual=p.predict_positions(p.fit_velocity(xx,yy,recipe=recipe),xx,yy[0])
 np.testing.assert_allclose(actual,target,rtol=1e-12,atol=1e-12)
 checks['decoder_'+recipe]='coefficients and true-start positions match pinned source'
with mock.patch.object(p.endpoints,'source_windows',return_value=(x[55:-15],movement[65:-5])):
 repeated=p.repeated_decoding(x,movement,recipe='source_code_ridge1')
 averaged=p.condition_average_control(x,movement,angles,recipe='source_code_ridge1')
for condition,(lo,hi) in p.endpoints.CONDITIONS.items():
 source_scores,source_sd=ns['k_fold_cross_validated_r2'](x[55:-15,lo:hi],movement[65:-5,lo:hi],ns['velocity_decoding'],folds=5,sample_size=20,mean=False,seed=0)
 np.testing.assert_allclose(repeated['conditions'][condition]['details']['r2'],source_scores,rtol=1e-11,atol=1e-11)
 np.testing.assert_allclose(repeated['conditions'][condition]['summary']['mean_within_fold_population_sd'],source_sd,rtol=1e-11,atol=1e-11)
 checks['fivefold_'+condition]={'source_score_shape':list(source_scores.shape),'max_absolute_difference':float(np.max(np.abs(repeated['conditions'][condition]['details']['r2']-source_scores)))}
np.random.seed(0)
for _ in range(20):np.random.permutation(246)
source_average=fig['get_r2_all'](x,movement,angles,sample_size=20)
for condition,source_scores in zip(('straight','curved'),source_average):
 np.testing.assert_allclose(averaged['conditions'][condition]['r2'],source_scores,rtol=1e-11,atol=1e-11)
 checks['composed_twohalf_'+condition]={'source_score_shape':list(source_scores.shape),'max_absolute_difference':float(np.max(np.abs(averaged['conditions'][condition]['r2']-source_scores)))}
order_labels=np.array([20,22,10,34,18,39,32,5,37,35,26,31]);condition=np.resize(order_labels[::-1],511)
source_sorted,_,_=fig['sort_by_condition'](np.arange(511)[None,:,None],condition)
expected=np.concatenate([np.flatnonzero(condition[lo:hi]==label)+lo for lo,hi in ((0,265),(265,511)) for label in order_labels])
np.testing.assert_array_equal(source_sorted.ravel(),expected);checks['component_order']='matches explicit pinned source condition ordering'
report={'status':'passed','scope':'generated arrays only; full source trial/repeat/fold schedules, reduced3feature dimension for bounded numeric differential','authentic_arrays_read':False,'decomposition_or_candidate_models_fitted':False,'linear_decoders_fitted_on_generated_controls':True,'source_revision':p.SOURCE_REVISION,'producer_sha256':hashlib.sha256((COMP/'source-producer-v1/producer.py').read_bytes()).hexdigest(),'source_functions':used,'checks':checks,'dependencies':{'numpy':np.__version__,'sklearn':sklearn.__version__}}
with OUTPUT.open('x') as handle:handle.write(json.dumps(report,sort_keys=True,indent=2)+'\n')
print(json.dumps({'status':report['status'],'checks':checks},sort_keys=True))
