import types,hashlib,json,math,tracemalloc
from pathlib import Path
p=Path(__file__).resolve().parent.parent/'reference-math/core.py'
raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()=='61715146ac2f01042d1b526896f7133604246f4951ff467c36f2735530ed5892'
m=types.ModuleType('numeric_peer');exec(compile(raw,str(p),'exec'),m.__dict__)
tracemalloc.start();checks=[]
limits={'max_rows':8,'max_features':2,'max_pairs':28,'max_matrix_elements':64,'max_live_float_slots':4096}
def near(a,b):assert math.isclose(a,b,rel_tol=2e-13,abs_tol=2e-13),(a,b)
# Closed-form two-point ridge, explicitly unpenalized intercept.
ridge=next(s for s in m.settings() if s['family']=='ridge' and s['lambda']==1)
model=m.fit_head([[-1],[1]],[math.exp(1),math.exp(5)],[.5,.5],ridge,['u','v'],limits=limits)
for actual,expected in zip(m.predict_head(model,[[-1],[0],[2]]),[2,3,5]):near(actual,expected)
checks.append('ridge_closed_form_nonzero_intercept')
# Two-point RBF: alpha=(-1,+1)/(1-k+2lambda), sigma=2; no primal/ridge substitute.
rbf=next(s for s in m.settings() if s['family']=='rbf' and s['lambda']==1 and s['width_multiplier']==1)
model=m.fit_head([[-1],[1]],[math.exp(-1),math.exp(1)],[.5,.5],rbf,['u','v'],limits=limits)
k=math.exp(-.5);amplitude=(1-k)/(1-k+2)
for actual,expected in zip(m.predict_head(model,[[-1],[0],[1]]),[-amplitude,0,amplitude]):near(actual,expected)
checks.append('rbf_closed_form_weighted_diagonal_and_intercept')
# Piecewise-linear interpolation of a globally linear signal gives analytic bin integrals.
f=m.epoch_features([-.2,.1,.7],[2*x+3 for x in [-.2,.1,.7]],'offer_CPIn')
assert len(f['bins'])==12
for lo,hi,actual in zip(f['edges'],f['edges'][1:],f['bins']):near(actual,lo+hi+3)
near(f['integral'],2.04);checks.append('epoch_fixed_bins_linear_integral')
# Retain all positive pair multiplicities; zeros only are excluded.
near(m.positive_distance_median([[0],[0],[0],[1],[3],[4]],max_pairs=15),3)
checks.append('pair_median_keeps_multiplicity')
# Same behavior interactions and natural masks in every ablation; withheld values cannot be supplied.
b=m.build_variant([2],[1],[0],1,0,variant='B')
f=m.build_variant([2],[1],[0],1,0,variant='F',n_D=[7],n_A=[0])
assert b==[2,2,0,0,1.,0.,1.,0.] and f==[2,2,0,0,7,0,1.,0.,1.,0.]
try:m.build_variant([2],[1],[0],1,0,variant='B',n_D=object())
except m.NumericFailure as e:assert e.code=='withdrawn_information'
else:raise AssertionError('withdrawn operand accepted')
checks.append('exact_common_geometry_and_withdrawn_operands')
# Full declared20-setting grid, every four-stratum cell; tie policy is an ordered exact rule.
rows=[{'setting_id':s['id'],'animal':'a','stratum':h,'loss':1.0} for s in m.settings() for h in m.STRATA]
chosen=m.select_setting(rows,['a']);assert chosen['setting']['family']=='rbf' and chosen['setting']['lambda']==100 and chosen['setting']['width_multiplier']==2
try:m.select_setting(rows[:-1],['a'])
except m.NumericFailure as e:assert e.code=='incomplete_portfolio'
else:raise AssertionError('incomplete grid accepted')
checks.append('complete_grid_and_declared_exact_tie_order')
_,peak=tracemalloc.get_traced_memory();tracemalloc.stop();assert peak<8388608
out={'schema':'ach_peer_numeric_analytic_controls','groups':checks,'passed':len(checks),'tiny_invented_head_fits':2,'traced_peak_after_load':peak,'cumulative_reserved':524288,'physical_fixture_writes':0,'native_parity_or_real_science':False}
raw=json.dumps(out,sort_keys=True,indent=2,allow_nan=False).encode();assert len(raw)<262144
print(raw.decode());print('SUMMARY_ENCODING_BYTES',len(raw))
