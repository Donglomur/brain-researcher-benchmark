# Submit a CA trajectory-analysis program

This local interface evaluates a protocol-guided component of PAPER-FIND-013. It does not provide a complete final-paper packet or a paper-versus-code experimental condition. The public input consists of clean processed trajectories and onset positions; `PFs` and derived answers are excluded.

Submit one UTF-8 Python source file, at most 65,536 bytes. The isolated command is:

```
python -I /program/program.py --input /input --out /output
```

The five read-only public files are `CA1.mat`, `CA3.mat`, `manifest.json`, `PUBLIC_CONTRACT.json` and `METHODS.md`. The contract gives exact identities and schemas. METHODS gives the onset/full-clock handling, 6 cm conversion, 15-lap span eligibility, all three threshold/denominator conventions, animal assignments, summaries, orientations, undefined states and exact submission wrappers. The same environment as the qualified local reference is reused; no package installation or network is available.

Write only `/output/submission.json`, no more than 5,000,000 bytes. Its schema supports complete, partial and whole-abstention reports. The candidate has 20 seconds, 1.75 CPU and 3 GiB; the complete reviewed operator attempt allows 60 seconds for setup, execution, scoring and cleanup. Arbitrary wrong or partial answers receive the unchanged separate error/coverage/status scores; no numerical-performance floor is imposed. Invalid or missing outputs and nonzero program exits remain explicit outcomes. The producer is removed before output admission and private grading.

After registration and an explicit per-attempt operator review/allocation, the command is:

```
python3 tools/neurobench.py run PAPER-FIND-013 --program PATH.py --output artifacts-build/FRESH --review REVIEW.json --other-reserve-bytes 352000000
```

`outer_receipt.json` reports execution/cleanup separately from `result_status`. A graded full score is at `grade/output/score.json`; a handled pre-grade boundary result is at `result.json`. A software `passed` receipt is not a scientific success or an independent model result.

The capacity successor preserves the qualified scientific and isolation paths. Each attempt needs a separate root review with the current complete image/reservation inventory and latest closed additive cost; the source-only capacity policy is not an allocation. The five-file public view now includes the exact existing JSON token, shape and scalar limits in METHODS.md. Historical execution evidence remains historical; this capacity successor has not been run merely for registration.
