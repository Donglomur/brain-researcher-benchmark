"""Concrete private reference graph. Importing this module performs no data I/O.

The source owns transforms/solvers/selection; no caller-provided learning backend
can return an invented successful fit. Complete execution remains separately gated.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections.abc import Mapping as AbstractMapping
import hashlib
import hmac
import math
import time
from ..core.custody import CustodyError, VerifiedAuthority, canonical, digest, require_digest
from ..core.plan import PrivateRecord, StudyPlan, CONDITIONS, FAMILIES
from .. import admission, transforms, estimators, scoring
from .runtime_api import numpy_api,require_domain
from ..private_store import PrivateRunStore


@dataclass(frozen=True)
class ReferenceCapacity:
    max_array_elements: int
    max_workspace_bytes: int
    max_fit_allocation_bytes: int
    max_fit_work_units: int
    max_graph_allocation_bytes: int
    wall_seconds: int
    max_scramble_cache_bytes: int

    def __post_init__(self):
        for k,v in self.__dict__.items():
            if type(v) is not int or v <= 0:
                raise CustodyError("finite positive reference capacity required: "+k)

    @property
    def binding_digest(self):
        return digest(self.__dict__)


class ReferenceWork:
    """Actual operations separate from the planned graph. No zero-cost retries."""
    def __init__(self, capacity, store=None):
        if store is not None and type(store) is not PrivateRunStore:
            raise CustodyError("concrete private artifact store required")
        self.store=store
        self.capacity=capacity
        self.deadline=None
        self.counts={}
        self.allocations=0
        self.jobs={}
        self.events=[]
        self.numeric_budgets=[]

    def start(self):
        if self.deadline is not None:
            raise CustodyError("reference worker cannot restart")
        self.deadline=time.monotonic()+self.capacity.wall_seconds

    def tick(self,name,n=1):
        if type(n) is not int or n<0:
            raise CustodyError("reference work count")
        if self.deadline is None or time.monotonic()>self.deadline:
            raise CustodyError("reference worker inactive or deadline exceeded")
        self.counts[name]=self.counts.get(name,0)+n

    def allocation(self,n,role):
        self.tick("allocation_events")
        if type(n) is not int or n<0 or self.allocations+n>self.capacity.max_graph_allocation_bytes:
            raise CustodyError("complete reference allocation budget exhausted: "+role)
        self.allocations+=n
        self.counts["bytes:"+role]=self.counts.get("bytes:"+role,0)+n

    def reserve(self,key,parents):
        if key in self.jobs:
            raise CustodyError("duplicate fit/job invocation; no blind retry")
        self.tick("jobs_reserved")
        self.jobs[key]={"status":"reserved","parents":dict(parents)}
        if self.store is not None:self.store.append_event("reference_reserved",{"key":key,**self.jobs[key]})

    def finish(self,key,result_digest,counts):
        require_digest(result_digest)
        if key not in self.jobs or self.jobs[key]["status"]!="reserved":
            raise CustodyError("unreserved fit completion")
        self.jobs[key].update(status="complete",result_digest=result_digest,counts=dict(counts))
        self.events.append({"key":key,**self.jobs[key]})
        if self.store is not None:self.store.append_event("reference_completed",self.events[-1])

    def fail(self,key,exception):
        if key in self.jobs and self.jobs[key]["status"]=="reserved":
            self.jobs[key].update(status="failed",exception_type=type(exception).__name__,message=str(exception),details=_plain_metadata(getattr(exception,"details",None)))
            self.events.append({"key":key,**self.jobs[key]})
            if self.store is not None:self.store.append_event("reference_failed",self.events[-1])

    def receipt(self):
        return {"counts":dict(sorted(self.counts.items())),"logical_allocations":self.allocations,
                "jobs":len(self.jobs),"job_statuses":{s:sum(j['status']==s for j in self.jobs.values())
                    for s in ('reserved','complete','failed')},
                "event_digest":digest(self.events),"numeric_budgets":[b.snapshot() for b in self.numeric_budgets],"meaning":"Observed reference worker calls; not physical RSS/native I/O or empirical qualification."}


class TrackedEstimatorBudget(estimators.NumericBudget):
    """Precharge every estimator allocation to the same graph, including failures."""
    def __init__(self,capacity,work):
        super().__init__(capacity.max_fit_allocation_bytes,capacity.max_fit_work_units,work.deadline)
        self.graph_work=work
        work.numeric_budgets.append(self)

    def charge(self,count,role):
        if type(count) is not int or count<0 or self.allocated_bytes+count>self.max_bytes:
            raise estimators.EstimatorError('byte_budget_exceeded',self.snapshot())
        self.tick('allocation_events')
        self.graph_work.allocation(count,'estimator:'+role)
        self.allocated_bytes+=count
        self.counters['bytes:'+role]=self.counters.get('bytes:'+role,0)+count


class TrackedNumericLimits(transforms.NumericLimits):
    """Charge each declared transform envelope conservatively before execution.

    Repeated envelopes may double-count reused operands. This is a logical bound,
    not a measurement of native allocation, heap usage or peak resident memory.
    """
    def __init__(self,capacity,work):
        super().__init__(capacity.max_array_elements,capacity.max_workspace_bytes)
        object.__setattr__(self,"work",work)

    def require(self,elements,workspace_bytes,operation):
        super().require(elements,workspace_bytes,operation)
        self.work.allocation(workspace_bytes,"transform_envelope:"+operation)


def _plain_metadata(value):
    if isinstance(value,AbstractMapping):
        return {str(k):_plain_metadata(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):
        return [_plain_metadata(v) for v in value]
    if value is None or type(value) in (str,int,float,bool):
        return value
    raise CustodyError("unexpected fitted-state metadata type")


def _numeric_array_digest(value,work):
    np=numpy_api()
    if isinstance(value,estimators.FrozenArray):
        shape,body=value.shape,value.body
        work.tick("fitted_state_hash_bytes",len(body))
        return {"shape":list(shape),"dtype":"<f8","sha256":hashlib.sha256(body).hexdigest()}
    if type(value) is not np.ndarray or value.dtype!=np.dtype('float64') or not value.flags.c_contiguous:
        raise CustodyError("canonical fitted numeric array required")
    work.tick("fitted_state_hash_bytes",value.nbytes)
    return {"shape":list(value.shape),"dtype":"float64-native-bound-byte-order",
            "sha256":hashlib.sha256(memoryview(value).cast('B')).hexdigest()}


def fitted_state_digest(model,work):
    """Stream full actual numeric state into identity; do not serialize inner copies.

    Inner fitted states are identified before release; their complete fit source,
    seeds, certificates and OOF outputs remain. Actual outer states remain for tools.
    This does not claim that released inner parameter bodies are durably retained.
    """
    if isinstance(model,transforms.Ridge):
        return digest({"type":"ridge","coefficients":_numeric_array_digest(model.coefficients,work),
            "intercept":_numeric_array_digest(model.intercept,work),"metadata":_plain_metadata(model.metadata)})
    if isinstance(model,transforms.Centroid):
        return digest({"type":"centroid","centers":_numeric_array_digest(model.centers,work),
            "metadata":_plain_metadata(model.metadata)})
    if isinstance(model,estimators.SVMState):
        return digest({"type":"svm","kernel":model.kernel,"lambda":model.lambda_,"gamma":model.gamma,
            "features":model.features,"classes":model.classes,"full_grid_dimension":model.full_grid_dimension,
            "coefficients":_numeric_array_digest(model.coefficients,work),
            "intercepts":_numeric_array_digest(model.intercepts,work),
            "training_X":None if model.training_X is None else _numeric_array_digest(model.training_X,work),
            "certificates":[c.to_dict() for c in model.certificates],"context":list(model.fit_context),
            "production_wrapper":model.production_wrapper})
    if isinstance(model,estimators.ExtraTreesState):
        stream=hashlib.sha256()
        stream.update(canonical({"type":"extra_trees","classes":model.classes,"features":model.features,
            "min_samples_leaf":model.min_samples_leaf,"max_features_rule":model.max_features_rule,
            "context":list(model.fit_context),"production_wrapper":model.production_wrapper,
            "tree_count":len(model.trees)}))
        for index,tree in enumerate(model.trees):
            stream.update(canonical([index,len(tree)]))
            for node in tree:
                raw=canonical(node.to_dict());work.tick("fitted_state_hash_bytes",len(raw))
                stream.update(len(raw).to_bytes(8,'big'));stream.update(raw)
        return stream.hexdigest()
    raise CustodyError("unknown fitted state")


class ReferenceData:
    """Trusted corpus binding. Held outer labels are not returned by fold accessors."""
    def __init__(self, *, catalogue, assessment, observations, values_by_id,
                 original_descriptors, context_key, permutation_key, source_contract_digest):
        if not isinstance(catalogue,admission.Catalogue) or not isinstance(assessment,admission.CorpusAssessment):
            raise CustodyError("typed catalogue and numeric assessment required")
        catalogue.require_valid(); assessment.require_issued()
        if (assessment.catalogue_digest!=catalogue.fingerprint or assessment.domain!=catalogue.domain
            or not assessment.numeric_checks_passed or assessment.issues):
            raise CustodyError("corpus assessment does not qualify numeric support")
        if set(values_by_id)!=set(catalogue.by_id) or set(original_descriptors)!=set(catalogue.by_id):
            raise CustodyError("full explicit neural/original-C mappings required")
        from ..admission.arrays import observations_digest
        if observations_digest(observations)!=assessment.observations_digest:
            raise CustodyError("observation set differs from assessment")
        for rid in catalogue.by_id:
            original_descriptors[rid].validate(observations[rid])
        self.catalogue,self.assessment=catalogue,assessment
        self.observations=dict(observations)
        self.values_by_id=values_by_id
        self.descriptors=dict(original_descriptors)
        self.geometry=assessment.geometry
        self.domain="authentic" if catalogue.domain==admission.SOURCE_DOMAIN else "invented"
        normalize={"dir-ap":"AP","dir-pa":"PA","ffx":"FFX","AP":"AP","PA":"PA","FFX":"FFX"}
        try:
            records=[PrivateRecord(r.record_id,r.person,r.label,normalize[r.construction]) for r in catalogue.records]
        except KeyError as exc:
            raise CustodyError("unknown construction in private ledger") from exc
        self.plan=StudyPlan(records,assessment_digest=assessment.fingerprint,
                           source_contract_digest=source_contract_digest,context_key=context_key,domain=self.domain)
        if type(permutation_key) is not bytes or len(permutation_key)<32:
            raise CustodyError("private permutation key required")
        self._permutation_key=permutation_key
        self._by_id={r.case_id:r for r in records}
        self._banks={}
        self.work=admission.WorkCounter()

    def score_records(self,ids):
        return tuple(scoring.Record(r.case_id,r.person,r.label) for r in (self._by_id[i] for i in ids))

    def opaque_rows(self,ids,outer_person,condition):
        return tuple(self.plan._opaque(["reference-row",outer_person,condition,i]) for i in ids)

    def bank(self,outer_person,capacity):
        if outer_person not in self.plan.people:
            raise CustodyError("unknown outer bank")
        if outer_person not in self._banks:
            token=self.plan._opaque(["scramble-bank",outer_person])
            self._banks[outer_person]=admission.ScrambleBank(outer_person=outer_person,outer_token=token,
                key=self._permutation_key,cache_limit_bytes=capacity.max_scramble_cache_bytes)
        return self._banks[outer_person]

    def release_bank(self,outer_person):
        # Called only after all paired arms/repetitions using this immutable bank close.
        bank=self._banks.pop(outer_person,None)
        return None if bank is None else bank.commitment

    def weights(self,ids):
        np=numpy_api()
        ids=tuple(ids); people={self._by_id[i].person for i in ids}
        complete={r.case_id for r in self.plan.records if r.person in people}
        if set(ids)!=complete or len(ids)!=len(complete):
            raise CustodyError("fit/validation weights require whole-person support")
        exact=scoring.exact_weights(self.score_records(ids))
        return np.asarray([float(exact[i]) for i in ids],dtype=np.float64)

    def labels(self,ids,*,outer_person,fit_ids):
        if tuple(ids)!=tuple(fit_ids) or any(self._by_id[i].person==outer_person for i in ids):
            raise CustodyError("held outer labels are forbidden to the reference worker")
        return tuple(self._by_id[i].label for i in ids)

    def batch(self,ids,*,outer_person,condition,view,capacity,work):
        np=numpy_api(); ids=tuple(ids)
        if condition not in CONDITIONS or view not in (('C',) if condition=='C_only' else ('N','C','NC')):
            raise CustodyError("forbidden condition/view")
        if len(ids)!=len(set(ids)) or not set(ids)<=set(self._by_id):
            raise CustodyError("explicit distinct admitted records required")
        n=len(ids); D=self.geometry.voxels
        neural=context=None
        if view in ('N','NC'):
            if n*D>capacity.max_array_elements:
                raise CustodyError("complete neural matrix capacity gate")
            work.allocation(8*n*D,"neural_matrix")
            neural=np.empty((n,D),dtype=np.float64)
            for row,rid in enumerate(ids):
                raw=admission.canonical_f64(self.values_by_id[rid],self.work)
                obs=self.observations[rid]
                if len(raw)!=obs.decoded_bytes or hashlib.sha256(raw).hexdigest()!=obs.decoded_sha256:
                    raise CustodyError("neural operand changed after admission")
                if condition=='spatial_scrambled':
                    raw=self.bank(outer_person,capacity).transform_bytes(rid,raw,self.work)
                neural[row]=np.frombuffer(raw,dtype='<f8')
            work.tick("neural_rows_read",n)
        if view in ('C','NC'):
            work.allocation(8*n*105,"C_matrix")
            context=np.asarray([self.descriptors[i].values for i in ids],dtype=np.float64)
            if context.shape!=(n,105):
                raise CustodyError("complete originalC105 matrix required")
            work.tick("descriptor_rows_read",n)
        return neural,context


@dataclass(frozen=True)
class FittedReference:
    outer_person: str
    condition: str
    view: str
    family: str
    configuration: dict
    view_bank: object
    model: object
    calibration: dict
    selection: dict
    training_rows_digest: str
    fitted_state_digest: str
    raw_query_scores: dict
    query_probabilities: dict
    numerical_certificate: dict

    def private_descriptor(self):
        return {"outer_person":self.outer_person,"condition":self.condition,"view":self.view,
                "family":self.family,"configuration":self.configuration,"calibration":self.calibration,
                "selection":self.selection,"training_rows_digest":self.training_rows_digest,
                "fitted_state_digest":self.fitted_state_digest,
                "raw_query_digest":digest(self.raw_query_scores),"probability_digest":digest(self.query_probabilities),
                "numerical_certificate":self.numerical_certificate}


class SubsetCache:
    """Exactly one outer/condition/view/training subset; never shared across them."""
    def __init__(self,engine,outer_person,condition,view,training_ids,fit_role):
        self.engine=engine; self.data=engine.data
        self.outer_person,self.condition,self.view=outer_person,condition,view
        self.ids=tuple(training_ids)
        self.fit_role=fit_role
        self.opaque_ids=self.data.opaque_rows(self.ids,outer_person,condition)
        self.outer_token=self.data.plan._opaque(["reference",outer_person,condition])
        self.subset_token=self.data.plan._opaque(["subset",outer_person,condition,view,self.opaque_ids])
        self.source_key=digest([engine.source_digest,self.data.assessment.fingerprint,condition,
            self.data.bank(outer_person,engine.capacity).commitment if condition=='spatial_scrambled' else None])
        self.w=self.data.weights(self.ids)
        self.N,self.C=self.data.batch(self.ids,outer_person=outer_person,condition=condition,
            view=view,capacity=engine.capacity,work=engine.work)
        self.banks={}; self.features={}; self.kernels={}
        c_key=digest(["C-scaler",self.outer_token,condition,view,self.subset_token,engine.source_digest])
        c_scaler=None
        if view in ('C','NC'):
            c_scaler=transforms.fit_scaler(self.C,self.w,dependency_key=c_key,
                fit_record_ids=self.opaque_ids,limits=engine.limits)
            engine.work.tick("C_scaler_fits")
        representations=(None,) if view=='C' else ('raw','rms')
        for R in representations:
            key=digest(["view-bank",self.outer_token,condition,view,self.subset_token,R,engine.source_digest])
            bank=transforms.fit_view(self.N,self.C,self.w,view=view,representation=R,
                geometry_shape=None if view=='C' else self.data.geometry.shape,
                dependency_key=key,fit_record_ids=self.opaque_ids,limits=engine.limits,
                build_pca=view!='C',c_dependency_key=c_key if view in ('C','NC') else None,
                prefit_c_scaler=c_scaler)
            self.banks[R]=bank
            if view!='C':
                engine.work.tick("N_scaler_fits"); engine.work.tick("PCA_fits")
                engine.work.tick("PCA_score_scaler_fits",2)
            ranks=(None,) if view=='C' else (None,64,256)
            for rank in ranks:
                X=transforms.transform_view(bank,self.N,self.C,pca_rank=rank,limits=engine.limits)
                self.features[(R,rank)]=X
                engine.work.allocation(X.nbytes,"cached_transformed_training")
                families=('linear_ovr_svm','rbf_ovr_svm') if view=='C' else (
                    ('linear_ovr_svm',) if rank is None else ('rbf_ovr_svm',))
                for family in families:
                    gammas=(None,) if family=='linear_ovr_svm' else (.1,1,10)
                    for gamma in gammas:
                        component=self.component_key(R,rank)
                        budget=engine.numeric_budget()
                        kernel=estimators.build_kernel_bank(X,self.w,self.opaque_ids,family,gamma,component,budget)
                        self.kernels[(R,rank,family,gamma)]=kernel
                        engine.work.tick("linear_Gram_banks" if family=='linear_ovr_svm' else "RBF_Gram_banks")

    def component_key(self,R,rank):
        return {"schema":"n073_kernel_component_key_v1","outer_context_token":self.outer_token,
            "condition":self.condition,"view":self.view,"training_subset_token":self.subset_token,
            "representation":R,"pca_rank":rank,"data_generation_sha256":self.source_key,
            "transform_source_sha256":self.engine.transform_source_digest}

    def transformed(self,cfg,ids):
        R,rank=cfg['representation'],cfg['pca_rank']
        if tuple(ids)==self.ids:
            return self.features[(R,rank)]
        N,C=self.data.batch(ids,outer_person=self.outer_person,condition=self.condition,view=self.view,
            capacity=self.engine.capacity,work=self.engine.work)
        out=transforms.transform_view(self.banks[R],N,C,pca_rank=rank,limits=self.engine.limits)
        self.engine.work.allocation(out.nbytes,"transformed_prediction")
        return out


class ReferenceEngine:
    """Full35-block/353-cell learner. A failing required fit aborts qualification."""
    def __init__(self,*,data:ReferenceData,capacity:ReferenceCapacity,authority:VerifiedAuthority,
                 source_digest:str,transform_source_digest:str,numerical_contract_digest:str,store:PrivateRunStore):
        if not isinstance(data,ReferenceData) or not isinstance(authority,VerifiedAuthority):
            raise CustodyError("typed private corpus and verified reference authority required")
        if type(store) is not PrivateRunStore or store.domain!=data.domain:
            raise CustodyError("same-domain private artifact store required")
        self.store=store
        self.data,self.capacity,self.authority=data,capacity,authority
        self.source_digest=require_digest(source_digest)
        self.transform_source_digest=require_digest(transform_source_digest)
        self.numerical_contract_digest=require_digest(numerical_contract_digest)
        runtime_receipt=require_domain(data.domain)
        if numerical_contract_digest!=runtime_receipt["contract_digest"]:
            raise CustodyError("actual numerical runtime differs from reference authority binding")
        self.bindings={"plan_digest":data.plan.binding_digest,"assessment_digest":data.assessment.fingerprint,
            "reference_capacity_digest":capacity.binding_digest,"source_digest":source_digest,
            "transform_source_digest":transform_source_digest,"numerical_contract_digest":numerical_contract_digest}
        authority.require(role='reference_fit',domain=data.domain,bindings=self.bindings)
        self.work=ReferenceWork(capacity,store)
        self.limits=TrackedNumericLimits(capacity,self.work)
        self.blocks=scoring.grid()
        self.planned=data.plan.structural_work(self.blocks)
        self.outer_done=set(); self.outer_started=set(); self.results={}; self.best_families={}; self.priors={}

    def numeric_budget(self):
        if self.work.deadline is None:
            raise CustodyError("inactive reference graph")
        return TrackedEstimatorBudget(self.capacity,self.work)

    @staticmethod
    def _raw(result):
        np=numpy_api()
        if isinstance(result,estimators.FrozenArray):
            result=result.array()
        if type(result) is not np.ndarray or result.dtype!=np.dtype('float64') or result.ndim!=2 or result.shape[1]!=25:
            raise CustodyError("reference must return complete25-score numeric vectors")
        if not np.isfinite(result).all():
            raise CustodyError("nonfinite reference scores")
        return result

    def _fit(self,cache,family,cfg,kind):
        np=numpy_api()
        X=cache.features[(cfg['representation'],cfg['pca_rank'])]
        y=self.data.labels(cache.ids,outer_person=cache.outer_person,fit_ids=cache.ids)
        opaque=cache.opaque_ids
        context={"opaque_reference_context_token":cache.outer_token,"condition":cache.condition,
            "view":cache.view,"configuration_index":cfg['index'],"fit_role":cache.fit_role}
        job=digest([self.source_digest,context,family,cfg,cache.subset_token,kind])
        self.work.reserve(job,{"training_rows":digest(opaque),"view_bank":cache.banks[cfg['representation']].metadata['dependency_key'],
                              "source":self.source_digest,"kind":kind,"fit_context":context,"configuration":dict(cfg),
                               "subset_token":cache.subset_token})
        budget=self.numeric_budget()
        try:
            key=digest(["estimator",job])
            if family=='ridge':
                model=transforms.fit_ridge(X,np.asarray(y,dtype=np.int64),cache.w,cfg['lambda'],
                    dependency_key=key,fit_record_ids=opaque,limits=self.limits)
                counters={"ridge_shared_solves":1}
            elif family=='centroid':
                model=transforms.fit_centroid(X,np.asarray(y,dtype=np.int64),cache.w,
                    dependency_key=key,fit_record_ids=opaque,limits=self.limits)
                counters={"class_template_aggregations":25}
            elif family in ('linear_ovr_svm','rbf_ovr_svm'):
                gamma=cfg.get('gamma_factor')
                bank=cache.kernels[(cfg['representation'],cfg['pca_rank'],family,gamma)]
                model=estimators.fit_svm(X,y,cache.w,cfg['lambda'],family,gamma,context,budget,
                    full_grid_dimension=self.data.geometry.voxels if cache.view!='C' and family=='linear_ovr_svm' else None,
                    kernel_bank=bank,row_ids=opaque,component_key=cache.component_key(cfg['representation'],cfg['pca_rank']))
                counters={"binary_SVM_optimizations":25}
            elif family=='extra_trees':
                model=estimators.fit_extra_trees(X,y,cache.w,cfg['min_samples_leaf'],cfg['max_features_rule'],context,budget)
                counters={"trees":256}
            else:
                raise CustodyError("unknown selected family")
            self.work.tick(kind+"_base_fit_bundles")
            self.work.tick("base_training_record_exposures",len(cache.ids))
            for name,value in counters.items():
                self.work.tick(name,value)
            # Full fitted state digest is retained before an inner model can be released.
            # Durable capture capacity belongs to the private artifact controller.
            state_digest=fitted_state_digest(model,self.work)
            numerical_evidence=([c.to_dict() for c in model.certificates]
                if type(model) is estimators.SVMState else
                _plain_metadata(model.metadata) if type(model) in (transforms.Ridge,transforms.Centroid) else
                {'tree_count':len(model.trees),'node_count':sum(len(t) for t in model.trees),'deterministic_context':context})
            self.work.finish(job,state_digest,{**counters,"training_records":len(cache.ids),
                "numeric_budget":budget.snapshot(),"numerical_evidence":numerical_evidence})
            return model,state_digest
        except BaseException as exc:
            self.work.fail(job,exc)
            raise

    def _predict(self,model,family,X):
        budget=self.numeric_budget()
        if family=='ridge':
            result=transforms.predict_ridge(model,X,limits=self.limits)
        elif family=='centroid':
            result=transforms.predict_centroid(model,X,limits=self.limits)
        else:
            result=estimators.predict_raw(model,X,budget)
        raw=self._raw(result)
        self.work.tick("raw_prediction_vectors",raw.shape[0])
        return raw

    def run_outer(self,outer_person):
        self.data.plan.fold(outer_person)
        if outer_person in self.outer_started:
            raise CustodyError("outer invocation already started; no retry after partial work")
        self.outer_started.add(outer_person)
        try:
            return self._run_outer(outer_person)
        except BaseException as exc:
            self.work.events.append({'outer_person':outer_person,'status':'failed',
                'exception_type':type(exc).__name__,'message':str(exc),
                'details':_plain_metadata(getattr(exc,'details',None)),
                'numeric_budgets':[b.snapshot() for b in self.work.numeric_budgets]})
            if self.store is not None:self.store.append_event("outer_failed",self.work.events[-1])
            raise

    def _run_outer(self,outer_person):
        self.authority.require(role='reference_fit',domain=self.data.domain,bindings=self.bindings)
        if outer_person in self.outer_done:
            raise CustodyError("outer fold already executed; no blind retry")
        if self.work.deadline is None:
            self.work.start()
        fold=self.data.plan.fold(outer_person)
        outer_records=self.data.score_records(fold.training_ids)
        outer_results=[]
        for condition in CONDITIONS:
            views=('C',) if condition=='C_only' else ('N','C','NC')
            self.priors[(outer_person,condition)]=scoring.weighted_prior(outer_records)
            self.work.tick("prior_aggregations")
            for view in views:
                blocks=[b for b in self.blocks if b['condition']==condition and b['view']==view]
                if tuple(b['family'] for b in blocks)!=FAMILIES:
                    raise CustodyError("incomplete family graph")
                oof={b['family']:{cfg['index']:{} for cfg in b['configurations']} for b in blocks}
                for validation_person,fit_people in fold.inner_people():
                    fit_ids=tuple(r.case_id for r in self.data.plan.records_for(fit_people))
                    validation_ids=tuple(r.case_id for r in self.data.plan.records_for((validation_person,)))
                    if set(fit_ids)&set(validation_ids) or set(fit_ids)&set(fold.query_ids):
                        raise CustodyError("fold overlap")
                    role=self.data.plan._opaque(["inner-fit",outer_person,condition,view,validation_person])
                    cache=SubsetCache(self,outer_person,condition,view,fit_ids,role)
                    for b in blocks:
                        family=b['family']
                        for cfg in b['configurations']:
                            model,state_digest=self._fit(cache,family,cfg,'inner')
                            Xv=cache.transformed(cfg,validation_ids)
                            raw=self._predict(model,family,Xv)
                            bank=oof[family][cfg['index']]
                            if set(bank)&set(validation_ids):
                                raise CustodyError("OOF rows written twice")
                            for rid,row in zip(validation_ids,raw):
                                bank[rid]=tuple(float(x) for x in row)
                            self.work.allocation(len(validation_ids)*25*8,"OOF_raw_scores")
                            self.store.put_json('oof_'+digest([cache.subset_token,family,cfg]),
                                {'outer_person':outer_person,'condition':condition,'view':view,
                                 'family':family,'configuration':dict(cfg),'validation_person':validation_person,
                                 'fit_state_digest':state_digest,'rows':{rid:bank[rid] for rid in validation_ids}})
                            del model,raw,Xv
                    del cache
                selections={b['family']:scoring.select_configuration(outer_records,oof[b['family']],
                    expected_indices=[c['index'] for c in b['configurations']]) for b in blocks}
                best=scoring.select_family(selections)
                self.best_families[(outer_person,condition,view)]=best
                role=self.data.plan._opaque(["outer-fit",outer_person,condition,view])
                final_cache=SubsetCache(self,outer_person,condition,view,fold.training_ids,role)
                for b in blocks:
                    family=b['family']; selected=selections[family]
                    cfg=b['configurations'][selected['index']]
                    if cfg['index']!=selected['index']:
                        raise CustodyError("noncanonical configuration indexing")
                    model,state_digest=self._fit(final_cache,family,cfg,'outer')
                    calibration=scoring.calibrate_temperature(outer_records,oof[family][cfg['index']])
                    self.work.tick("calibrators")
                    self.work.tick("temperature_bank_passes",17)
                    self.work.tick("calibration_training_record_exposures",len(fold.training_ids))
                    self.work.tick("temperature_loss_row_evaluations",17*len(fold.training_ids))
                    Xq=final_cache.transformed(cfg,fold.query_ids)
                    raw=self._predict(model,family,Xq)
                    rawbank={rid:tuple(float(x) for x in row) for rid,row in zip(fold.query_ids,raw)}
                    calibrated=scoring.apply_temperature(rawbank,calibration)
                    result=FittedReference(outer_person,condition,view,family,dict(cfg),
                        final_cache.banks[cfg['representation']],model,calibration,selected,
                        digest(final_cache.opaque_ids),state_digest,rawbank,calibrated['probabilities'],calibrated['numerical_ordering_certificate'])
                    key=(outer_person,condition,view,family)
                    if key in self.results:
                        raise CustodyError("duplicate reference result")
                    self.store.put_json('outer_'+digest(list(key)),
                        {'descriptor':result.private_descriptor(),'raw_query_scores':rawbank,
                         'query_probabilities':result.query_probabilities})
                    self.results[key]=result; outer_results.append(result)
                del final_cache,oof
        self.outer_done.add(outer_person)
        if len(outer_results)!=35:
            raise CustodyError("outer fold must produce all35 reference blocks")
        return tuple(outer_results)

    def assert_complete(self):
        if self.outer_done!=set(self.data.plan.people):
            raise CustodyError("full held-person reference graph is incomplete")
        S,N=len(self.data.plan.people),len(self.data.plan.records)
        expected={"inner_base_fit_bundles":S*(S-1)*353,"outer_base_fit_bundles":S*35,
                  "calibrators":S*35,"PCA_fits":S*S*8,"N_scaler_fits":S*S*8,
                  "C_scaler_fits":S*S*5,"PCA_score_scaler_fits":S*S*16,
                  "RBF_Gram_banks":S*S*57,"linear_Gram_banks":S*S*11,
                  "prior_aggregations":S*3,"raw_prediction_vectors":((S-1)*353+35)*N,
                  "base_training_record_exposures":((S-1)*(S-2)*353+(S-1)*35)*N,
                  "temperature_bank_passes":S*35*17,
                  "calibration_training_record_exposures":(S-1)*35*N,
                  "temperature_loss_row_evaluations":17*(S-1)*35*N}
        for key,value in expected.items():
            if self.work.counts.get(key)!=value:
                raise CustodyError(f"complete workload mismatch {key}: {self.work.counts.get(key)} != {value}")
        if any(j['status']!='complete' for j in self.work.jobs.values()):
            raise CustodyError("failed or outstanding reference jobs")
        result={"domain":self.data.domain,"plan_digest":self.data.plan.binding_digest,
                "reference_models":len(self.results),"work":self.work.receipt(),
                "additional_linear_Gram_banks":S*S*11,
                "reference_result_descriptors_digest":digest([self.results[k].private_descriptor() for k in sorted(self.results)]),
                "no_candidate_or_scoring_execution_inferred":True}
        result['completion_digest']=digest(result)
        return result
