"""Untrusted product transport, exact support and protected collection.

A valid shape is not scientific agreement. No model-state deserialization occurs
here; products are admitted only after their actual producer has been reaped.
"""
import hashlib
import math
import os
import struct
from .protocol import fields,need,integer,finite,digest,descriptor,identity,npy_header,Refusal

TYPES=tuple('T%02d'%i for i in range(1,15))
STATUSES=('complete','abstained','unsupported','failed','unavailable')
COLLECTION_STATUSES=STATUSES+('sealed_analysis_specification',)
MEMBERS={
 'T01':('cohort','split','exclusions','source_axes','transforms'),
 'T02':('states','initialization','train_support','selection','optimizer','state_changes','rng','precision','source_ancestry','context_ancestry'),
 'T03':('probabilities','row_ids','class_ids','logits','source_auxiliary','mapping'),
 'T04':('observations','normalization','variant','checkpoints','mask_crop_rng','exposure'),
 'T05':('modules','dimensions','tokens','patches','trainability','parameters','masks','normalization','optimizer','scheduler','ema'),
 'T06':('points','parameter_convention','fractions','training_counts','corpus_selection','checkpoints','formula','parameters','residuals'),
 'T07':('channel_ids','embeddings','cosines','zero_norm','physical_layout','edges','equality_policy'),
 'T08':('plan_indices','baseline_logits','noise','perturbed_logits','deltas','noise_policy','pearson_sums','denominators'),
 'T09':('row_ids','features','layer','pooling','tsne','tsne_recipe'),
 'T10':('axes','weights','valid_mask','aggregation','state','query'),
 'T11':('coverage','case_metrics','dataset_metrics','paired_effects','selections','historical_parity','qualifications','resources'),
 'T12':('issuer_receipts',), 'T13':('expected','members','genesis','local_closures','selectors','global_closure'),
 'T14':('claims','release','phase','information_limits')}


def validate_envelope(value,expected,process):
    fields(value,('schema','product_id','type','status','scope','parents','support_identity','arrays','body','reason'),'typed whole scientific product')
    need(value['schema']=='eegpt_product_v1' and value['type'] in TYPES and value['status'] in STATUSES,'known product protocol')
    for key in ('product_id','type','scope','support_identity'):need(value[key]==expected[key],'exact operator-selected product '+key)
    need(value['parents']==expected['parents'],'exact original source/state/query/producer ancestry')
    need(process['status']=='completed','original process and all descendants complete before any product admission')
    need(type(value['arrays']) is dict,'exact array map')
    if value['status']!='complete':
        need(value['body'] is None and not value['arrays'] and type(value['reason']) is str and value['reason'],'explicit absent product, never NaN or fabricated zeros')
        return value
    need(value['reason'] is None,'complete product has no invented exception');fields(value['body'],MEMBERS[value['type']],'complete scientific fields')
    for key,pin in value['arrays'].items():need(type(key) is str and key,'array semantic name');descriptor(pin)
    need(set(value['arrays'])==set(expected['arrays']),'every planned full array and no unplanned label-bearing artifact')
    need(value['support_identity']==identity(expected['support']),'complete prespecified support')
    return value


def array_rows(directory,pin,shape,ledger,*,probabilities=False):
    """Stream little-endian C-order float rows; authenticate full bytes again.

    The iterator must be exhausted. Its consumers below do not accept a prefix.
    A full-file pin prevents replacement between admission and private scoring.
    """
    descriptor(pin);need(pin['bytes']<=8000000000,'retained original classification extent cap')
    ledger.reserve('read_bytes',pin['bytes']);parent,name=directory.parent(pin['path']);fd=None;known=0;sha=hashlib.sha256()
    try:
        fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent);before=os.fstat(fd)
        need(before.st_size==pin['bytes'] and before.st_nlink==1,'ordinary exact matrix extent')
        def take(n):
            nonlocal known
            out=bytearray()
            while len(out)<n:
                ledger.guard('before_original_matrix_chunk');block=os.read(fd,n-len(out));out.extend(block);sha.update(block);known+=len(block);ledger.guard('after_original_matrix_chunk');need(bool(block),'complete matrix bytes')
            return bytes(out)
        start=take(10);need(start[:8]==b'\x93NUMPY\x01\x00','NPYv1 matrix only');hlen=int.from_bytes(start[8:10],'little');need(hlen<=4096,'bounded matrix metadata')
        head=start+take(hlen);metadata=npy_header(head,extent=pin['bytes'],shape=shape,cap=8000000000)
        width=metadata['itemsize'];columns=math.prod(shape[1:]);fmt='<'+('f' if width==4 else 'd')*columns
        need(columns*width<=ledger.limits['resident_bytes']//4,'one full scientific row fits selected memory policy; no silent tiling/change')
        for _ in range(shape[0]):
            row=struct.unpack(fmt,take(columns*width));need(all(math.isfinite(x) for x in row),'finite scientific array')
            if probabilities:need(all(0<=x<=1 for x in row) and abs(math.fsum(row)-1)<=1e-6,'complete probability simplex')
            ledger.guard('before_original_matrix_row_return');yield row
        ledger.guard('before_original_matrix_eof');tail=os.read(fd,1);known+=len(tail);ledger.guard('after_original_matrix_eof');need(not tail and sha.hexdigest()==pin['sha256'],'complete exact original matrix pin')
        after=os.fstat(fd);need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'matrix unchanged while read');directory.verify()
    finally:
        from .protocol import _close,account,observation,Refusal
        import sys
        primary=sys.exc_info()[1];failures=_close((fd,parent));account(ledger,'read_bytes',known,failures)
        try:ledger.guard('after_original_matrix_close')
        except BaseException as exc:failures.append(observation(exc))
        if failures:raise Refusal('original matrix close/accounting failure',observation={'primary':None if primary is None else observation(primary),'secondary_failures':failures,'known_read_bytes':known}) from primary


