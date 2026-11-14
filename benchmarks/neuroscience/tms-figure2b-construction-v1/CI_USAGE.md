# Linux construction invocation

The proposed workflow adds one `tms-figure2b-construction-controls` job on Ubuntu24.04 x86_64 while preserving all 21 existing jobs. It uses CPython3.11.18 and a fresh job-owned virtual environment. `requirements-ci.lock` fixes official NumPy2.4.6 and h5py3.16.0 cp311 manylinux wheel URLs and SHA-256 values. Their metadata requires glibc≥2.28. No source build, alternate wheel, dependency resolver expansion or automatic retry is selected.

The pinned setup-python action plus exact patch version does not itself freeze a Python toolcache archive. The owner separately requires the observed Linux libpython3.11.so.1.0 identity: 23,050,048 bytes, SHA-256 `bb41a7ec12bb82772ffb9099b944d2d338a357318548a260a58385f7e802730f`. Drift fails closed. The run records actual Python, NumPy, h5py, HDF5 and pip versions and dependency initializer hashes. This does not attest the complete OS/native/pip binary closure or equivalence to another platform.

The workflow creates only its unique `/tmp/tms-runtime-RUN-ATTEMPT` venv and `/tmp/tms-figure2b-controls-RUN-ATTEMPT` scratch. It verifies the exact owner/source selection, copies the complete selected source read-only and changes ownership only of the new inner directory. Shared runner ancestors are not changed.

The fixed harness runs as UID/GID65534, PID1 owner plus its one child, in new PID/network namespaces, with empty capabilities/groups and no_new_privs. Provider credentials and ambient environment are not passed. The finite trusted harness is the only executable workload; this is not a qualification of an arbitrary untrusted-agent sandbox. The child invokes `run_synthetic.py`, which observes the exact venv dependencies then executes the unchanged `test_source_positions.py --out ...` once. The original 146 semantic checks and full invented input geometry remain intact.

The original attempt deadline is 180 seconds, established before namespace launch. It includes complete capture and final admission publication; a later deadline failure overrides any earlier passing receipt. The outer namespace timeout is 190 seconds for failure closure only. No late or failed attempt becomes a pass. RLIMIT_CPU is 180 seconds per process; the original 180-second absolute wall deadline governs the entire attempt. Address space is limited to4GiB, descriptors to256 and each output member to16MiB. The unchanged harness additionally requires its observed peak RSS≤2GiB. These are distinct limits; address space and observed RSS are not equivalent measures.

Original source, fixture and result retention is bounded to384MiB; original plus complete artifact copy and admission records are bounded to768MiB. The complete prior synthetic shape generated roughly284MB across258 fixture/result files, including both producer and captured outputs, reference and residual arrays. The new owner also retains all source, lifecycle and runtime records. Nothing is thinned to fit. The member bound is16MiB. File-size limits are enforced; aggregate storage is observed and admitted by the bounded owner, not represented as a filesystem hard quota. Hash/validation/copy reads are separate from retention and may total up to2GiB for this fixed complete packet.

The root collector reads private0700/0600 synthetic outputs only after the namespace exits. It hashes every ordinary original, checks all146 names, complete258-file fixture census, both37-file captures, exact A/B planted-error behavior and all process/stream/deadline joins. It retains full stdout/stderr and original failures; no success is inferred from an exit code alone. Failed setup/collection produces bounded, explicitly incomplete diagnostics. The always-run artifact step retains the complete available evidence outside Git for seven days. Review the full job log if an artifact is incomplete; do not silently retry.

For a local synthetic check on an independently provisioned compatible runtime, the unchanged harness accepts:

```sh
python -I -B test_source_positions.py --out /absolute/fresh/fixtures
```

That direct command has no outer namespace/lifecycle owner and does not establish CI containment. The exact reviewed workflow provides the bounded Linux invocation. Neither command reads authentic data or runs MATLAB, a provider, model training or a scientific evaluation.
