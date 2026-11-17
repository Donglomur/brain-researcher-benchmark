# Exact public source preparation for NEURAL-058

This companion restores the historical source namespace expected by the unchanged NEURAL-058 central runtime. It repairs source availability after repository relocation. It does not qualify the benchmark, approve a campaign, create protected inputs, or execute a neural-data analysis.

The current `../score.py` is the exact frozen original entry. Its operational path guard rejects its relocated checkout path; its `--help` still works. Rewriting that guard alone would violate its self pin and leave the historical source, freeze, registration, and argument checks inconsistent. Preparation instead copies 326 exact public files (3,010,666 source bytes) into a fresh directory under their original identities. The original code, metadata, hashes, qualification gates, metrics, population, and resource limits remain unchanged.

`SOURCE_MAP.json` binds each historical identity to a current public file and its original byte length and SHA-256. Four historical framework helpers differ from their current counterparts. The exact originals are included in `historical-tools/`, recovered from verified public ancestor `8a07b93da68e8b9cf193cdba7d09faa17bf56a43`; `PROVENANCE.json` records their origin and original pins. They are versioned historical dependencies, not replacements for the current framework.

From a trusted checkout, review and authenticate the companion against [`DESCRIPTOR.json`](../../../../../integrity/current-closures/relocation-neural058/DESCRIPTOR.json), then run:

```sh
python3 -I -S -B benchmarks/neural/NEURAL-058/implementations/registered-runtime/source-resolution/prepare_sources.py \
  --repository /ABSOLUTE/PUBLIC-CHECKOUT \
  --destination /ABSOLUTE/NEW-SOURCE-ROOT \
  --max-read-bytes 16777216 \
  --max-write-bytes 8388608 \
  --max-live-bytes 1048576 \
  --deadline-seconds 120
```

Replace both absolute-path placeholders. Paths must be canonical, with ordinary directory ancestors; the destination must be absent, outside the source checkout, and have an existing parent directory. This step reads only the explicitly mapped public sources and writes its newly owned output. It preflights every source before creating the destination, then recaptures and checks each file again while copying. Source files must be regular, single-link files; symbolic links and changed source bodies are refused. A partial failure may leave the newly created directory. Use a new destination for a retry; no failed directory is silently removed or reused.

Success requires **both exit status 0 and `SOURCE_PREPARATION.json`** with state `source_prepared_not_qualified`. A receipt alone is insufficient. This is not an atomic publication protocol or protection against an adversarial concurrent owner changing the prepared tree after verification. The unchanged runtime authenticates its sources again before any operation.

The byte budgets prospectively account for map reads, two source captures, file writes and readback, and a conservative 64 KiB receipt/terminal reservation. Receipt filesystem I/O is additionally counted. The reported observed counters describe successful filesystem reads/writes; reservations include attempted reads and terminal encoding capacity, not observed physical disk I/O. A failed CLI can emit one separately bounded 4 KiB diagnostic even when no valid budget can be established. `--max-live-bytes` counts retained source content buffers plus transient source/readback buffers; it is **not an RSS, Python-object, allocator, or OS-cache limit**. The deadline is checked between bounded operations, not a preemptive CPU or wall-time kill. Interpreter startup and script loading precede these preparation counters. The frozen runtime has its own separate unchanged limits.

After successful preparation, use the prepared root as the working directory. The original collection entry is:

```text
authoring/delivery-20261105/common/remaining-builds-wave29/neural058-complete-design/implementation-v1/central-integration-v1/entry.py
```

The original grading entry is `benchmarks/neuroscience/neural-058-brainwide-wheel/score.py`. Their unchanged central source-manifest pin is 886 bytes and SHA-256 `f3df6e660df0c81f330f6c2e7be255a95d079be408615a0842cfe040d953f214`. The exact original command, interpreter, argument order, selected review and protected authority requirements still apply; see the [current programme guide](../../../docs/current-programme.md).

The retained registration is `verification.status = not_run`. Consequently, an operational invocation currently authenticates the recovered source closure and refuses at `not qualified: complete NEURAL058 central interface`, before review, program, output, or protected operands are opened. Preparation does not remove that hold. Generated source-only tests cover the default/full collection modes and grading separately, observing zero protected operand opens and zero native launches; these checks provide no benchmark result or scientific qualification.
