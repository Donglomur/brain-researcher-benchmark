"""Point estimates only for the fixed cohort/two chapters/all ten seeds.

No bootstrap, randomization, p-value, confidence interval or population
narrative/generalization inference exists. Query targets are evaluator-private.
"""
import math
from collections import defaultdict
from programme.contracts import need
from .protocol import EPSILON,SEEDS,PROTECTED,jobs,work_key
from .capture import TRACKS,invocation_key
from .probability import scored_probability,row_loss,mean_loss

def metrics(predictions,targets):
    need(predictions and set(predictions)<=set(targets),'full chapter original target support')
    confusion=[[0]*39 for _ in range(39)];losses=[]
    for key,p in predictions.items():
        y=targets[key];q=scored_probability(p)
        losses.append(row_loss(p,y));guess=max(range(39),key=lambda j:(q[j],-j));confusion[y][guess]+=1
    supports=[sum(r) for r in confusion];f1=[]
    for c in range(39):
        tp=confusion[c][c];fp=sum(row[c] for row in confusion)-tp;fn=supports[c]-tp;d=2*tp+fp+fn
        f1.append(0. if d==0 else 2*tp/d)
    return {'query_rows':len(predictions),'log_loss':mean_loss(losses,len(predictions)),'macro_f1_fixed39':sum(f1)/39,
            'per_class_support':supports,'per_class_f1':f1,'absent_class_rule':'F1=0 when2TP+FP+FN=0'}

def report(book,private_labels):
    targets=book.targets(private_labels);expected={invocation_key(j,t) for j in jobs() for t in TRACKS}
    need(set(book.records)==expected,'full programme denominator, no successful-only aggregation')
    rows=[];bykey={}
    for key,r in book.records.items():
        out={**r['job'],'track':r['track'],**metrics(book.probabilities(r),targets)};rows.append(out);bykey[key]=out
    # Aggregate each seed separately, first equally over both chapters per person,
    # then equally over the32 people. Preserve all intermediate distributions.
    groups=defaultdict(dict)
    for r in rows:
        k=(r['axis'],r['budget'],r['mode'],r['track'],r['arm'],r['seed'])
        groups[k][(r['person'],r['chapter'])]=r
    vectors=[]
    for k,g in sorted(groups.items()):
        need(set(g)=={(str(p),c) for p in range(1,33) for c in ('11','12')},'full32x2 each fixed-seed vector')
        people=[{'person':str(p),'log_loss':sum(g[(str(p),c)]['log_loss'] for c in ('11','12'))/2,
                 'macro_f1_fixed39':sum(g[(str(p),c)]['macro_f1_fixed39'] for c in ('11','12'))/2} for p in range(1,33)]
        vectors.append({'axis':k[0],'budget':k[1],'mode':k[2],'track':k[3],'arm':k[4],'seed':k[5],
                        'people':people,'log_loss':sum(v['log_loss'] for v in people)/32,'macro_f1_fixed39':sum(v['macro_f1_fixed39'] for v in people)/32})
    paired=[];candidate=[]
    for j in jobs():
        if j['arm']!='neural':continue
        for track in TRACKS:
            n=bykey[invocation_key(j,track)]
            for control in ('time_shifted_neural','timing','acoustic','transcript'):
                other={**j,'arm':control};r=book.records[invocation_key(j,track)];s=book.records[invocation_key(other,track)]
                need(r['support_key']==s['support_key'],'private exact paired original rows, no actor-visible map')
                c=bykey[invocation_key(other,track)]
                paired.append({**j,'track':track,'control':control,'positive_improvement':c['log_loss']-n['log_loss'],
                               'contrast_status':'protected_primary' if j['axis']!='exposed_person' and control in PROTECTED else 'exposed_or_secondary_diagnostic'})
        ref=book.records[invocation_key(j,'reference')];cand=book.records[invocation_key(j,'candidate')]
        need(ref['support_key']==cand['support_key'],'full matched candidate/reference support')
        candidate.append({**j,'positive_improvement':bykey[invocation_key(j,'reference')]['log_loss']-bykey[invocation_key(j,'candidate')]['log_loss']})
    averages=defaultdict(list)
    for v in vectors:averages[tuple(v[k] for k in ('axis','budget','mode','track','arm'))].append(v)
    seed_averages=[]
    for key,values in sorted(averages.items()):
        need({v['seed'] for v in values}==set(SEEDS) and len(values)==10,'all ten paired seeds; no winner selection')
        seed_averages.append(dict(zip(('axis','budget','mode','track','arm'),key),log_loss=sum(v['log_loss'] for v in values)/10,
                                  macro_f1_fixed39=sum(v['macro_f1_fixed39'] for v in values)/10))
    return {'schema':'n090-broad-point-report-v1','chapter_seed_distribution':rows,'person_seed_vectors':vectors,'ten_seed_averages':seed_averages,
            'all_four_paired_control_contrasts':paired,'candidate_neural_improvement':candidate,
            'primary_axes':['held_chapter','joint_person_held_chapter'],'secondary_axis':'exposed_person',
            'primary_controls':['time_shifted_neural','timing'],'stimulus_exposed_diagnostics':['acoustic','transcript'],
            'denominator':{'people':32,'fixed_chapters':2,'cases':384,'paired_slots':38400,'invocations':76800,'arms':5,'seeds':10},
            'uncertainty':'finite-cohort point estimates/full distributions only; noCI/pvalue/narrative-population claim',
            'probability_rule':'q=(1-1e-6)*normalized_admitted_p+1e-6/39; no strict properness in rawp claim',
            'qualification':False}
