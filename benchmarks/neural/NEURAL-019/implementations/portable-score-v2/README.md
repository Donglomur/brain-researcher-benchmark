# Portable NEURAL-019 artifact scoring

This version makes the existing 126-trial movement endpoint callable after the repository reorganization. The historical launcher computes its artifact root from the old directory depth, invokes a fixed Docker executable, and uses a host-specific Docker socket. This scorer accepts explicit operator asset paths and runs trusted parsing and metric code in the current Python environment. It executes no candidate code and performs no fitting.

The predecessor in `../registered-runtime/` remains unchanged. Its NPZ parser, numerical metric and asset manifest are imported only after checking their literal SHA256 pins. The four-reference verification retains the predecessor's frozen producer, prediction inventory, arithmetic receipt, eight-group counts and signed-comparison requirements. The CLI offers no replacement pin or manifest option.

Run with an existing Python environment containing NumPy and SciPy:

```sh
python3 benchmarks/neural/NEURAL-019/implementations/portable-score-v2/score.py validate \
  --submission /operator/submission.npz \
  --public-packet /operator/public.npz \
  --output /operator/validation.json

python3 benchmarks/neural/NEURAL-019/implementations/portable-score-v2/score.py score \
  --submission /operator/submission.npz \
  --public-packet /operator/public.npz \
  --private-targets /operator/private.npz \
  --reference-grade /operator/grade.json \
  --reference-commit /operator/prediction_commit.json \
  --output /operator/score.json
```

These paths are illustrative. Use fresh output files in an existing operator-owned directory. Exit 0 means validation/scoring completed; exit 2 reports an invalid submission or scoring error. CLI usage and output-path errors occur before grading. The Python `evaluate` entrypoint returns the same result and exit code without writing a report.

The exact registered asset pins remain authoritative. Public packet SHA256 is `98e9b00b9a641e3aa1117c2ea2d737956c3e0df5daa8e77105d34a3449ef02c2` (59,347,496 bytes). No original source NWB, neural counts tensor, training velocity tensor, private identity map, or reference prediction tensor is materialized. After authenticating the packet, only its five public assessment identity/clock/axis/unit/fingerprint fields are loaded. Candidate bytes are SHA256-bound, copied into private temporary scratch, and checked by the unchanged bounded header/CRC parser. Validation must complete before private reference or target paths are resolved. Validate mode rejects private path flags and has no private asset requirement.

The output must contain every one of the 126 anonymous assessment cases, 140 velocity bins and two signed x/y values in m/s. The primary remains equal-maze-group macro uniform-axis R² across all eight held groups. Pooled R² is secondary, negative scores remain valid, and any exactly constant group/axis retains the group and makes the primary and its contrasts undefined. The four historical references are `phase_only`, `raw137`, `pca10` and `random10`; they are authenticated and reused without recomputation.

The operator packet, targets and reference JSON are each parsed from the same immutable byte capture whose length and SHA256 were authenticated. A later file replacement cannot change that scoring operand. Historical source modules and the asset manifest are likewise executed or decoded from their authenticated bytes. Capturing the public packet retains up to 65,000,000 bytes temporarily (the fixed packet is 59,347,496 bytes); only its five metadata fields become arrays, and the byte capture is released before candidate validation. This additional trusted-host memory is a source-level bound, not a measured authentic-run resource result.

This is an operator artifact evaluator, not the historical Docker sandbox, a programme lifecycle, a direct-observation transport, a viewer, or a tool-assisted participant loop. Run it only as trusted operator code; no OS resource isolation is claimed. Generated controls exercise parsing, identity, target ordering and independent scalar metric arithmetic. They do not qualify authentic scoring, baseline performance, representation-fit provenance, or participant performance. No new scientific trial is included.

The source remains the exposed Jenkins MC_Maze development panel from DANDI `000128/0.220113.0400`, source asset `26e85f09-39b7-480f-b337-278a8f034007`. The endpoint is a declared grouped-holdout adaptation of the source, not the NLB leaderboard split/readout. The 100 ms behavior lag, symmetric retrospective filters, one animal/session, 1,340 training trials, 126 assessment trials and prior NEURAL-017/018 exposure are unchanged. Arbitrary velocity predictions can be scored, but their accuracy alone cannot establish the stronger matched latent-representation claim.

`test_score.py` uses only generated arrays and in-process test substitutions for asset pins. Those substitutions are absent from the CLI. It performs no model fits and never opens the actual public/private source assets. Run the controls through the current project test pool rather than launching additional uncoordinated numerical processes.
