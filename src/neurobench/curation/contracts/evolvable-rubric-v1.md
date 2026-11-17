# Evolvable question-family rubric v1

This file is the canonical definition of C1–C10 and F0 for automated curation.
Prompts and skills should reference these definitions rather than redefine them.

- **C1 reality/execution-grounded automatic oracle.** A pinned, independent
  scoring path can decide an instance in bounded time. A clean oracle is
  necessary, not sufficient.
- **C2 quantified headroom to a raisable ceiling above the reliability floor.**
  Measure the target-specific reliability/noise ceiling and current baseline.
  The residual must be capability-limited rather than measurement-noise-limited,
  and the ceiling must have a credible way to rise.
- **C3 exogenous, time-forward, sequestered freshness.** Name the world process
  that emits new problem/truth pairs after the training cutoff and the concrete
  sequestration mechanism, such as post-cutoff release, a private split, or a
  novel measurement. Human-authored paraphrases are not freshness.
- **C4 capability-orthogonal gradient plus a mandatory falsification test.**
  Define a natural harder continuum, then test whether scale or compute alone
  closes the gap. If it does, downgrade the family rather than calling the
  gradient capability-open.
- **C5 cheap, pre-committed re-targeting rule.** State before calibration how
  difficulty changes when a rung saturates. Prefer an automatable hardness knob,
  held-out generator, or exogenous stream.
- **C6 oracle independence.** The solver must not grade itself, and a model
  output must not be treated as scientific truth without an external
  measurement.
- **C7 leakage and shortcut controls.** Put the relevant grouped splits,
  permutation/null checks, and fresh retest inside the scoring protocol.
- **C8 anti-memorization by construction.** Use a private, post-cutoff, or novel
  measurement split and record a concrete contamination argument.
- **C9 simulator validity.** A simulator-based family must pass a declared
  sim-to-real validation gate before simulator recovery counts as scientific
  evidence.
- **C10 efficiency reopening.** When accuracy saturates, reopen the frontier on
  sample, compute, or scan-time efficiency against the same reality-grounded
  target.
- **F0 immutable episode lineage.** Every generated instance records generator
  version, source inputs, parameters, splits, oracle version, artifact hashes,
  and predecessor/ratchet relation. An instance without this lineage cannot
  support a freshness or ratchet claim.

## Pass boundary

An evolvable-family `pass` requires executable C1, measured C2, an actually run
C4 falsification probe, concrete C3 and C5, independent C6, applicable C7–C9
controls, and an executed F0 freshness probe. `planned` evidence supports at
most `conditional`. C10 may reopen a saturated family, but it cannot repair a
missing reality-grounded oracle.
