from pathlib import Path
import json,hashlib
p=Path('/Users/nicholas/Documents/Codex/neuroscience-benchmark-planning/authoring/delivery-20261105/common/remaining-builds-wave29/neural058-complete-design/implementation-v1')
doc=json.loads((p/'COMPLETE_SOURCE_SLICE_V1.json').read_bytes())
for d in doc['files']:
 b=Path('/Users/nicholas/Documents/Codex/neuroscience-benchmark-planning',d['path']).read_bytes();assert len(b)==d['bytes'] and hashlib.sha256(b).hexdigest()==d['sha256']
def edit(name,old,new):
 f=p/'program'/name;s=f.read_text();assert old in s,(name,old[:100]);f.write_text(s.replace(old,new))
# I6: exact embedded bytes precede any score/model/producer use.
f=p/'program/admission.py';s=f.read_text();at=s.index('\ndef admit(')
s=s[:at]+'''
def authenticate_product(product):
    members=product['derived']['members']
    names=[r['path'] for r in members]
    need(len(names)==len(set(names)) and names.count('RESULT.json')==1,'unique complete derived RESULT.json')
    result=next(r['pin'] for r in members if r['path']=='RESULT.json')
    need(result==product['result_pin']==pin(encoded(product['result'])), 'embedded result exact canonical closed bytes')
    need(product['native']['artifacts']['TERMINAL.json']==pin(encoded(product['terminal'])),
         'embedded terminal exact canonical closed bytes')
    need(product['terminal']['result']=={'path':'RESULT.json','pin':result},'terminal result belongs to unique closed member')
    return True

'''+s[at:];s=s.replace("    roster=complete['roster'];choices=complete['reference_selection']['choices']", "    for product in complete['products'].values():authenticate_product(product)\n    roster=complete['roster'];choices=complete['reference_selection']['choices']");f.write_text(s)
# I7/I8: independent diagnostics cannot turn a numeric overflow into a primary failure.
edit('native_diagnostic.py',"    need(bool(torch.isfinite(value).item()),'finite native convention diagnostic')", "    if not bool(torch.isfinite(value).item()):\n        return {'status':'not_comparable','reason':'native float32 metric reduction is nonfinite',\n                'trial_count':len(trial),'timestamp_count':len(target),\n                'dependency_or_physical_exception_suppressed':False}")
edit('scores.py',"    sse=np.zeros(2,dtype=np.float64); sst=sse.copy()", "    sse=np.zeros(2,dtype=np.float64); sst=sse.copy();mae=sse.copy()")
edit('scores.py',"        sst += w*((y-mu)**2).sum(axis=0,dtype=np.float64)", "        sst += w*((y-mu)**2).sum(axis=0,dtype=np.float64)\n        mae += w*np.abs(y-p).sum(axis=0,dtype=np.float64)")
edit('scores.py',"    return {'mean':mu.tolist(),'sse':sse.tolist(),'sst':sst.tolist(),\n            'r2':[None if d==0 else float(1-n/d) for n,d in zip(sse,sst)]}", "    need(bool(np.isfinite(sse).all() and np.isfinite(sst).all() and np.isfinite(mae).all()),'finite canonical diagnostic arithmetic')\n    return {'mean':mu.tolist(),'sse':sse.tolist(),'sst':sst.tolist(),'mse':sse.tolist(),'mae':mae.tolist(),\n            'support':{'sessions':len(sessions),'windows':sum(len(s) for s in sessions),\n                       'timestamps':sum(len(y) for s in sessions for y,_ in s),\n                       'per_session':[{'windows':len(s),'timestamps':sum(len(y) for y,_ in s)} for s in sessions]},\n            'weight_rule':'1/(animal sessions * session windows * window timestamps); normalized mass1',\n            'undefined_reason':['exact constant target' if d==0 else None for d in sst],\n            'r2':[None if d==0 else float(1-n/d) for n,d in zip(sse,sst)]}")
# I9: stable original-source order independent of opaque labels.
(p/'program/ordering.py').write_text('''"""Stable original-roster ordinals; opaque aliases never determine traversal."""
from core import need


def animals(sessions):
    rows={}
    for s in sessions:
        a=s['animal'];ordinal=s['animal_ordinal']
        need(type(ordinal)is int and ordinal>=0,'source-owned ordinary animal ordinal')
        need(a not in rows or rows[a]==ordinal,'one ordinal per biological animal')
        rows[a]=ordinal
    need(len(set(rows.values()))==len(rows),'unique biological animal ordinals')
    return sorted(rows,key=lambda a:rows[a])


def roster(rows):
    result={}
    for role,count,animal_count in (('source',423,126),('evaluation',29,13)):
        group={s:r for s,r in rows.items() if r['role']==role}
        need(len(group)==count,'complete ordered source corpus')
        need(all(type(r['session_ordinal'])is int for r in group.values()) and
             sorted(r['session_ordinal'] for r in group.values())==list(range(count)),'exact stable session ordinal bijection')
        ordered=sorted(group,key=lambda s:group[s]['session_ordinal'])
        people=animals([group[s] for s in ordered])
        need(len(people)==animal_count and sorted({r['animal_ordinal'] for r in group.values()})==list(range(animal_count)),
             'complete source-owned animal ordinal bijection')
        result[role]=group;result[role+'_order']=ordered
        result['source_animals' if role=='source' else 'eval_animals']=people
    need(not set(result['source_animals'])&set(result['eval_animals']),'full disjoint biological roster')
    folds={}
    for r in result['source'].values():
        a=r['animal'];f=r['fold'];need(type(f)is int and 0<=f<5,'ordinary full source fold')
        need(a not in folds or folds[a]==f,'one fold per animal');folds[a]=f
    need([list(folds.values()).count(i) for i in range(5)]==[26,25,25,25,25],'exact biological fold sizes')
    result['folds']=folds;return result


def sessions(roster,role,animal=None):
    order=roster[role+'_order'];need(len(order)==len(set(order)) and set(order)==set(roster[role]),'complete explicit session order')
    return [s for s in order if animal is None or roster[role][s]['animal']==animal]


def subset_animals(roster,session_ids):
    present={roster['source'][s]['animal'] for s in session_ids}
    return [a for a in roster['source_animals'] if a in present]
''')
edit('contracts.py',"'eval_animals': sorted(animals['evaluation_sessions']), 'folds': dict(folds)}", "'eval_animals': sorted(animals['evaluation_sessions']), 'folds': dict(folds),\n            'source_order':sorted(by_role['source_sessions']), 'evaluation_order':sorted(by_role['evaluation_sessions'])}")
edit('contracts.py',"    train = sorted(e for e,r in roster['source'].items() if fold == 'full' or roster['folds'][r['animal']] != fold)\n    val = [] if fold == 'full' else sorted(e for e,r in roster['source'].items() if roster['folds'][r['animal']] == fold)", "    from ordering import sessions\n    order=sessions(roster,'source')\n    train = [e for e in order if fold == 'full' or roster['folds'][roster['source'][e]['animal']] != fold]\n    val = [] if fold == 'full' else [e for e in order if roster['folds'][roster['source'][e]['animal']] == fold]")
edit('contracts.py',"    need(record.get('training_animals') == sorted({roster['source'][e]['animal'] for e in train}),", "    from ordering import subset_animals\n    need(record.get('training_animals') == subset_animals(roster,train),")
edit('preparation.py',"            for eid in sorted(roster[role]):\n                stage = {'session': eid, 'role': role, 'status':'attempted'}; outcomes.append(stage)", "            people=roster['source_animals' if role=='source' else 'eval_animals']\n            for ordinal,eid in enumerate(roster[role+'_order']):\n                animal_ordinal=people.index(roster[role][eid]['animal'])\n                stage = {'session': eid, 'role': role, 'status':'attempted','session_ordinal':ordinal,'animal_ordinal':animal_ordinal}; outcomes.append(stage)")
edit('preparation.py',"'animal':aliases[row['animal']], 'windows':windows,'regions':regions,", "'animal':aliases[row['animal']], 'session_ordinal':ordinal,'animal_ordinal':animal_ordinal,\n                        'windows':windows,'regions':regions,")
edit('preparation.py',"                     'cohort':pin(encoded(cohort_document)), 'authority':pin(encoded(authority)),", "                     'source_order':[r['session_alias'] for r in outcomes if r['role']=='source'],\n                     'evaluation_order':[r['session_alias'] for r in outcomes if r['role']=='evaluation'],\n                     'source_animal_order':[aliases[a] for a in roster['source_animals']],\n                     'evaluation_animal_order':[aliases[a] for a in roster['eval_animals']],\n                     'cohort':pin(encoded(cohort_document)), 'authority':pin(encoded(authority)),")
edit('corpus.py',"'windows':original['windows'],'regions':original['regions'],'fold':original['fold'],", "'windows':original['windows'],'regions':original['regions'],'fold':original['fold'],\n            'session_ordinal':original['session_ordinal'],'animal_ordinal':original['animal_ordinal'],")
edit('corpus.py',"result={'session':doc['session'],'animal':doc['animal'],'fold':doc['fold'],'regions':doc['regions'],", "result={'session':doc['session'],'animal':doc['animal'],'fold':doc['fold'],'regions':doc['regions'],\n            'session_ordinal':doc['session_ordinal'],'animal_ordinal':doc['animal_ordinal'],")
edit('corpus.py',"    need(sorted({s['animal'] for s in sessions})==expected_animals,'full animal membership')", "    from ordering import animals\n    need(animals(sessions)==expected_animals,'full stable animal membership')")
edit('views.py',"self.rows[sid]={'eid':sid,'animal':doc['animal'],'role':corpus,'fold':doc['fold']}", "self.rows[sid]={'eid':sid,'animal':doc['animal'],'role':corpus,'fold':doc['fold'],\n                                'session_ordinal':doc['session_ordinal'],'animal_ordinal':doc['animal_ordinal']}")
f=p/'program/views.py';s=f.read_text();start=s.index("        source={s:r");end=s.index('\n    def input_rows',start)
s=s[:start]+'''        from ordering import roster as ordered_roster
        self.roster=ordered_roster(self.rows)
        need(self.roster['source_order']==top['source_order'] and self.roster['evaluation_order']==top['evaluation_order']
             and self.roster['source_animals']==top['source_animal_order'] and self.roster['eval_animals']==top['evaluation_animal_order'],
             'exact stable original-source ordering, opaque labels only')
'''+s[end:];s=s.replace("        return sorted(s for s,r in self.roster['evaluation'].items() if r['animal']==animal)","        from ordering import sessions\n        return sessions(self.roster,'evaluation',animal)");f.write_text(s)
for name in ['reference_models.py','reference_worker.py']:
 f=p/'program'/name;s=f.read_text();s=s.replace("animals=sorted({s['animal'] for s in sessions})","from ordering import animals as ordered_animals\n    animals=ordered_animals(sessions)")
 s=s.replace("'training_animals':sorted({s['animal'] for s in sessions})", "'training_animals':__import__('ordering').animals(sessions)")
 s=s.replace("train_animals=sorted({s['animal'] for s in training})", "train_animals=__import__('ordering').animals(training)");f.write_text(s)
