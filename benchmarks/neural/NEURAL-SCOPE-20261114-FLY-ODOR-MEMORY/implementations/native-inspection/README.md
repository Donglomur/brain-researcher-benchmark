# Complete Fly native inspection operator source

This package makes the accepted complete Fly inspector and its independent auditor relocatable. It preserves all 42 files, 1,345 trials, 32,280 original field comparisons, 470 present optional fields, 2,220 absent optional slots and 1,345 diagnostic records. It prepares and checks source-derived metadata; it does not produce forecast predictions or establish a scientifically qualified benchmark.

The existing owner, worker, outer closure, three lifecycle helpers and four inspector modules are unchanged. The auditor changes only its consumer directory to the adjacent `inspector` directory. The provisioner authenticates all package members and copies this fixed graph into a fresh operator directory. It neither opens nor validates external data bodies, launches the owner, probes capacity, installs dependencies, nor selects an actual run.

## Prerequisites and external operands

Source checks and provisioning use Python 3.11 with its standard library. Actual owner execution retains its macOS `/usr/bin/vm_stat` capacity interface and macOS `ru_maxrss` units. Linux CI checks source behavior only; it does not qualify the actual owner on Linux.

Supply the exact already-reviewed archive and two complete descriptor maps. They are external and are not distributed in this package. A public source checkout alone cannot recover them. Obtain them through the programme's retained acquisition/descriptor preparation handoffs; never substitute a reduced map or another archive.

| Operand | Bytes | SHA-256 |
| --- | ---: | --- |
| Original archive | 789165393 | `6c263d5037fef4e84c1ed33fa03b6673da35cb8a8cb3aace340a1db58b300302` |
| Complete base map | 3419523 | `7eb06156b8ce98b9bb00f078ef64e8b57e99c5e1e234dc4c7222372a4d40b10c` |
| Optional descriptor map | 125940 | `e25d53f30c0404164f89553cf414c92c145bcb33eec341973cd4a43dc88ac034` |

The released source commit and reviewed manifest are the trust root. Hashes in a locally editable manifest do not defend against replacement of both code and manifest. Keep the provisioned operator workspace inaccessible to untrusted candidates; this component is trusted preparation, not a candidate sandbox.

## Provision without running

Create an ordinary UTF-8 JSON config file with exactly these four absolute paths. Symlinks and special files are rejected; nonblocking open prevents a FIFO from hanging before its file-type check. The input paths can be unavailable while provisioning; their contents are authenticated by the unchanged producer/auditor during a separately selected run.

```json
{
  "python": "/absolute/path/to/python3.11",
  "archive": "/absolute/path/to/original.zip",
  "operand_plan": "/absolute/path/to/complete-base-map.json",
  "optional_plan": "/absolute/path/to/complete-optional-map.json"
}
```

```sh
python3.11 -I -S -B provision.py --config /absolute/config.json --output /existing/canonical/parent/new-operator
```

The output must not exist; its parent must exist and be canonical. A failure after directory creation preserves the partial directory and refuses reuse. The tool never removes or overwrites an existing directory. It writes `runtime/`, `selection/REQUEST_TEMPLATE.json`, `selection/INERT_DISPATCH.sh` and `PROVISION.json`. The future `owner/` and `products/` directories remain absent. Provisioned source files and the runtime template are read-only; the selection template is private and unselected.

## Separately selected actual operation

The generated dispatch is deliberately inert. Running it without a fresh, explicit selection stops before any path read, capacity observation, process-group mutation or owner execution. Creating the directory does not select an operation.

The root operator must first review the unchanged full-operation contract and resource booking: 1,500 active wall seconds, 1,500 CPU seconds, 256 MiB serial host allocation, 128 MiB new retention, 4 GiB explicit file-read ceiling and 16 GiB managed logical-read ceiling. The prospective complete-read upper bound is 3,315,245,562 bytes. Sampling RSS is not a hard aggregate memory limit, and the memory potential estimate is a heuristic. There is no automatic retry or limit relaxation.

For an approved operation, create `selection/ROOT_DECISION.json` and a fresh mode-0600 `selection/REQUEST.json` from the template. Only `selected`, `selected_at_unix_ns`, `outside_host_bytes`, `outside_disk_bytes`, `other_selected_cpu_slots` and `root_decision` may change. The decision identity has exact `path`, `bytes` and `sha256` fields. Fill exactly the five `None` selection identity/timestamp values in `INERT_DISPATCH.sh`; keep all other script and request bytes fixed. Dispatch once within 120 seconds of selection and preserve its original terminal result. The source graph remains checked before `exec`; the inherited CPU hard limit must allow 450 seconds. This package does not automate those authorization steps.

After that same owner exits, run the existing outer closure against its recorded identities using the configured interpreter, retaining the terminal result:

```sh
/absolute/path/to/python3.11 -I -S -B /absolute/new-operator/runtime/outer_closure.py \
  --request /absolute/new-operator/selection/REQUEST.json \
  --dispatch /absolute/new-operator/selection/DISPATCH.json \
  --output /absolute/new-operator/selection/OUTER_CLOSURE.json
```

The outer closure only probes recorded PID/group identities; it does not kill unrelated processes. It does not establish complete operation if the owner result is absent. Review all failures and physical closure before any new selection. Success requires the full producer result, independent all-field comparison, exact report hash, owner completion and outer closure. `scientific_admission` remains false.

## Source checks and scientific limits

```sh
python3.11 -I -S -B -m unittest discover -s . -p test_portable.py -v
```

These generated controls cover relocation, source identity refusal, unchanged full request fields, missing external operands, immutable output refusal, inert dispatch and bounded rejection of FIFO/non-UTF-8 configs. They do not repeat the authentic 42-file pass. Previously accepted parser/auditor controls remain ancestral evidence; unchanged modules are pinned byte-for-byte.

Animal identity and the 50/51 alias, full condition/control assignment, physical odor offsets, calibration applicability, eligible forecast windows and causal normalization remain unresolved. Clock diagnostic windows are not eligible targets. No new task ID, benchmark completion, model comparison, improvement or SOTA result is claimed.
