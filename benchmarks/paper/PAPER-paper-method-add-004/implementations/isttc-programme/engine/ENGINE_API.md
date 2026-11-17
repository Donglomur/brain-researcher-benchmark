# iSTTC execution engine: source component, not qualified runtime

`execute(executor, docker, *, phase, request, program, readonly_mounts, output_dir,
source_dir, original_deadline, publish)` runs one prospective complete-context
phase. Allowed roles are `reproduction`, `improvement`, `reference`. The parent
owns full scientific input construction, independent A/B authoring and global
freezing, all five phase ordering, complete CSV/schema admission, comparisons and
the original whole-command observer. This engine transports complete artifacts;
it does not score, fit or execute during source construction.

`executor` supplies `tick()`, `read(bytes)`, `write(bytes)`. `docker` is exactly
`{binary: absolute_path, socket: absolute_path}` for an existing local CLI/socket.
The image must already exist by immutable SHA256 identity. There is no pull,
installation, networking, attached producer stdout or log retrieval.

The exact request fields are `schema`, `phase_id`, `image`, `source`,
`expected_files`, `entry`, `entry_support`, `setup_seconds`, `producer_seconds`,
`capture_seconds`, `cleanup_seconds`. Schema is `isttc_owned_phase_request_v1`.
`source` is `{bytes,sha256}` for `source_dir/SOURCE_MANIFEST.json`; `entry` is
exactly `<phase>_entry.py`. Every role requires the same complete sorted list:
`["estimates.csv","methods.json"]`. The fixed role clocks are 120 setup, 172800
producer, 1800 capture and 120 cleanup seconds.

Producer argv is always:

```
python -I -B /entry.py --request /request.json
```

All roles bind only `/input` (one authenticated complete read-only view) and
`/request.json` (one authenticated ordinary read-only file), plus the exact entry
and source helpers. Candidates additionally receive their globally frozen program
at `/program/program.py`, from 1 byte through 8 MiB. This is the new candidate-program
domain; the existing 100 MB CSV artifact domain remains unchanged. Reference
requires `program=None`. It receives no candidate code, private truth, author
notebook, original parent directory, models or another view.

The candidate helper map is exactly:

```
/trusted/entry_common.py -> entry_common.py
```

The reference map additionally binds:

```
/trusted/baseline.py -> baseline/baseline.py
/trusted/read_inputs.py -> baseline/read_inputs.py
```

For each suffix below, it binds `/trusted/source/src/isttc/<suffix>` to
`baseline/source/src/isttc/<suffix>`:

```
__init__.py
acfunc.py
tau.py
spike_utils.py
scripts/__init__.py
scripts/calculate_acf.py
scripts/calculate_tau.py
scripts/spike_train_utils.py
```

These are exact source-to-target maps; aliases, omissions and extra helpers are
refused. No private source can be rebound under the public common-helper name.
All 11 reference helpers belong to the selected source closure. Source-relative
components allow an initial underscore for the genuine `__init__.py` filenames;
canonical paths and traversal restrictions remain, and artifact names are fixed.

The caller authenticates before compiling and passes its owned immutable source
snapshot. The manifest's `files` mapping contains exact relative descriptors for
all runtime members, including both engine files and all three entries. Before
resource creation and after all native resources close, the engine captures and
authenticates the whole closure: at most 128 members, 1 MiB/member,4 MiB/pass
including the manifest. The genuinely zero-byte upstream
`scripts/__init__.py` is permitted only as an authenticated source member.
`descriptor(..., allow_empty=False)` remains nonempty by default; only source-member
capture passes `allow_empty=True`. An empty member still needs its exact SHA256
and a complete stable EOF capture. Empty source manifests, candidate programs and
output artifacts remain invalid. Parent request/input admission remains separate
and must preserve its nonempty schema. Repeated pins alone do not establish
historical execution or authoring chronology.

