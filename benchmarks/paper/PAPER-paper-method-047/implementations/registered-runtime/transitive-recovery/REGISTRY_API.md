# Fixed GCaMP8 resource registry API

This is an inactive source component for PAPER-paper-method-047. It preserves the original Catalogue.identities order:117 distinct source roster IDs, each with pooled/A, pooled/B, variant/A, variant/B. It neither reads that roster from disk nor establishes authentic data identity. The unchanged captured coordinator supplies its actual complete list. The outer caller must still bind the exact selected source and scientific catalogue.

Construct `Registry(journal, session)`, where `type(journal) is resource_journal.Journal` and session is the actual surviving parent's freshly selected24 lowercase hexadecimal nonce. There is no arbitrary publisher or native callback. The module imports only inert source. Native ownership, the original cgroup, endpoint isolation, physical writer/fork exclusion and outer-exit admission belong to the concrete parent; a session string is not independent authority.

`dispatch(request)` accepts only these exact dictionaries:

| op | Other fields | Successful response |
| --- | --- | --- |
| programme | identities: list of468 three-string lists | op, cases468, resources2808, maximum_events12169 |
| begin | index: next integer0..467; identity: corresponding list | op and index |
| reserve | index; role | copied original resource row |
| attempt | index; role | copied resource row with attempted=True |
| ack | index; role; identifier | copied acknowledged resource row |
| close | index; role; result: original E.retire projection | copied closure result |
| finish | index | op and index |

The six reservation roles, in order, are train-volume, train-holder, train-candidate, predict-volume, predict-holder and predict-candidate. Each is reserved, attempted, acknowledged and closed at most once. Producer candidates may close before subsequent resources are reserved, matching the unchanged scientific runtime. A new case cannot start before all six original resources were actually acknowledged and closed. A reserved-but-never-created absent resource cannot make a successful case finish.

Names are assigned solely by this parent registry. It hashes the canonical compact ASCII JSON plus newline of `[session,index,role]`, takes24 hexadecimal digits and forms `slicetca-<token>-volume` for a volume or `slicetca-<token>-<role>` for a container. Its owner value is `slicetca-<token>/<role>`. Names are checked for uniqueness within the complete session. These match the original Slice inventory/ownership contract; no broad prefix search grants cleanup authority. Containers acknowledge their exact64 lowercase hexadecimal returned ID, stored as id; volumes acknowledge their exact assigned name.

Resource rows always contain case_index, role, kind, name, owner, attempted and acknowledged, with id added only for an acknowledged container. `recovery_rows()` returns fresh copies of every known row whose original closure is not true, including state retained after append failure. It does not infer state from a stale child INTENT. Parent recovery is separate evidence and does not mutate these original outcomes.

`close.result` accepts exactly the original Slice retire success/uncertainty shapes, or the original runtime's four-field failed-retirement projection (kind,name,closed=False,error_type). Kind/name must match this registry's actual resource. An attempted but unacknowledged resource with no observed removal must remain creation_outcome_unknown=True and closed=False even if absence was observed. A not-attempted collision is preserved. A nonclosed outcome blocks new creation and cases, but permits independent original close observations for already reserved resources. Repeated closure or lifecycle requests are rejected. Recovery cannot turn a failed controller into a successful programme.

Every transition records schema gcamp8_resource_transition_v1, task_id, session, zero-based sequence0..12168 and op plus its typed fields. One complete programme has1 declaration +468 beginnings +2808 each of reserve/attempt/ack/close +468 finishes =12169 append calls. There is one active case and at most2808 resource rows. Programme records are at most1MiB; all others are at most1024 bytes when canonically encoded. The programme preflight also checks all eventual begin records against1024 bytes. IDs are nonempty strings of at most512 characters without slash, backslash or NUL; this additional source envelope is validated before activation, not asserted from authentic data inspection.

`journal.append(record)` must return the original dictionary with exactly bytes, sha256, offset and sequence. Registry retains that returned object before validating its shape and zero-based sequence. The journal owns byte framing and cumulative accounting; registry permits at most64 framing bytes beyond the relevant record cap and does not invent offset continuity or a second serialization authority. The concrete Journal must enforce its actual bounded append, fsync, original deadline and capacity rules before acknowledging durable publication.

Validated ownership state is mutated before the append attempt. An exception or invalid append return therefore leaves the original possible effect and original return/exception object retained. Dispatch is poisoned before any reply and cannot continue. No state, cost or failure is rolled back. `snapshot()` and `recovery_rows()` remain available; `natural_complete()` is false after poisoning. The snapshot includes original exception objects and original append-return objects, is bounded by the fixed programme, and is intentionally not a JSON evidence receipt. It does not format or replace the first exception. The parent separately retains actual journal partial-prefix/native observations.

`natural_complete()` requires all468 finishes, all2808 attempted/acknowledged/closed resources, and12169 successful durable append returns, with no poison or failed closure. It establishes only this lifecycle condition. The existing complete468 scientific acceptance, actual natural controller wait, cgroup emptiness, original streams, protected grading barrier, source custody, independent qualification and final external owner exit remain separate requirements.

Construction was source-only. No benchmark import, test/control, empirical input, native/Docker operation or scientific execution was performed by this slice. The parent must freeze and select finite controls and arrange independent whole-source review before claiming verification.