def validate_scientific_body(value,expected):
    """Source/control admission, not a replacement for independent adjudication."""
    if value['status']!='complete':return
    t=value['type'];b=value['body'];s=expected['support']
    if t=='T03':
        need(b['row_ids']==s['row_ids'] and b['class_ids']==s['class_ids'],'every original row/class in original order')
        need(b['probabilities'] in value['arrays'],'required probabilities bound to actual captured matrix')
        need(b['mapping']==s['mapping'],'common versus source-native semantic mapping remains explicit')
        need(b['source_auxiliary'] is None or s['source_auxiliary_allowed'],'source-only four-logit diagnostics never hidden A requirement')
        need((b['source_auxiliary'] is None)==(s.get('source_auxiliary') is None),'all selected original source auxiliary outputs retained')
        if s.get('source_auxiliary') is not None:
            fields(b['source_auxiliary'],('kind','original_argmax','semantic_positive_column','semantic_negative_probability','native_argmax_not_binary_argmax'),'original4logit binary semantic transport');need(b['source_auxiliary']['kind']==s['source_auxiliary'] and b['logits']=='source_logits' and b['source_auxiliary']['original_argmax']=='source_argmax' and b['source_auxiliary']['semantic_positive_column']==1 and b['source_auxiliary']['semantic_negative_probability']=='one_minus_positive_probability' and b['source_auxiliary']['native_argmax_not_binary_argmax'] is True,'exact source-semantic distinction')
    elif t=='T02':
        need(type(b['states']) is list and b['states'] and not value['arrays'],'opaque states use captured file descriptors, never evaluator numeric decoding')
        for member in b['states']:descriptor(member)
        need(len({r['path'] for r in b['states']})==len(b['states']),'all opaque state files unique')
        need(b['train_support']==s['train_support'] and b['selection']==s['selection'],'state fit/selection uses exact eligible original support')
    elif t=='T04':
        need([x['id'] for x in b['observations']]==s['observation_ids'],'all selected loss steps/epochs retained')
        for row in b['observations']:
            fields(row,('id','step','epoch','partition','LA_numerator','LA_denominator','LR_numerator','LR_denominator','total','checkpoint','crop','mask','rng','exposure'),'complete raw loss primitive')
            need(row['partition'] in ('train','validation'),'original complete loss partition')
            for key in ('LA_numerator','LR_numerator','total'):finite(row[key],key)
            for key in ('LA_denominator','LR_denominator'):integer(row[key],key,1)
        need(b['normalization']==s['normalization'] and b['variant']==s['variant'],'exact source or paper loss recipe')
    elif t=='T05':
        need(set(b['modules'])==set(s['module_ids']),'complete architecture modules; comparator judges values')
        need(set(b['parameters'])==set(s['parameter_categories']),'total/encoder/head identities separate')
    elif t=='T06':
        need([r['id'] for r in b['points']]==s['point_ids'],'all eight sizes or four data fractions, no favorable subset')
        need(b['parameter_convention']==s['parameter_convention'] and b['formula']==s['formula'],'predeclared scaling estimand')
        need(len(b['residuals'])==len(s['point_ids']),'all point residuals')
    elif t=='T07':
        need(b['channel_ids']==s['channel_ids'] and len(b['channel_ids'])==58,'all58 ordered channels')
        need(set(b['edges'])==set(s['threshold_ids']),'complete threshold/equality branches')
        need(b['equality_policy']==s['equality_policy'],'unresolved original caption/prose differences stay named')
    elif t=='T08':
        need(b['plan_indices']==s['indices'],'every planned query/channel/draw/class cell')
        need(b['noise_policy']==s['noise_policy'],'full fixed noise distribution/seed/draw count')
    elif t=='T09':
        need(b['row_ids']==s['row_ids'] and b['layer']==s['layer'] and b['pooling']==s['pooling'] and b['tsne_recipe']==s['tsne_recipe'],'complete prespecified feature/t-SNE population and recipe')
    elif t=='T10':need(b['axes']==s['axes'] and b['aggregation']==s['aggregation'],'all planned heads/layers/query/key/time/channel axes')
    elif t=='T14':
        need([r['claim_id'] for r in b['claims']]==['CL%02d'%i for i in range(1,25)],'all24 claim interpretations')
        for row in b['claims']:
            fields(row,('claim_id','status','evidence','numerical_statement','uncertainty_scope','counterevidence_alternative','falsifier','information_cost_limits'),'complete scientific reasoning claim')
            need(row['status'] in ('supported','contradicted','indeterminate'),'no agreement-with-paper reward')
            need(set(row['evidence'])<=set(s['released_evidence']),'interpretation cites only actual released evidence')
        need(b['phase'] in ('pre_score_hypothesis','post_score_interpretation'),'timestamped separate reasoning phase')


