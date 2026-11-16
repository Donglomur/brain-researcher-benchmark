"""Selected complete scientific caller; native producers remain unavailable.

The public entry cannot accept a caller dictionary as native authority. The
internal caller is concrete source, independently testable with poisoned leaves;
it does not replace scientific methods with a supplied completed answer table.
"""
from dataclasses import dataclass
from .contracts import need,ScientificUnavailable
from .preparation import session_view
from .reference import complete_reference
from .budget import finish_preserving
from .catalogue import OutputKey,StudyCatalogue
from .outputs import Collection
from .support import build as common_support
from .access import author_contexts,checked_view
from .policy import panel_name
from .resource_demand import compile_plan

@dataclass(frozen=True)
class Production:
    catalogue:StudyCatalogue
    collection:Collection
    support:object
    reference_audit:tuple
    receipts:tuple
    operation_plan:object
    cost:object
    def validate(self):
        self.catalogue.validate()
        need(self.collection.catalogue is self.catalogue,'same actual catalogue producer')
        self.collection.validate_seal()
        need(self.support.collection is self.collection,'same complete output support')
        self.support.validate()
        need(self.operation_plan.catalogue is self.catalogue,'same original resource-demand graph')
        need(tuple(c for c,_ in self.reference_audit)==self.catalogue.cells,'all selected reference cell audits')
        return self

def collect(prepared,host,owner):
    from .admission import require_native
    require_native('original production allocation, provider, isolation and observation',host,owner)
    primary=None;product=None
    try:product=_collect(prepared,host,owner)
    except BaseException as error:
        primary=error
        try:owner.fail(error)
        except BaseException as secondary:
            # Cleanup still runs and both originals escape in their source order.
            primary=BaseExceptionGroup('production and owner failure',[error,secondary])
    def cleanup():
        try:host.cleanup_remaining()
        except BaseException as error:
            if product is not None:product.collection.fail(error)
            raise
    finish_preserving(primary,(cleanup,))
    try:
        published=host.publish_production(product.validate(),owner)
        need(published is product,'publication retains actual source-owned Production')
        return published
    except BaseException as error:
        product.collection.fail(error)
        try:owner.fail(error)
        except BaseException as secondary:raise BaseExceptionGroup('publication and owner failure',[error,secondary])
        raise

def _collect(prepared,host,owner):
    """Full selected reference/participant graph; no grading or target capture.

    Every host operation below is a required native producer in API_SELECTED.md.
    None is an accepted external recipe for reference mathematics. Complete
    source reference fitting is called directly, with its original six-arm CV.
    """
    cat=prepared['catalogue'].validate();cat.policy.require_selected()
    need(prepared['policy'] is cat.policy and prepared['cells']==cat.cells,'actual selected preparation')
    host.require_entry(prepared,owner)
    plan=compile_plan(cat);collection=Collection(cat);references={};unavailable={};audits=[];receipts=[]
    def observed(kind,request,result):
        receipt=host.observe_operation(kind,request,result,owner)
        need(receipt is not None,'original operation capture is required')
        receipts.append(receipt);return receipt
    def put(panel,cell,sid,arm,body,receipt):
        cause=body if body['status']=='unavailable' else None
        return collection.put(OutputKey(panel,cell,sid,arm),body,receipt,cause)
    try:
        for cell in cat.cells:
            owner.tick();request={'cell':cell,'arms':cat.policy.reference_arms,'source':cat.source,'evaluation':cat.evaluation}
            try:
                ref=complete_reference(prepared,cell,owner)
            except ScientificUnavailable as error:
                body={'status':'unavailable','reason':error.reason,'details':error.details}
                unavailable[cell]=body;audits.append((cell,body))
                for sid in cat.evaluation:
                    for arm in cat.policy.reference_arms:put('REFERENCE',cell,sid,arm,body,None)
                continue
            need(set(ref['states'])==set(cat.policy.reference_arms),'full six-arm reference state inverse')
            need(set(ref['predictions'])=={(s,a) for s in cat.evaluation for a in cat.policy.reference_arms},'full six-arm reference prediction inverse')
            references[cell]=ref;receipt=observed('reference',request,ref)
            audits.append((cell,{'status':'complete','selection':ref['selection'],'receipt':receipt}))
            for sid in cat.evaluation:
                for arm in cat.policy.reference_arms:put('REFERENCE',cell,sid,arm,ref['predictions'][sid,arm],receipt)
        for panel in cat.policy.panels:
            pk=panel_name(panel)
            for context in author_contexts(cat,panel):
                request=context.request();mode,tool,repeat=panel;authored=None
                if mode=='F':
                    # Exactly one global source-only author; no evaluation union.
                    authored=host.author(request,{s:prepared['public'][s] for s in cat.source},owner)
                    observed('author',request,authored)
                cells=cat.cells if mode=='F' else (context.cell,)
                current=cat.evaluation if mode=='F' else context.evaluation_sessions
                for cell in cells:
                    arms=cat.policy.candidate_arms if mode=='F' else (context.arm,)
                    for arm in arms:
                        owner.tick()
                        if cell in unavailable:
                            for sid in current:put(pk,cell,sid,arm,unavailable[cell],None)
                            continue
                        train=tuple(checked_view(session_view(prepared,s,cell,arm,True),context,cell,arm,s,True) for s in cat.source)
                        tools=None
                        if tool=='T1':
                            tools=host.open_tool(context,cell,arm,references[cell]['states'][arm],owner)
                            observed('tool_lease',{'context':request,'cell':cell,'arm':arm},tools)
                        if mode=='I':
                            query_views=tuple(checked_view(session_view(prepared,s,cell,arm,False),context,cell,arm,s,False) for s in current)
                            authored=host.author(request,{'source':train,'evaluation':query_views,'tool':tools},owner)
                            observed('author',request,authored)
                        fit_request={'context':request,'cell':cell,'arm':arm,'source_sessions':cat.source,'method':authored.source_identity}
                        fitted=host.fit(fit_request,authored,train,tools,owner);observed('fit',fit_request,fitted)
                        for sid in current:
                            query=checked_view(session_view(prepared,sid,cell,arm,False),context,cell,arm,sid,False)
                            if query['status']!='complete':put(pk,cell,sid,arm,query,None);continue
                            predict_request={'context':request,'cell':cell,'arm':arm,'session':sid,'method':authored.source_identity,'state':fitted.state_identity}
                            predicted=host.predict(predict_request,fitted,query,tools,owner)
                            receipt=observed('predict',predict_request,predicted)
                            # Candidate failure/abstention is not scientific unavailability.
                            need(predicted.predictions.get('status')=='complete','participant must return full predictions')
                            put(pk,cell,sid,arm,predicted.predictions,receipt)
                        retired=host.retire_state(fitted,owner);observed('retire_state',fit_request,retired)
                        if tools is not None:
                            retired=host.retire_tool(tools,owner);observed('retire_tool',{'context':request,'cell':cell,'arm':arm},retired)
                        if mode=='I':
                            retired=host.retire_method(authored,owner);observed('retire_method',request,retired)
                if mode=='F':
                    retired=host.retire_method(authored,owner);observed('retire_method',request,retired)
        for cell,ref in references.items():
            retired=host.retire_reference(cell,ref,owner);observed('retire_reference',{'cell':cell},retired)
        collection.freeze();support=common_support(collection)
        return Production(cat,collection,support,tuple(audits),tuple(receipts),plan,owner.snapshot()).validate()
    except BaseException as error:
        collection.fail(error)
        raise
