# Reading the original public observation packets

`packet.load_packet(manifest_raw, expected_manifest, payloads, numpy)` adds a
portable binary reader to the recovered four-arm planner and scorer. It reads
the original exporter’s uncompressed `np.savez` representation. The caller
supplies captured bytes; this API performs no filesystem discovery, downloads,
candidate execution, fitting, target lookup, or grading.

Obtain `expected_manifest` from the operator-authenticated `packet_plan` result.
It contains exactly `bytes` and `sha256`. A candidate-supplied descriptor or a
hash computed from an arbitrary replacement manifest is not source authority.
The reader checks the complete public file allowlist and every payload hash
before decoding any archive. It then checks bounded, primitive one-dimensional
NPY arrays and the exporter’s exact fields and dtypes. Object/pickle arrays,
compressed or duplicate ZIP members, extra fields, incorrect extents, changed
unit aliases, missing wheel bins and query labels are refused.

All four arms retain the same permitted `u`/`u_squared` context. Neural arms
retain every dense session-local QC2/3 unit alias, including units with no
events. Only wheel arms receive wheel samples. Fitting/validation packets
include their labels; query packets do not. This does not add behavioral-history
features: the recovered source context is relative original trial position and
its square. Exact source-row chronological splits and stimulus target mapping
remain in the existing planner/`targets.py` interfaces.

`packet.case_observation(loaded_packet, case_token, numpy)` returns an operator
numerical projection of one already authenticated case. It retains native bin
IDs, within-bin event offsets, dense unit inventory, and wheel positions relative
to the trial’s first observed sample. Arrays are marked read-only. No binning,
averaging, rasterization, dropped events, inferred anatomy or outcome-dependent
selection occurs. This is a numerical interface, not a visual participant
transport or evidence of native neural understanding.

The exporter computes offsets by subtracting an absolute bin origin. The
floating-point difference between its absolute upper and lower edges need not
equal the nominal decimal `0.02`. This reader preserves the authoritative bin
and offset rather than reassigning events at a fabricated edge. Nonnegative
finite offsets and their order are checked. Exact absolute-clock membership,
recording coverage and source eligibility still require the original exporter’s
source checks; they cannot be reconstructed from these public packets alone.

The single-packet reader does not authenticate the complete 39-session,
10-mouse, 2,042-query, 312-packet panel. It does not enforce process isolation,
arm separation, model freezing or target custody. Use the existing complete
planner/scorer and an independently qualified operator runtime for those gates.
Read-only array flags are not a security boundary. No authentic packet or
participant was run during this construction.

Generated controls: `python -I -B test_packet.py` in this component directory,
with the same NumPy environment used by `test_scoring.py`. Integration must add
this command and its 12 methods to the explicit component CI inventory; this
private construction does not change shared CI or registration. Existing
historical numerical source and task contracts remain unchanged.
