# SMC-RNN author reference calibration

Both complete author predictions and both original scoring children produced authenticated aggregate results. The existing noncausal aggregate was accepted as **recovered reference-calibration output**. Its supervisor stage remains failed: `success: false`, exit 1, `ValueError: Scorer identity changed`. No rerun occurred.

| Author arm | Metric | Published | Observed | Observed − published |
|---|---|---:|---:|---:|
| Causal | co-bps | 0.3225 | 0.322129780 | −0.000370220 |
| Causal | vel R2 | 0.8479 | 0.845960503 | −0.001939497 |
| Causal | psth R2 | 0.5927 | 0.593137726 | +0.000437726 |
| Causal | fp-bps | 0.2184 | 0.219242115 | +0.000842115 |
| Noncausal | co-bps | 0.3407 | 0.341016088 | +0.000316088 |
| Noncausal | vel R2 | 0.8902 | 0.889860746 | −0.000339254 |
| Noncausal | psth R2 | 0.5963 | 0.595833124 | −0.000466876 |
| Noncausal | fp-bps | 0.2417 | 0.241865445 | +0.000165445 |

All eight absolute differences are below 0.002 and the prespecified 0.01 diagnostic tolerance. This is calibration evidence, not an accepted reproduction threshold, independent uncertainty estimate, candidate improvement or SOTA result. The [companion JSON](smc-author-calibration-20261117.json) retains unrounded values and provenance. The JSON draft and publication-pending flags record the original report-assembly stage.

The implementation is `5d63c9c2feda1243f23b791cbde949e11fa38aea`; author source is `c808c76ad940491b0a14d2671e3884140aa61258`. Both selected 36-D, 512-unit recipes used **192 particles × 32 repeats**, `smooth=False`, and seeds 20261117/20261118. The complete MC_Maze 20-ms test panel has 2,295 training and 574 evaluation trials, 137 held-in/45 held-out neurons, 35 observed bins and ten forward bins; validation preparation has 1,721/574 trials. All eight source arrays, input order/content hashes, selected checkpoint identities and original four-metric scorer are bound in the JSON. DANDI `000128` version `0.220113.0400` was used; the paper did not pin that revision, and close scores do not prove exact published-checkpoint linkage.

The causal supervised stage succeeded. For noncausal scoring, the child exited 0, report and stdout matched, all aggregate/provenance checks passed, and cleanup reaped the child without signals. The supervisor's mismatching process-observation tuple was not retained, so the exact cause is **unknown**; a terminal observer race is only a hypothesis. The detached root disposition (`R022` in the JSON) admits the existing scalar output only. The failed receipt, ledger status and full 39.573543 CPU-second stage charge remain intact.

**Counts:** two completed full author prediction runs, two scoring children, one failed supervised scoring stage, zero scoring retries, zero candidate runs, no LLM study. Two earlier bounded characterization probes are separate. Accounting revision 9 charges **60,720.795396 CPU seconds**, leaving 14,279.204604 of the 75,000-second ceiling for recorded work. Charges include measured costs and labeled conservative debits, failures and guards; later review costs require reconciliation. Residual budget grants no new execution authority.

Both prediction freezes preceded target acquisition. The operator scorer privately read the canonical targets after those freezes; report assembly inspected only aggregate and metadata records. No payloads are published. Original test targets have been public since January 2026 and are not untouched. Their pinned SHA256 is `f2f434d30193251b58e6a693381fdd185c8fbc0e47d38f8810e65295bc42c865`. No new RNN training, candidate search or scorer change occurred; original Ridge decoder fitting is part of the metric.

The primary task is official offline MC_Maze: all 35 supplied held-in bins may be used, while withheld neurons, future activity and test behavior remain protected. Author prefixes are optional information-matched conditions, not universal restrictions or evidence of strict-online performance. A single averaged inference is not independent uncertainty evidence. Later LangevinFlow/MINT values remain separate published context, not locally qualified comparators; the SMC paper itself reports stronger LFADS/NDT co-bps. No AI study, candidate-improvement or current-SOTA qualification is established.
