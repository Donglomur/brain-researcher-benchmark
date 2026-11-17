# Participant delivery under calcium source condition v2

This successor uses the pinned v2 normalized pipeline and the separately
evidenced processed-input condition. The v1 delivery source remains unchanged;
all observation, query-target exclusion, complete-response collection and private
scoring logic retain their prior semantics. No authentic-data run, model fit or
process-isolation qualification is added.

Packet, operator-index and response schemas are `calcium_participant_v2`,
`calcium_operator_index_v2` and `calcium_response_v2`. Reach context stays v1.
The prepared packet carries a whitelisted source-condition summary per session
and its exposure-record digest. Locked/decoder grids, representation-specific
preprocessing, unknown actual model support and unknown fitted-trial exposure
are disclosed separately. No ambiguous `upstream_temporal_support_ms` survives.
Private source IDs, trial IDs, checkpoints and held-out target trajectories are
not copied into the summary. Full source evidence stays with the operator.

Direct numerical observation, typed trace rendering, tool-assisted responses and
frozen programs remain separately labeled modes. A program's performance is not
evidence of native/direct neural understanding. The participant receives training
labels, query neural values, lift grid and reach direction; held-out kinematics
remain in the private scorer. Training-only cell selection and same 51-row/24-joint
prediction coverage remain mandatory.

See [the original interface reference](../participant-delivery-v1/README.md) for
unchanged APIs/actions/collection conventions and
[the v2 scientific condition](../train-only-decoding-v2/README.md) for source
meaning and qualification limits. The predecessor's v1 schemas/support field are
historical. Exact source/dependency hashes appear in `SOURCE.json`; focused v2
controls include held-out-label perturbation invariance. No protected candidate
runner, isolated tool transport or authentic qualification is claimed by source
construction alone.