def admit_producer(expected,process_receipt,issuer):
    """Join a scheduled obligation to its original host-issued request, never
    to a product's claimed role or rewritten expected parents."""
    process=issuer.verify(process_receipt,'process');scope=process['scope'];body=process['body']
    need(scope['kind']=='episode','scientific product from actual original episode')
    spec={k:expected['scope'][k] for k in ('mode','access','policy_id','actor_role','dataset','outer_fold','method')}
    need(scope['spec']==spec and issuer.episodes[scope['episode_id']]['scope']==scope,'actual producer matches complete original expected episode')
    request=body['issued_request'];need(identity(request)==body['request_identity'],'immutable actual host-issued request identity')
    rep=body['repetition'];need(request['scope']=={k:v for k,v in spec.items() if k!='actor_role'}|{'repetition':rep},'actual request private episode/repetition join')
    expected_rep=expected['scope'].get('repetition')
    need(expected_rep==rep or (expected_rep is None and rep==0 and expected.get('plan',{}).get('repetition','absent') is None),'original product repetition; nonrepeated diagnostic only at original zero call')
    call='PREDICT' if expected['type']=='T03' else expected['plan']['producer_call']
    need(body['call']==request['call']==call,'original allowed scientific producer API call')
    templates=[v for v in request['output_contract']['products'] if type(v) is dict and v.get('product_id')==expected['product_id']]
    need(len(templates)==1,'one exact requested original output obligation')
    bound=dict(expected);bound['parents']=[p['record_sha256'] for p in process['parents']]
    need(request['public_parent_identities']==bound['parents'] and templates[0]==bound,'actual requested output/support/parents equal immutable scheduled obligation')
    need(body['original_budget_record']['status']=='completed','original scientific producer fully completed')
    need(body['input_identity']==body['request_identity'] and body['source_identity']==request['source_identity'],'actual executed request and source match host-issued producer obligation')
    if expected['type']=='T03':
        def one(kind):
            rows=[issuer.verify(p,kind) for p in process['parents'] if p['kind']==kind];need(len(rows)==1,'one original query '+kind);return rows[0]
        state=one('state');query=one('prepared');closed=one('development_close')
        selected=closed['body']['selections']['selected'][str(rep)]
        need(selected['state'] in process['parents'] and state['scope']==scope and query['scope']==scope and closed['scope']==scope,'query uses actual sealed selected state of same episode')
        need(state['body']['repetition']==rep and query['body']['repetition']==rep and query['body']['role']=='query','exact original state/query repetition and role')
        need(request['source_identity']==state['body']['source_identity'],'actual selected predictor source')
        inputs={r['name']:r for r in request['inputs']}
        need(inputs['fitted']['public_identity']==state['body']['state_identity'] and inputs['query']['public_identity']==query['body']['public_document']['sha256'],'actual selected model and full query inputs')
    return bound


