"""Evaluator signature admission; participant metadata never grants authority."""
from .core import need,digest
GATES=("source_trial_identity","all_40200_trials","video_equivalence","shared_corpus_exposure",
       "video_clock_decoder","versionB_unnormalized_field","joint_estimator_conditioning",
       "independent_46_ROI_masks","coordinate_order","object_container_conversion",
       "checkpoint_identity","bidirectional_checkpoint_layout","pretraining_exposure",
       "motion_energy_S_fin_producer","category_dictionary_binding","primitive_array_extent",
       "image_dependency_lock","cgroup_descendant_cleanup","write_observer_completeness",
       "host_io_accounting","source_target_mount_barrier","fixed_adaptive_budget_parity",
       "reference_numerical_parity","scorer_numerical_parity","bootstrap_10_person_calibration",
       "literal_A_FIR_reliability_producers","publication_terms","complete_resource_profile")
_SEAL=object()
class Deployment:
    def __init__(self,body,seal):
        need(seal is _SEAL,"Only verified evaluator profile may create deployment")
        self.body=body;self.identity=digest(body)
    def require(self):
        need(set(self.body["gates"])==set(GATES),"Complete qualification gate roster")
        need(all(self.body["gates"][g]["status"]=="qualified"and self.body["gates"][g]["evidence_identity"]for g in GATES),"Open gate refuses scientific execution")
        return self
def authenticate(profile_bytes,signature,key,expected_key_hash):
    import hashlib,hmac
    from .native.io import parse
    need(hashlib.sha256(key).hexdigest()==expected_key_hash,"Operator-selected evaluator key identity")
    need(hmac.compare_digest(hmac.digest(key,profile_bytes,"sha256"),signature),"Evaluator signed full profile")
    body=parse(profile_bytes)
    need(body["task"]=="NEURAL-070"and body["execution_authority"]=="independent_evaluator","Exact task authority")
    return Deployment(body,_SEAL)

