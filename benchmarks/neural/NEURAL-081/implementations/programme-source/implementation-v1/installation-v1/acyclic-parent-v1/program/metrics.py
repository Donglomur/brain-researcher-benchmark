"""Exact canonical scorer functions, copied as source, never original main."""
import math
import common as c
CLASSES=list(c.CLASSES)
PEOPLE=list(c.PEOPLE)
FLOOR=1e-12

def exact(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError('Unexpected object fields')

def probabilities(value):
    if not isinstance(value, list) or len(value) != 12:
        raise ValueError('Exactly twelve probabilities are required')
    for p in value:
        if type(p) not in (float, int) or not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError('Probability outside finite [0,1]')
    if abs(math.fsum(value) - 1.0) > 1e-6:
        raise ValueError('Probabilities must sum to one; no automatic renormalization')
    return value

def submission_rows(submission, ids):
    exact(submission, ['schema', 'predictions'])
    if submission['schema'] != 'neural081_predictions_v1' or not isinstance(submission['predictions'], list) or len(submission['predictions']) != len(ids):
        raise ValueError('Wrong submission identity/coverage')
    rows = []
    for expected, row in zip(ids, submission['predictions']):
        exact(row, ['id', 'probabilities'])
        if row['id'] != expected:
            raise ValueError('Prediction order/identity mismatch')
        rows.append(probabilities(row['probabilities']))
    return rows

def numerical_score(rows, labels, people):
    per_person = []
    for person in PEOPLE:
        select = [i for i, p in enumerate(people) if p == person]
        recalls = []
        for label in CLASSES:
            relevant = [i for i in select if labels[i] == label]
            if not relevant:
                raise ValueError('Private gold is missing a class in a participant')
            correct = sum(CLASSES[max(range(12), key=lambda k: rows[i][k])] == label for i in relevant)
            recalls.append(correct / len(relevant))
        loss = math.fsum(-math.log(max(FLOOR, rows[i][CLASSES.index(labels[i])])) for i in select) / len(select)
        per_person.append({'participant': person, 'cases': len(select),
                           'balanced_accuracy': math.fsum(recalls) / 12.0,
                           'log_loss': loss})
    return {'participant_macro_balanced_accuracy': math.fsum(p['balanced_accuracy'] for p in per_person) / 10.0,
            'participant_macro_log_loss': math.fsum(p['log_loss'] for p in per_person) / 10.0,
            'per_participant': per_person}

def aggregation_sensitivity(per_person,ba='balanced_accuracy',loss='log_loss'):
    """Descriptive deletion of one existing biological score, no refitting."""
    c.need([r['participant']for r in per_person]==PEOPLE,'all ten already-computed biological scores')
    result=[]
    for omitted in PEOPLE:
        rows=[r for r in per_person if r['participant']!=omitted]
        result.append({'omitted_person':omitted,'retained_people':9,ba:math.fsum(r[ba]for r in rows)/9,loss:math.fsum(r[loss]for r in rows)/9})
    return result

def replication_summary(values):
    c.need(type(values)is list and len(values)==3 and all(type(x)in(int,float)and math.isfinite(x)for x in values),'three complete finite author replication scalars')
    mean=math.fsum(values)/3
    return {'values':list(values),'mean':mean,'minimum':min(values),'maximum':max(values),'range':max(values)-min(values),'sample_standard_deviation':math.sqrt(math.fsum((x-mean)**2 for x in values)/2)}

def descriptive_diagnostics(rows,labels,people,scored):
    """Add mandated counts/recalls without altering canonical primary arithmetic."""
    c.need(len(rows)==len(labels)==len(people),'complete admitted descriptive operands')
    predicted=[max(range(12),key=lambda k:row[k])for row in rows];persons=[]
    for person in PEOPLE:
        selected=[i for i,value in enumerate(people)if value==person];classes=[]
        for label in CLASSES:
            relevant=[i for i in selected if labels[i]==label];c.need(relevant,'all classes retained in descriptive report')
            counts=[sum(predicted[i]==column for i in relevant)for column in range(12)]
            classes.append({'true_class':label,'support':len(relevant),'predicted_class_counts':counts,'recall':counts[CLASSES.index(label)]/len(relevant)})
        persons.append({'participant':person,'class_rows':classes})
    macro=[{'class':label,'participant_macro_recall':math.fsum(row['class_rows'][j]['recall']for row in persons)/10}for j,label in enumerate(CLASSES)]
    return {'class_order':list(CLASSES),'per_participant':persons,'class_recalls':macro,'leave_one_person_out_aggregation_sensitivity':aggregation_sensitivity(scored['per_participant']),'interpretation':'Fixed-cohort descriptive aggregation only; no retraining, independent-population confidence interval or iid-trial test.'}
