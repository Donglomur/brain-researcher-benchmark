"""Source-owned scientific phase composition; external boundaries are injected.

Only transport, isolated candidate/native execution and independent observation
are external. Reference/packet/schema/scoring choices are fixed here, not supplied
by an arbitrary scientific executor factory. No runtime is installed in this tree.
"""
from .strict import need, sha, text, digest
from .programme import CONFIGS, ACTORS, REGIMES, validate_contract
from .admission import validate_admission
from .splits import make_outer_assignment, fold_view
from .packets import prepare_training_packet, fit_reference_packet, predict_reference_packet, prediction_expectations
from .native_scoring import export_reproduction, validate_record, native_schema, native_keys, validate_native_bundle, native_schemas_digest, array_digest
from .scoring import validate_prediction_bundle, prediction_keys, prediction_bundle_digest, expected_prediction_digest, grade_study, finite_prediction
from .units import require_hz


def artifact_fingerprint(value):
    """Typed immutable value fingerprint; source arrays are never embedded JSON."""
    import numpy as np
    def walk(x):
        if isinstance(x,np.ndarray): return {"array_sha256":array_digest(x)}
        if type(x) is dict:
            need(all(type(k) is str for k in x),"artifact","String artifact keys required")
            return {k:walk(v) for k,v in x.items()}
        if type(x) in (tuple,list): return [walk(v) for v in x]
        return x
    return digest(walk(value))


def portable_reproduction_kernel(packet):
    from .reproduction import reproduce_case
    need(type(packet) is dict and set(packet)=={"features","psth","times","arguments"},
         "packet","Exact source-admitted reproduction packet required")
    return export_reproduction(reproduce_case(packet["features"],packet["psth"],packet["times"],**packet["arguments"]))


def reference_prediction_kernel(packet):
    return predict_reference_packet(packet["sealed"],packet["query"],observed_fit_digest=packet["observed_fit_digest"])


KERNELS = {"portable_reproduction":portable_reproduction_kernel,
           "nested_reference_fit":fit_reference_packet,"frozen_reference_predict":reference_prediction_kernel}