class Collection:
    def __init__(self,expected,issuer):
        self.expected={r['product_id']:r for r in expected};need(len(self.expected)==len(expected),'unique complete expected product identities');self.members={};self.issuer=issuer;self.closed=False
    def add(self,product,capture_receipt,process_receipt):
        self.issuer.budget.guard('before_original_collection_'+'add')
        need(not self.closed and product['product_id'] in self.expected and product['product_id'] not in self.members,'one actual result for one original obligation')
        process=self.issuer.verify(process_receipt,kind='process');capture=self.issuer.verify(capture_receipt,kind='capture')
        need(capture['body']['product_identity']==identity(product) and process_receipt in capture['parents'],'actual capture bound to original producer')
        bound=admit_producer(self.expected[product['product_id']],process_receipt,self.issuer)
        need(capture['scope']==process['scope'],'capture from the same actual producer scope')
        validate_envelope(product,bound,process['body']['original_budget_record']);validate_scientific_body(product,bound)
        self.members[product['product_id']]={'status':product['status'],'product':product,'capture':capture_receipt,'process':process_receipt}
    def seal_analysis(self,product_id,analysis_receipt,primitives):
        self.issuer.budget.guard('before_original_collection_'+'seal_analysis')
        need(not self.closed and product_id in self.expected and product_id not in self.members,'one original protected analysis obligation')
        expected=self.expected[product_id];need(expected['type']=='T06','only assessment-dependent complete scaling uses this declarative post-target reduction')
        record=self.issuer.verify(analysis_receipt,'analysis');need(record['scope']['kind']=='episode' and not self.issuer.targets_open,'actual pretarget frozen analysis specification')
        need(record['body']['analysis_specification']==expected['support']['analysis_specification'],'complete prespecified formula and all original point identities')
        need(set(primitives)==set(expected['support']['primitive_product_ids']),'all required frozen state/prediction/loss primitives; no favorable subset')
        need(all(pid in self.members and self.members[pid]['status']=='complete' for pid in primitives),'all protected analysis primitives actually captured before barrier')
        episode=self.issuer.episodes[record['scope']['episode_id']];need(episode['final_selection'] is not None and analysis_receipt['ordinal']<episode['final_selection']['ordinal'],'A09 analysis specification frozen before original development closure/query')
        process_receipts=[r for r in record['parents'] if r['kind']=='process']
        for process in process_receipts:admit_producer(expected,process,self.issuer)
        processes=[self.issuer.verify(r,'process') for r in process_receipts];need(processes and all(r['body']['call']=='ANALYZE' and r['body']['original_budget_record']['status']=='completed' for r in processes),'actual complete pretarget A09 producer, not a caller-created analysis dictionary')
        self.members[product_id]={'status':'sealed_analysis_specification','analysis':analysis_receipt,'primitives':primitives,'protected_result_pending':True,'scientifically_complete':False}
    def unavailable(self,product_id,reason,original_receipts):
        self.issuer.budget.guard('before_original_collection_'+'unavailable')
        need(not self.closed and product_id in self.expected and product_id not in self.members,'one explicit unresolved obligation')
        need(type(reason) is str and reason and original_receipts,'gating/failure source evidence, never fabricated successful production')
        for r in original_receipts:self.issuer.verify(r)
        self.members[product_id]={'status':'unavailable','reason':reason,'original_receipts':original_receipts}
    def seal(self):
        self.issuer.budget.guard('before_original_collection_'+'seal')
        need(not self.closed and set(self.members)==set(self.expected),'full programme closure, no omitted failure or native branch');self.closed=True
        statuses={k:sum(v['status']==k for v in self.members.values()) for k in COLLECTION_STATUSES}
        return {'expected':list(self.expected),'expected_identity':identity(list(self.expected.values())),'members':self.members,'counts':statuses,'transport_complete':statuses['complete']+statuses['sealed_analysis_specification']==len(self.expected),'protected_derived_outputs_pending':statuses['sealed_analysis_specification'],'scientifically_complete':False,'scientific_adjudication_pending':True}


def scientific_completion(collection,grades,gates,reference_selection,claim_reports,within_family_contrasts):
    """A complete transport or an empty error list cannot establish science."""
    need(type(grades) is dict and set(grades)==set(collection['expected']),'every expected product independently adjudicated')
    need(len(gates)==24 and set(gates)=={'G%02d'%i for i in range(1,25)},'every original gate retained')
    need(all(type(x) is dict and set(x)>= {'status','evidence'} for x in grades.values()),'typed actual grade, including failed numerical reducer')
    need(set(reference_selection)=={'A','B'} and all(len(v)==43 for v in reference_selection.values()),'all same-fold reference choices and all arms')
    need(len(claim_reports)==24,'full reasoning report')
    from .contrasts import completion_ready
    contrast_complete=completion_ready(within_family_contrasts)
    return contrast_complete and collection['transport_complete'] and all(x['status']=='adjudicated' and x['evidence'] for x in grades.values()) and all(x['status']=='qualified' and x['evidence'] for x in gates.values()) and all(x['status']=='selected' for arm in reference_selection.values() for x in arm) and all(x['status']=='adjudicated' for x in claim_reports)
