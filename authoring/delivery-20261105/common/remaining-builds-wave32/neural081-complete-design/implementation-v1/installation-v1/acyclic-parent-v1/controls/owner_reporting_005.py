"""Tiny invented descriptive reports and literal captured-source roster parity."""
import ast,hashlib,importlib.abc,importlib.util,json,math,sys,types
from pathlib import Path
P=Path(__file__).resolve().parent.parent
raw=(P/'SOURCE_MANIFEST.json').read_bytes();assert hashlib.sha256(raw).hexdigest()=='15d582f6a35cca15fa24886da5b4c14d3bf0ce72a16fe919c3ee6d8fd1f84fcc'
m=json.loads(raw);captured={}
for row in m['modules']:
    d=row['source'];b=Path(d['path']).read_bytes();assert len(b)==d['bytes']and hashlib.sha256(b).hexdigest()==d['sha256'];captured[row['name']]=(d['path'],b)
class Loader(importlib.abc.MetaPathFinder,importlib.abc.Loader):
    def find_spec(self,name,path=None,target=None):return importlib.util.spec_from_loader(name,self,is_package=name=='transport')if name in captured else None
    def create_module(self,spec):return None
    def exec_module(self,module):
        path,body=captured[module.__name__];module.__file__=path;exec(compile(body,path,'exec'),module.__dict__)
sys.meta_path.insert(0,Loader())
import common as c,protocol as p,metrics,grading,runtime,grade_driver,preparation_driver,worker_bootstrap
checks=[];used=0;largest=0
def encode(v):
    global used,largest
    b=c.encoded(v);assert used+len(b)<=1048576 and len(b)<=1048576;used+=len(b);largest=max(largest,len(b));return b
old=(P/'history/full-runtime-v1/program/metrics.py').read_bytes();ot=ast.parse(old);nt=ast.parse(captured['metrics'][1])
for node in ot.body:
    if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
        matching=next(x for x in nt.body if isinstance(x,ast.FunctionDef)and x.name==node.name)
        assert ast.dump(node,include_attributes=False)==ast.dump(matching,include_attributes=False)
checks.append('every original canonical primary scorer function AST unchanged')
grade_ast=ast.parse(captured['grade_entry'][1]);declared=next(ast.literal_eval(x.value.args[0])for x in ast.walk(grade_ast)if isinstance(x,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='required'for t in x.targets))
assert runtime.TRUSTED_MODULES['grader']==grade_driver.NAMES==frozenset(declared)
assert runtime.TRUSTED_MODULES['reference']==worker_bootstrap.REQUIRED and runtime.TRUSTED_MODULES['preparation']==preparation_driver.NAMES
assert [len(runtime.TRUSTED_MODULES[k])for k in('reference','preparation','grader')]==[8,7,17]
assert {'authority','transport.common','transport.provider','transport.process'}<=grade_driver.NAMES
checks.append('literal complete reference8/preparation7/grader17 producer-loader-runtime rosters agree')
labels=list(c.CLASSES)*10;people=[person for person in c.PEOPLE for _ in c.CLASSES]
def pattern(correct):
    return [[1. if col==(j if j<correct else(j+1)%12)else 0. for col in range(12)]for j in range(12)]
groups={}
for mode in c.MODES:
    for rep_index,rep in enumerate(c.REPS):
        for view in c.VIEWS:
            n=(0,6,12)[rep_index]if mode=='I'and view=='EEG'else 0
            groups[('candidate',mode,rep,view)]={person:pattern(n)for person in c.PEOPLE}
for role,handles in(('reference',p.HANDLES),('analytic',('UNIFORM','LAPLACE'))):
    for handle in handles:
        for view in c.VIEWS:groups[(role,handle,view)]={person:[[1/12]*12 for _ in c.CLASSES]for person in c.PEOPLE}
