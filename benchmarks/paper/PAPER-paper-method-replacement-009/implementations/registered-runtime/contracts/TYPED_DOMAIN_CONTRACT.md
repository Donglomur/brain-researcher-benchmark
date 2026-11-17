# Additive closed-domain contract

This contract supplements the five unchanged V1 scientific/scope/roster/gate/construction roles and the current V3 source/API index. It changes no scientific method, record schema identifier, original Pin fieldset, resource ceiling or source-authority issuer.

| Record | Actual validator | Admission consumer |
| --- | --- | --- |
| trial_session_support_v1 | schemas.trial_support | interchange.validate_trial_support; prepared validator before PreparedCase |
| numeric leaf {pin,dtype,shape,axis_ids} | schemas.numeric_leaf | read_array; every prepared/prediction/model leaf validator |
| trial_session_interchange_v1 | schemas.prepared | Preparation.complete_case; PreparedCase.document |
| trial_session_training_lineage_v2 | schemas.training | PredictionRegistry.admit before exact original training inverse |
| trial_session_prediction_v2 | schemas.prediction | PredictionRegistry.admit before tree issuance |
| trial_session_job_output_v2 | schemas.job_output | PredictionRegistry.admit before complete job transition |
| trial_session_model_state_v1 | schemas.model_state | PredictionRegistry.admit before model-tree resolution |

Every field and nested object is fixed by the actual validator source. Unsigned integer fields use the original signed64-positive domain and reject bool/float, including mathematically equal values. Typed IDs use the original two alternatives without conversion. Pins use the original three fields and exact path/length/hash validation. List order, uniqueness, domain and rank checks precede the existing semantic source inverse. Canonical-byte comparison is additional type-sensitive equality after validation; it is never a capability or a replacement for original capture identity.

Failures propagate through the existing source-owned attempted/failed state and raw-first custody; no failed metadata is coerced into a successful value, and no new retry, owner, callback, source factory or deadline is introduced. Missing real input/native qualification and scientific producers stay unavailable.