f=p/'program/schedule.py';s=f.read_text().replace("from core import need","from core import need\nfrom ordering import sessions")
s=s.replace("sorted(e for e,r in roster['evaluation'].items() if r['animal'] == animal)","sessions(roster,'evaluation',animal)")
s=s.replace("for eid, row in sorted(roster['evaluation'].items()):", "for eid in sessions(roster,'evaluation'):\n        row=roster['evaluation'][eid]",1)
# final_reference_sessions nested loop has a different indent.
s=s.replace("        for eid, row in sorted(roster['evaluation'].items()):", "        for eid in sessions(roster,'evaluation'):\n            row=roster['evaluation'][eid]")
f.write_text(s)
f=p/'program/references.py';s=f.read_text().replace("from core import need,finite","from core import need,finite\nfrom ordering import sessions,subset_animals")
s=s.replace("sorted({roster['source'][s]['animal'] for s in train})","subset_animals(roster,train)")
s=s.replace("sorted(set(roster['eval_animals'])|{roster['source'][s]['animal'] for s in val})","roster['eval_animals']+subset_animals(roster,val)")
s=s.replace("train=sorted(roster['source'])","train=sessions(roster,'source')");f.write_text(s)
edit('authors.py',"source=sorted(self.views.roster['source'])", "source=self.views.roster['source_order']")
f=p/'program/admission.py';s=f.read_text().replace("from journal import closure","from journal import closure\nfrom ordering import sessions")
s=s.replace("sorted(roster['source'])","sessions(roster,'source')")
s=s.replace("sorted(s for s,x in roster['evaluation'].items() if x['animal']==spec['animal'])","sessions(roster,'evaluation',spec['animal'])");f.write_text(s)
f=p/'program/grading.py';s=f.read_text().replace("from schedule import panels","from schedule import panels\nfrom ordering import sessions as ordered_sessions")
s=s.replace("sorted(s for s,r in roster['evaluation'].items() if r['animal']==animal)","ordered_sessions(roster,'evaluation',animal)")
s=s.replace("for sid in sorted(views):","for sid in complete['roster']['evaluation_order']:")
s=s.replace("sorted(views))","complete['roster']['evaluation_order'])");f.write_text(s)
f=p/'program/projection_admission.py';s=f.read_text().replace("    docs={};projections={}","    docs={};projections={};ordinal_rows={}")
s=s.replace("            docs[sid]=doc", "            ordinal_rows[sid]={'eid':sid,'animal':doc['animal'],'role':role,'fold':doc['fold'],\n                               'session_ordinal':doc['session_ordinal'],'animal_ordinal':doc['animal_ordinal']}\n            docs[sid]=doc")
s=s.replace("    native_intents=", "    from ordering import roster as ordered_roster\n    need(ordered_roster(ordinal_rows)==complete['roster'],'independent full stable source/animal order')\n    need(complete['roster']['source_order']==top['source_order'] and complete['roster']['evaluation_order']==top['evaluation_order']\n         and complete['roster']['source_animals']==top['source_animal_order']\n         and complete['roster']['eval_animals']==top['evaluation_animal_order'],'exact authenticated preparation order arrays')\n    native_intents=")
f.write_text(s)
print('Applied preserved I6-I9 draft repairs; I10-I11 follow before successor freeze.')
