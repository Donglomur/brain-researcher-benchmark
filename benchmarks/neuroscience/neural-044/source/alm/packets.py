"""Separate public/query features and evaluator-only labels; no source metadata leak."""
from .contracts import require, digest
from .prediction import design
from .splits import validate_fold

def _opaque(secret,value):
    import hmac,hashlib,json
    require(isinstance(secret,bytes) and len(secret)>=32,'private identifier key missing')
    return hmac.new(secret,json.dumps(value,sort_keys=True).encode(),hashlib.sha256).hexdigest()

def prediction_packet(rows,fold,feature_kind,private_key):
    classes=validate_fold(rows,fold)
    train,test=fold['train'],fold['test']
    identities=[[rows[i]['mouse'],rows[i]['session'],rows[i]['trial_id']] for i in test]
    public={'task':'NEURAL-043','case_id':_opaque(private_key,fold['id']),'claim':fold['claim'],
            'classes':classes,'feature_kind':feature_kind,
            'training_features':design(rows,train,feature_kind,classes).tolist(),
            'training_labels':[rows[i]['y'] for i in train],
            'query_features':design(rows,test,feature_kind,classes).tolist(),
            'ids':[_opaque(private_key,v) for v in identities]}
    private={'case_id':public['case_id'],'ids':public['ids'],'labels':[rows[i]['y'] for i in test],
             'units':[rows[i]['mouse'] for i in test],'source_ids':identities}
    return public,private

def response_prediction_packet(rows,held_mouse,private_key):
    from .inference import pair_design
    train=[r for r in rows if r['mouse']!=held_mouse]
    test=[r for r in rows if r['mouse']==held_mouse]
    require(train and test,'response held-mouse split')
    def identity(r):
        return [r['mouse'],r['session'],r['epoch'],r['target_id'],r['power'],r['condition'],r['follower_roi']]
    identities=[identity(r) for r in test]
    public={'task':'NEURAL-044','case_id':_opaque(private_key,['response',held_mouse]),
            'training_features':pair_design(train,True).tolist(),
            'training_responses':[r['response'] for r in train],
            'query_features':pair_design(test,True).tolist(),
            'ids':[_opaque(private_key,v) for v in identities],
            'prohibited_inputs':['held_mouse_response','held_mouse_stimulation_signals'],
            'claim':'held_mouse_response_prediction'}
    private={'case_id':public['case_id'],'ids':public['ids'],
             'responses':[r['response'] for r in test],'units':[held_mouse for r in test],
             'source_ids':identities}
    return public,private

def equal_arm_specs(public,limits):
    require(set(limits)=={'wall_seconds','cpu_seconds','memory_bytes','output_bytes','model_calls','model_tokens'},'budget fields')
    for value in limits.values():
        require(type(value) is int and value>0,'positive fixed resource limit')
    result=[]
    for arm in ('frozen_program','case_adaptive'):
        result.append({'arm':arm,'public_digest':digest(public),'limits':dict(limits),
                       'tools':['python','numpy','scipy','sklearn','supplied_reference'],
                       'state_reset':'new isolated process and input view per case',
                       'feedback':False,'target_access':False,'test_batch_adaptation':False,
                       'recipe_freeze':'before query access' if arm=='frozen_program' else 'case-local equal-view investigation'})
    return result