class _ScientificDispatcher:
    """Private composable phase seam; production uses create_dispatcher below.

    Small engineering controls exercise this same phase code on invented inputs.
    This class has no independent scientific authority or partial-study runner.
    """
    def __init__(self, contract, admission, runtime, monitor, *, admission_digest, implementation_digest):
        need(runtime is not monitor,"provider","Runtime and independent monitor must be distinct")
        sha(admission_digest); sha(implementation_digest)
        self.contract,self.admission,self.runtime,self.monitor=contract,admission,runtime,monitor
        self.admission_digest,self.implementation_digest=admission_digest,implementation_digest
        self.contexts,self.views,self.fits,self.seals={}, {}, {}, {}
        self.native,self.predictions={},{}
        self.expected_native=None
        self.validated=None
        self.closed=None
        self.context_ids=set()

    def _context_key(self,p):
        return (p["actor"],p["regime"],p["outer_fold"],p["control"])

    def _new_context(self, key, descriptor, binding):
        need(key not in self.contexts,"context","Fresh context required for every track/fold/regime/control")
        context=self.runtime.new_isolated_context(descriptor,binding)
        text(context,"opaque isolated context")
        need(context not in self.context_ids,"context","A runtime reused another scientific context")
        self.context_ids.add(context);self.contexts[key]=context
        return context

    def _dimensions(self,case):
        h=self.admission["cases"][case]
        require_hz(h["response_units"])
        return {"configuration":case,"cells":len(h["cell_ids"]),"time_windows":len(h["time_bins"]),
                "feature_ids":h["feature_ids"],"feature_groups":h["feature_groups"],
                "admission_digest":self.admission_digest,"response_units":h["response_units"]}

    def _run_reference(self,name,packet,context,binding):
        need(name in KERNELS,"kernel","Only source-owned reference kernels may be dispatched")
        # Qualified runtime isolates this exact callable/source identity. It may
        # not replace the mathematical family or return an unobserved cache.
        return self.runtime.run_reference(name,KERNELS[name],packet,context,binding,self.implementation_digest)

    def _store(self,kind,value,context,binding):
        expected=artifact_fingerprint(value)
        receipt=self.runtime.store_immutable(kind,value,context,binding)
        need(type(receipt) is dict and set(receipt)=={"handle","artifact_digest"}
             and receipt["artifact_digest"]==expected,"artifact","Immutable transport digest mismatch")
        text(receipt["handle"],"artifact handle")
        return {**receipt,"context":context}

    def _load(self,stored):
        value=self.runtime.load_immutable(stored["handle"],stored["context"])
        need(artifact_fingerprint(value)==stored["artifact_digest"],"artifact","Transported artifact changed after sealing")
        return value

    def _reproduction(self,p,binding):
        key=(p["actor"],p["configuration"],p["mode"],p["variant"])
        need(key not in self.native,"coverage","Repeated reproduction output")
        context=self.contexts[("native",p["actor"])]
        if p["actor"]=="reference" and p["requires_literal_matlab"]:
            record=self.runtime.literal_native_capture(p,context,binding,self.implementation_digest)
        else:
            packet=self.runtime.reproduction_packet(p,context,self.admission_digest)
            arguments=packet["arguments"]
            h=self.admission["cases"][p["configuration"]]
            need(arguments.get("configuration")==p["configuration"] and arguments.get("stimulus_set")==CONFIGS[p["configuration"]][2]
                 and arguments.get("mode")==p["mode"] and arguments.get("family")==p["family"]
                 and arguments.get("method")==p["method"] and list(arguments.get("cell_ids",[]))==h["cell_ids"]
                 and list(arguments.get("feature_ids",[]))==h["feature_ids"]
                 and list(arguments.get("feature_groups",[]))==h["feature_groups"],"source","Reproduction packet differs from original source/phase")
            import numpy as np
            need(np.asarray(packet["features"]).shape==(h["source_rows"],20)
                 and np.asarray(packet["psth"]).shape==(h["source_rows"],len(h["cell_ids"]),len(h["times_ms"]))
                 and np.array_equal(packet["times"],h["times_ms"]),
                 "source","Full original response/feature/clock dimensions and values must match admitted headers")
            if p["actor"]=="reference":
                record=self._run_reference("portable_reproduction",packet,context,binding)
            else:
                record=self.runtime.candidate_reproduction(p,packet,context,binding)
        validate_record(record)
        need(self.expected_native is not None and native_schema(record)==self.expected_native[key],
             "coverage","Reproduction output differs from independently pre-admitted complete schema")
        stored=self._store("reproduction",record,context,binding);self.native[key]=stored
        return {**stored,"configuration":p["configuration"],"implementation_digest":self.implementation_digest}

    def _fit(self,p,binding):
        key=self._context_key(p);context=self.contexts[key];case=p["configuration"]
        need((key,case) not in self.fits,"coverage","Repeated fit")
        view=self.views[key]
        def reader(kind,configuration,row_ids):
            return self.runtime.read_training_rows(context,kind,configuration,row_ids,binding)
        packet=prepare_training_packet(view,case,p["control"],reader,self._dimensions(case))
        input_digest=artifact_fingerprint(packet)
        if p["actor"]=="reference":
            model=self._run_reference("nested_reference_fit",packet,context,binding)
            stored=self._store("reference_fit",model,context,binding)
            model_digest=model["model_digest"]
        else:
            result=self.runtime.candidate_fit(p,packet,context,binding)
            need(type(result) is dict and set(result)=={"handle","artifact_digest","model_digest"},
                 "model","Candidate must supply an immutable source/parameter artifact")
            text(result["handle"],"candidate model handle");sha(result["artifact_digest"])
            stored={"handle":result["handle"],"artifact_digest":result["artifact_digest"],"context":context}
            model_digest=result["model_digest"]
        sha(model_digest)
        closure=self.monitor.close_fit(context,case,stored,model_digest,input_digest,binding)
        need(type(closure) is dict and closure.get("natural_complete") is True
             and closure.get("all_descendants_closed") is True and type(closure.get("exit_code")) is int
             and closure["exit_code"]==0 and closure.get("model_digest")==model_digest
             and closure.get("input_digest")==input_digest,"closure","Actual isolated fit closure/input/model binding required")
        receipt=digest(closure)
        fit={"model_digest":model_digest,"fit_receipt_digest":receipt,"input_digest":input_digest,
             "implementation_digest":self.implementation_digest,"stored":stored}
        self.fits[(key,case)]=fit
        return {k:v for k,v in fit.items() if k!="stored"}

    def _predict(self,p,binding):
        import numpy as np
        key=self._context_key(p);case=p["configuration"];context=self.contexts[key]
        need(key in self.seals and self.seals[key].get("queries_released") is True,"seal","Query inference precedes complete fit seal")
        fit=self.fits[(key,case)];view=self.views[key]
        rows=[r for r in view["queries"] if r["configuration"]==case]
        ids=[r["row_id"] for r in rows];dimensions=self._dimensions(case)
        features=self.runtime.read_query_features(context,case,ids,self.seals[key]["seal_digest"],binding)
        finite_prediction(features,(len(ids),20))
        query={"configuration":case,"row_ids":ids,"features":features,
               "familiarity":np.asarray([r["stratum"]=="familiar" for r in rows],dtype=np.int64),"dimensions":dimensions}
        if p["actor"]=="reference":
            sealed=self._load(fit["stored"])
            prediction=self._run_reference("frozen_reference_predict",{"sealed":sealed,"query":query,
                "observed_fit_digest":fit["model_digest"]},context,binding)
        else:
            prediction=self.runtime.candidate_predict(p,fit["stored"],query,fit["model_digest"],context,binding)
        record={"row_ids":ids,"time":prediction["time"],"static":prediction["static"],
                "model_digest":fit["model_digest"],"fit_receipt_digest":fit["fit_receipt_digest"],
                "response_units":dimensions["response_units"]}
        spec={"row_ids":ids,"time_shape":[len(ids),dimensions["cells"],dimensions["time_windows"]],
              "static_shape":[len(ids),dimensions["cells"]],"model_digest":fit["model_digest"],
              "fit_receipt_digest":fit["fit_receipt_digest"],"response_units":dimensions["response_units"]}
        output_key=(*key,case)
        validate_prediction_bundle({output_key:record},{output_key:spec})
        need(output_key not in self.predictions,"coverage","Repeated prediction output")
        stored=self._store("prediction",record,context,binding);self.predictions[output_key]=stored
        return {**stored,"model_digest":fit["model_digest"],"fit_receipt_digest":fit["fit_receipt_digest"],
                "query_digest":artifact_fingerprint(query),"implementation_digest":self.implementation_digest}

    def dispatch(self,p,parents,origin,deadline,binding):
        kind=p["kind"]
        if kind=="source_and_exposure_admission":
            proof=validate_admission(self.admission,self.contract)
            need(proof["admission_digest"]==self.admission_digest,"source","Original admission changed")
            self.expected_native=self.runtime.pre_admitted_native_schemas(self.admission_digest,self.implementation_digest)
            need(type(self.expected_native) is dict and set(self.expected_native)==native_keys(),
                 "schema","All independent native schemas required before any policy exposure")
            return {"admission_digest":self.admission_digest,"implementation_digest":self.implementation_digest,
                    "native_schema_digest":native_schemas_digest(self.expected_native)}
        if kind=="whole_programme_commitment":
            result=self.runtime.commit_policy(p["actor"],p["track"],binding)
            need(type(result) is dict and set(result)=={"policy_digest","source_view_digest"},"commitment","Complete source-bound policy commitment required")
            for value in result.values():sha(value)
            return result
        if kind=="commitment_barrier":
            need(set(parents)=={f"commit/{a}/{t}" for a in ACTORS for t in ("native","prediction")},
                 "commitment","All policies must be committed before numerical exposure")
            return {"commitments_digest":digest(parents)}
        if kind=="fresh_native_context":
            descriptor={"track":"native","actor":p["actor"],"admission_digest":self.admission_digest,
                        "implementation_digest":self.implementation_digest,"author_code_allowed":p["actor"]=="B",
                        "prediction_history_available":False}
            return {"context":self._new_context(("native",p["actor"]),descriptor,binding),"view_digest":digest(descriptor)}
        if kind=="reproduction":return self._reproduction(p,binding)
        if kind=="fresh_training_context":
            key=self._context_key(p)
            assignment=make_outer_assignment(self.admission["rows"])
            view=fold_view(self.admission["rows"],assignment,p["outer_fold"],p["regime"])
            self.views[key]=view
            descriptor={"track":"prediction","actor":p["actor"],"regime":p["regime"],"outer_fold":p["outer_fold"],
                "control":p["control"],"training_rows":view["training"],"inner_folds":view["inner_folds"],
                "assignment_digest":view["assignment_digest"],"admission_digest":self.admission_digest,
                "implementation_digest":self.implementation_digest,"author_code_allowed":p["actor"]=="B",
                "query_features_available":False,"native_history_available":False}
            return {"context":self._new_context(key,descriptor,binding),"view_digest":digest(descriptor)}
        if kind=="fit":return self._fit(p,binding)
        if kind=="seal_complete_fit":
            key=self._context_key(p)
            need(set(p["configurations"])==set(CONFIGS),"coverage","Every original configuration must fit before query release")
            need(all((key,case) in self.fits for case in CONFIGS),"coverage","Every actual fit closure is required before any query feature")
            models,receipts={},{}
            for case in CONFIGS:
                fit=self.fits[(key,case)]
                models[case]=fit["model_digest"];receipts[case]=fit["fit_receipt_digest"]
            artifact={"fit_models":models,"fit_receipts":receipts}
            self.seals[key]={"artifact":artifact,"seal_digest":digest(artifact),"queries_released":False}
            return artifact
        if kind=="query_features_after_seal":
            key=self._context_key(p)
            need(key in self.seals,"seal","Complete fit seal is absent")
            seal=self.seals[key]
            need(not seal["queries_released"],"seal","Query view already released")
            self.runtime.release_query_features(self.contexts[key],seal["seal_digest"],binding)
            seal["queries_released"]=True
            return {"seal_digest":seal["seal_digest"]}
        if kind=="predict":return self._predict(p,binding)
        if kind=="validate_all_candidate_and_reference_outputs":
            need(set(self.predictions)==prediction_keys() and set(self.native)==native_keys(),
                 "coverage","Every candidate/reference scientific phase must finish before validation/targets")
            seals={k:v["artifact"] for k,v in self.seals.items()}
            expected=prediction_expectations(self.admission,self.contract,seals)
            predictions={k:self._load(v) for k,v in self.predictions.items()}
            native={k:self._load(v) for k,v in self.native.items()}
            validate_prediction_bundle(predictions,expected)
            native_digest=validate_native_bundle(native,self.expected_native)
            artifact={"prediction_bundle_digest":prediction_bundle_digest(predictions,expected),
                      "expected_bundle_digest":expected_prediction_digest(expected),"native_bundle_digest":native_digest,
                      "native_schema_digest":native_schemas_digest(self.expected_native)}
            self.validated={"artifact":artifact,"predictions":predictions,"expected":expected,"native":native}
            return artifact
        if kind=="independent_full_process_and_resource_closure":
            need(self.validated is not None,"closure","Complete value/schema validation required first")
            closure=self.monitor.close_all(self.validated["artifact"],origin,deadline,binding)
            need(type(closure) is dict and all(closure.get(k)==v for k,v in self.validated["artifact"].items())
                 and all(closure.get(k) is True for k in ("all_outputs_validated","resources_passed","natural_complete","all_descendants_closed")),
                 "closure","Independent full scientific output/process/resource closure required")
            self.closed=closure
            return closure
        if kind=="load_targets_last_and_grade":
            need(self.validated is not None and self.closed is not None,"closure","No protected capability before complete validation and closure")
            v=self.validated
            # Only this branch creates/passes the actual protected-reader capability.
            return grade_study(v["predictions"],v["expected"],v["native"],
                lambda:self.runtime.load_protected_targets(self.admission_digest,binding),
                expected_native_schemas=self.expected_native,independent_closure=self.closed)
        need(False,"phase","Unknown scientific phase")

    def __call__(self,phase,parents,origin,deadline,binding):
        artifact=self.dispatch(phase,parents,origin,deadline,binding)
        return {"phase_id":phase["id"],"binding_digest":binding,"artifact":artifact,
                "receipt":{"scientific_dispatcher":"paper020_v2","implementation_digest":self.implementation_digest}}

    def observe(self,phase,result,origin,deadline,binding):
        # This adapter owns observation shape/source identity; physical process
        # observation remains the separate qualified monitor's responsibility.
        receipt=self.monitor.observe_phase(phase,result,origin,deadline,binding,self.implementation_digest)
        need(type(receipt) is dict and receipt.get("implementation_digest")==self.implementation_digest,
             "source","Independent observation must bind this actual source implementation")
        return receipt


def create_dispatcher(contract,admission,runtime,monitor,*,implementation_digest):
    """Full production builder; no partial-study, candidate-supplied or bypass flag."""
    validate_contract(contract)
    proof=validate_admission(admission,contract)
    return _ScientificDispatcher(contract,admission,runtime,monitor,
        admission_digest=proof["admission_digest"],implementation_digest=implementation_digest)
