"""Separate scalar metric implementation, still unqualified until measured.

This is a numerical checker source, not an independent scientific review or a
claim of agreement. It is never invoked by engineering controls.
"""
import math
from core import need

def check(predictions,rows,reported):
    p={r['id']:r['p_high'] for r in predictions};per=[]
    for person in sorted({r['identity']['patient'] for r in rows}):
        trials=[r for r in rows if r['eligibility'] and r['identity']['patient']==person]
        counts={1:0,3:0};correct={1:0,3:0};loss=0.
        for row in trials:
            label=row['load'];prob=p[row['identity']['trial']];counts[label]+=1
            correct[label]+=int((prob>=.5)==(label==3))
            q=min(1-1e-15,max(1e-15,prob));loss-=math.log(q if label==3 else 1-q)
        need(counts[1]>0 and counts[3]>0,'complete ascertainment and class support per patient')
        per.append(((correct[1]/counts[1]+correct[3]/counts[3])/2,loss/len(trials)))
    a=sum(v[0] for v in per)/len(per);l=sum(v[1] for v in per)/len(per)
    need(abs(a-reported['patient_macro_balanced_accuracy'])<=1e-12 and abs(l-reported['patient_macro_log_loss'])<=1e-12,'independent numerical metric agreement')
    return {'scalar_agreement':True,'patients':len(per),'absolute_tolerance':1e-12}