encode({'construction':'literal deterministic pattern function and uniform12class rows in this captured script','group_keys':[list(k)for k in groups],'patterns':[pattern(n)for n in(0,6,12)],'uniform_row':[1/12]*12,'labels':labels,'people':people})
strongest={(view,person):p.FAMILIES[0]for view in c.VIEWS for person in c.PEOPLE}
historical=types.ModuleType('historical_grading');old=(P/'history/full-runtime-v1/program/grading.py').read_bytes();exec(compile(old,'historical_grading.py','exec'),historical.__dict__)
old_score=historical.score({},groups,labels,people,strongest)
new=grading.score({},groups,labels,people,strongest)
assert len(new['conditions'])==26 and len(new['replication_means'])==4 and len(new['paired_contrasts'])==12 and len(new['mean_paired_contrasts'])==4 and len(new['candidate_comparisons'])==84
for a,b in zip(old_score['conditions'],new['conditions']):assert c.typed_equal(a,{'key':b['key'],'metrics':b['metrics']})
for a,b in zip(old_score['replication_means'],new['replication_means']):assert c.typed_equal(a,{k:b[k]for k in a})
assert c.typed_equal(old_score['paired_contrasts'],new['paired_contrasts'])and c.typed_equal(old_score['candidate_comparisons'],new['candidate_comparisons'])
checks.append('all26 condition primary outputs and prior contrasts match historical tiny invented calculation')
for condition in new['conditions']:
    diagnostic=condition['descriptive'];assert diagnostic['class_order']==list(c.CLASSES)and len(diagnostic['class_recalls'])==12 and len(diagnostic['per_participant'])==10
    for person in diagnostic['per_participant']:
        assert [x['true_class']for x in person['class_rows']]==list(c.CLASSES)
        for j,row in enumerate(person['class_rows']):assert row['support']==1 and len(row['predicted_class_counts'])==12 and sum(row['predicted_class_counts'])==1 and row['recall']==row['predicted_class_counts'][j]
    assert len(diagnostic['leave_one_person_out_aggregation_sensitivity'])==10
checks.append('complete person-by-class confusion/support/recalls and aggregation sensitivity')
headline=next(r for r in new['replication_means']if r['mode']=='I'and r['view']=='EEG')
assert headline['participant_macro_balanced_accuracy']==.5 and headline['balanced_accuracy_replications']=={'values':[0.,.5,1.],'mean':.5,'minimum':0.,'maximum':1.,'range':1.,'sample_standard_deviation':.5}
assert all(r['balanced_accuracy']==.5 for r in headline['leave_one_person_out_aggregation_sensitivity'])
paired=next(r for r in new['mean_paired_contrasts']if r['contrast']=='I-minus-F'and r.get('view')=='EEG')
assert paired['participant_macro_balanced_accuracy_difference']==.5 and paired['balanced_accuracy_replications']['sample_standard_deviation']==.5
assert all(r['balanced_accuracy_difference']==.5 for r in paired['leave_one_person_out_aggregation_sensitivity'])
checks.append('analytic three-replication range/sample SD and ordered paired headline')
flags=[{'person':person,'bad_channels':[p.CHANNELS[0],p.CHANNELS[1]]if j==0 else(['AUX-INVENTED']if j==1 else[])}for j,person in enumerate(c.PEOPLE)]
prevalence=grading.bad_channel_prevalence(flags)
assert prevalence['people_with_any_original_bad_flag']==2 and prevalence['people_with_any_canonical_eeg_bad_flag']==1 and prevalence['proportion_with_any_original_bad_flag']==.2 and prevalence['channels_dropped_or_interpolated']is False
assert [r['people_flagged']for r in prevalence['canonical_eeg_channel_person_counts']]==[1,1]+[0]*62
checks.append('complete private flag prevalence including canonical EEG versus auxiliary flags')
encode(new);encode(prevalence)
assert not any(n in sys.modules for n in('numpy','scipy','sklearn','mne','tiktoken'))
result={'schema':'neural081_owner_reporting_controls_v2','passed':True,'groups':checks,'known_encoded_before_result_bytes':used,'largest_encoding_bytes':largest,'full_fixture_debit_bytes':1048576,'scope':'Tiny invented120-row arithmetic, actual reporting functions, primary AST parity and exact literal rosters; no arrays/fits/provider/native/process/authentic source/header/target access. Real full-roster trusted-request and captured G5 lazy-import successor controls belong to the sole peer.'}
b=encode(result);(P/'controls/OWNER_REPORTING_RESULT_005.json').write_bytes(b);print(json.dumps({'passed':True,'groups':len(checks),'encoded_bytes':used,'largest':largest,'result_bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}))