Each phase uses a fresh producer, dedicated nonroot holder and named tmpfs volume.
Every host bind is read-only; output is never a writable host mount. Producer
limits for all roles are 8 GiB RAM, no swap, 4 CPUs, 64 PIDs, 16 MiB shared memory,
read-only root, no capabilities, no networking and 512 MiB output tmpfs. Per-file
native bounds are `estimates.csv <=100,000,000 B` and `methods.json <=20,000 B`.
The holder's generic per-file bound is 100,000,000 B; the stricter exact native
methods bound is checked on the complete inventory before any artifact capture.
Only the two flat, positive-size, ordinary, single-link files are admitted.

Scratch is one 128 MiB noexec/nosuid/nodev tmpfs: candidates at `/tmp`, reference at
`/work`. Reference writes its temporary full baseline output under
`/work/reference`, then its trusted entry transfers the exact two files to
`/output`. The body cap 100,020,000 B fits that scratch allowance, with remaining
capacity for allocation/metadata; actual adequacy is unqualified. Reference has
no second writable `/tmp` mount. The parent must account for any other temporary
requirements before future qualification.

The holder has 128 MiB RAM, 1 CPU, no swap and a private 4 KiB `/ready` tmpfs. It is
PID1 with explicit `--init=false`. Its exact current-owner 0600 readiness marker is
atomically published after cgroup/mount guards and empty-output checks. At most 16
readiness probes share one 30-second window inside the original setup endpoint.

Capture occurs only after typed natural-zero producer state and exact owned
producer removal/absence. The holder supplies an initial metadata inventory;
source-selected 4 MiB chunks carry the current owner/role, immutable stat stamp,
exact interval/base64 length and chunk digest; every file receives an explicit
EOF probe; the final whole inventory must match. Files stream to
`output_dir/artifacts` with exclusive creation and mode0400. They remain
quarantined until a successful return. They are never loaded whole into host
memory. Parent scientific/schema admission remains necessary after capture.

`output_dir` must be fresh, existing and empty. `publish(event_name, metadata)`
must durably write a bounded sequenced journal outside that directory before
returning. Resource intents precede creation; acknowledgements retain exact IDs;
each Docker CLI PID and independent PGID is journaled. No output bodies enter
journals. The caller charges these writes and allocation separately.

Success then requires all three native resources and all CLI groups closed, a
second complete source authentication, durable final phase publication and a
check against the same original phase deadline after publication. A persisted
late receipt alone cannot authorize acceptance. Returned schema
`isttc_owned_phase_v1` includes `status="captured"`, phase/source identity, exact
six-field natural exit, producer closure before capture, three closure records,
strict eleven-field CLI records with actual phase-specific byte counts,
source-before/source-after, exact artifact pins/totals and original clock fields.
The parent additionally requires its outer natural-exit evidence.

A full phase allowance is 174,840 seconds and must fit inside the remaining
original absolute parent deadline before creation. Five maxima total 874,200
seconds, leaving 25,800 inside the parent's 900,000-second work endpoint.
Publication 900,120 and outer closure 900,240 remain separate original parent
endpoints. No retry resets any clock. These long limits are prospective; no
runtime, image, scientific or performance qualification is inherited.

Capture budgets derive from 100,020,000 total possible body bytes, not 512 MiB
capacity or a donor task's domain. The combined chunk response cap is 5,596,504 B
(4*ceil(4MiB/3)+4096 overhead). `ceil(100020000/4MiB)+2*2` gives 28 chunk/EOF commands.
Adding 128 general commands capped at 128 KiB and two inventory commands at 256 KiB
gives 158 commands and 174,003,616 B reserved CLI response bytes per phase. The
five-phase totals are 870,018,080 CLI-response bytes, 41,943,040 source-pass bytes
and 500,100,000 captured body bytes if all artifacts are retained. Parent inputs,
journals, source snapshots, allocation and other outputs are additional.
Managed counters are reservations, not measured physical I/O; failed/retired
attempts retain their costs.

Forced outer termination can leave independent host CLI groups or daemon
resources alive. The controller PGID disappearing proves neither. Receipts retain
`failure_custody_complete=false`, exact recovery identifiers,
`automatic_retry_authorized=false`, no qualification transfer and an explicit
unknown forced-stop state. Cooperative cleanup attempts every known resource
independently within the original endpoint. Ambiguous creation, timeout or
incomplete cleanup never returns success. All construction controls use invented
RAM seams: no actual processes, timers, arrays, models, fitting or scoring.
