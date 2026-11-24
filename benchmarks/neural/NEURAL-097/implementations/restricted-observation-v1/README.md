# NEURAL-097 restricted numeric observations

This component fills the source gap between the existing label-hidden one-query numeric ABI and a participant-readable observation. It renders all 60 neural coordinates, all eight nuisance indicators, or the unchanged 68-coordinate combined arms, and collects one complete episode into the existing `n097-query-outcomes-v1` ABI. It does not run a participant, alter the metric, add a new registered condition or enable the frozen scientific runtime.

The scientific question remains face/object prediction from six fixed magnetometers on the prospective 33-person experiment 1 panel. Direct numeric interpretation and a frozen program can receive the same numeric query and declared training context. This component binds those source representations; actual equal exposure, tool restrictions, model state and comparable compute need external execution evidence. A readable card alone does not deliver or qualify a no-tools condition.

## Observation and response interface

`make_packet(training_view, query)` accepts the existing `neural097-train-view-v2` descriptor and `neural097-query-v2` observation. The complete feature order, physical units, episode nonce, member descriptors and exact field sets are checked. Its packet includes the unchanged one-query vector, fixed coordinate names and a SHA-256 identity of canonical training-view JSON. The latter binds the declared training features, labels/group sidecars and inner folds by their member identities; it does not authenticate those files or prove their delivery. The operator must admit those public inputs before calling this component.

`render_text(packet)` displays every coordinate with round-trip numeric precision. There is no clipping, aggregation, normalization or query-dependent scaling. SIGNAL bins cover [0.1,0.3) seconds; PRE bins cover [-0.3,-0.1) seconds; each of the ten bins spans 20 ms. Neural values are the existing baseline-corrected tesla means. Nuisance columns preserve the existing duration, relevance and orientation order. The packet contains no query class, original source identity, target join, private roster, reference output or feedback. Extra input fields are refused rather than projected into the card. Calibration/training context is separately delivered; the card is not a substitute for that context.

`collect_responses(packets, responses)` consumes the operator-owned complete expected packet list for one episode and a list of existing `neural097-query-prediction-v2` responses. It checks one arm/access/training context, unique expected query identities, exact response fields, finite nonboolean probabilities, and explicit failed/abstained reasons. Unknown, duplicate or malformed responses refuse collection. A missing response becomes an explicit `failed` outcome with `reason=missing_response`; the expected roster never shrinks to the successful subset. Retain the original input artifacts whenever collection refuses. The existing registered collector rejects any failed/abstained query as an incomplete condition, so missing responses do not acquire a favorable score.

The collector returns the existing exact outcome envelope. It does not read targets or score a case. An operator must retain the complete packet list and original responses, authenticate their provenance, record participant/process/cost custody and connect every admitted episode to the protected complete campaign before scoring. The 33-person roster, both image halves, 66 folds, five feature arms, original seeds, class/cell/person weighting and existing missing-support semantics remain unchanged. The historical F/I modes are not renamed direct observation.

## Commands

Python 3 standard library only, with fresh output paths:

```sh
python3 -B observation.py render --training-view TRAIN_VIEW.json --query query-000000.json --packet observation.json --text observation.txt
python3 -B observation.py collect --packets complete-episode-packets.json --responses original-responses.json --output outcomes.json
```

`complete-episode-packets.json` is the operator-owned JSON list of all generated packets for that episode; `original-responses.json` is a JSON list of participant responses. Rendering opens only the public training descriptor and one public query, never the training payloads or protected data. Collection accepts at most 20,000 expected queries; its 100 MB packet-list and 16 MB response-file caps refuse oversize complete input rather than truncate. Card duplication adds storage beyond numeric views, so a full authentic delivery needs a separately selected resource plan. Outputs use exclusive creation. The JSON reader refuses duplicate keys and nonfinite constants.

Run generated controls from this directory with `python3 -I -B tests/test_observation.py`. For an isolated staged candidate, set `N097_SOURCE_ROOT` to the read-only registered runtime's `full-cogitate-meg-v1` directory and `N097_TEST_TMPDIR` to a writable task-owned temporary directory. Tests compare all five coordinate orders with the existing source, round-trip every displayed value including tiny/large finite floats and negative zero, exercise exact-roster failure retention, and pass collected outcomes through the existing source parser. These are software controls, not scientific trials.

## Remaining limits

Authentic source intake, the protected roster/census, preprocessing lineage, competent references, actual participant delivery, physical no-tools enforcement, exposure isolation and all 22 scientific/runtime gates remain unresolved. This component does not establish direct interpretation accuracy, a program score, equal perceptual information, a general native-versus-tool result or an original-paper replication. It is separate from the disabled registered runtime; the historical source pins and task definitions are unchanged. Integration must register this reviewed component and enroll its generated control without marking an access condition delivered or enabling deployment.

Source anchors are in [SOURCES.json](SOURCES.json). They identify the inspected contract and implementation bytes; they are not authentic-data or execution receipts.
