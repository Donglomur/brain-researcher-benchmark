# Full-field FUS packet delivery

The [delivery implementation](../implementations/fullfield-delivery-v1/README.md)
converts a successful full-field preparation output into one lossless nine-map
packet per query: eight fixed labeled calibration maps and one unlabeled query
at the original image dimensions. It validates the full frozen intake and held
fold, preserves every query, and returns exact packet hashes for sharing the
same evidence across native, fixed-program and tool-assisted conditions.

The operator must retain outputs privately until the whole fold succeeds.
Source identity, input custody, full-resolution provider delivery, fresh
per-query contexts and protected execution require independent qualification.
The component does not implement a model runner or native MAT normalization.

Native acquisition intervals, clock synchronization, actual dtype/geometry and
Run99 constituent lineage remain unresolved. See the
[source-context record](../implementations/fullfield-delivery-v1/SOURCE_CONTEXT.json)
for verified consumer-code facts and the precise remaining inputs. Original task
definitions, source counts and qualification holds remain unchanged.
