# Exact runtime and action boundary

The scientific source and numerical interface are unchanged. The transport is new and requires its own source-bound native qualification before any authentic candidate action.

| Item | Contract |
|---|---|
| Candidate image | `sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156`, local and prequalified; `--pull=never` |
| Candidate | One UTF-8 Python source file, 1–131,072 bytes, original `--input` and `--out` arguments |
| Candidate resources | 1.75 CPU, 3 GiB memory and memory+swap, 64 PIDs, sixty seconds, two numerical-library threads, CPU ulimit 105/106 seconds |
| Container | Nonroot `65534:65534`, read-only root, no network, no capabilities, no new privileges, no host namespaces/devices |
| Output scratch | Eight MiB, 32 inodes, noexec/nosuid/nodev; five required files plus optional interpretation; original per-file limits and decimal 8,000,000-byte aggregate |
| Temporary scratch | 64 MiB, noexec/nosuid/nodev |
| Logs | Candidate stdout/stderr are drained by the bridge, at most 65,536 bytes each; excess fails the attempt; Docker log driver disabled |
| File limits | 1,024 descriptors, 4,000,000-byte file-size limit, core dumps disabled |
| Wire capture | 12 MiB JSON/base64 envelope; exact member names, bytes, hashes, aggregate extent; no object deserialization |
| Host | Darwin CPython 3.11.6 executable, 52,640 bytes, SHA-256 `4959d784e83b29c47836a946a6ce6ac7f8f36bb1edc90b394dde44a6376cb1a1`; `-I -S -B` |
| Whole action | 150 seconds reserved; ordinary work ends at 120 seconds, final thirty reserved for cleanup; 256 MiB managed reads, 128 MiB attempted retention reservation |
| Capacity | Fresh operator-admitted raw evidence; host reservation at least 512 MiB, VM reservation at least 3 GiB, other workloads explicitly reserved, margin at least 1 GiB; normal pressure, no observed swap/pageout growth; 15,000,000,000 bytes free plus output reserve |

The program's argument names, input contents, output names and scientific limits remain those in `TASK.md`. This transport overlays its literal path examples: the frozen candidate is materialized as `/tmp/purkinje-selected-program.py`, its output argument is `/work/output`, and the trusted wrapper is `/candidate/solution.py`. `/input` contains the exact fifteen public members; `/task` duplicates only the public task/schema text. No private reference path or selection receipt is mounted. The wrapper allows ten additional seconds to capture files after the candidate's sixty-second horizon; Docker start/capture has a seventy-five-second ceiling inside the original whole-action deadline. Candidate log overflow is an explicit transport failure, not a score threshold.

Unlike the earlier holder-volume route, this transport uses a trusted in-container multifile wrapper and a pure-standard-library host grader after candidate closure. The original numerical scorer is unchanged. These transport differences are why earlier native qualification is **not** inherited. The wrapper and candidate share a container; the wrapper is not claimed to be an additional security boundary. Host grading receives inert bytes only. Candidate isolation rests on the separately qualified container and its exact resources, mounts and image contents.

`docker_owner.py` owns only a uniquely named, labeled container and the Docker-client process groups it created. It checks initial/final inspection, client exit/reap/EOF, exact container removal and independent absence by ID and name before returning a sealed closed receipt. The local Docker socket and executable physical identity are explicitly selected. CLI configuration is empty and isolated from host credentials. The underlying daemon and OS remain trusted services; a full daemon binary closure is not claimed. Cancellation and uncertain cleanup remain operational failures rather than benchmark zeros. A hard owner deadline can leave uncertain Docker state; an external controller must retain the journal and reconcile that exact ownership before another action.

The operator-selected source review must affirm independent whole-source and public-leak review for this source-lock hash. Native qualification must bind this same hash and the exact selected runtime object, including physical executable/socket identity. At minimum, native qualification must demonstrate absent private targets in image and mounts, original input/program visibility, output capture, child/client/container termination, normal and failed candidate closure, and rejection of altered mount/resource profiles. No qualifying native receipt is included here.

Capacity and history receipts are adjudicated by the trusted external operator. Their hashes bind exact evidence, but this module does not turn arbitrary JSON booleans into independently measured capacity or authority. The operator must join the current complete workload roster and all predecessor attempts, reserve this attempt once, and record failed as well as successful elapsed/reserved costs. The historical 1167.2520854590086-second floor is a conservative recorded counter, not exact lifetime CPU/wall cost. The new whole-action reservation is added to the supplied current counter. No parallel admission or retry is authorized merely by the executable's presence.
