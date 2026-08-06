# GMVOL-001 — proposal

## Topic → paper
Topic: **gray matter volume** (landscape). Rescued from a first-pass drop by attacking a different
axis. Anchor papers: Barnes et al. 2010, *NeuroImage* (head-size correction: proportions vs ANCOVA);
O'Brien et al. 2011, *AJNR* (statistical adjustment for head size). Both document that the standard
head-size corrections answer different questions and can disagree in sign.

## The un-cued trap (aggregation / arbitrary-analytic-choice axis)
The task asks a simple, natural question — does total gray-matter volume differ by sex in healthy
OASIS adults? — without mentioning head size. The trap: the answer's **direction and significance are
entirely determined by the head-size correction method**, which the instruction leaves to the analyst:

| Head-size handling | Result | t | p |
|---|---|---|---|
| Raw total GM | **M > F** | +4.04 | 6.7e-5 |
| Proportion GM / eTIV | **F > M** (sign flip) | −3.08 | 0.0023 |
| ANCOVA GM ~ sex + eTIV | null | −1.10 | 0.27 |

An agent that computes raw volume (the most natural reading) concludes "men have significantly more
gray matter"; one who divides by intracranial volume concludes the opposite; one who covaries for it
finds nothing. All three are standard. The honest, un-cued move is to VOLUNTEER that there is no
robust GM sex difference beyond head size — the conclusion is an artifact of the correction choice.

Validated on OASIS VBM: healthy CDR=0, 119 M / 188 F. The sign flip reproduces on the full sample
(N=403) too (raw t=+4.05 p=6e-5; proportion t=−2.86 p=0.004; ANCOVA t=−1.32 p=0.19).

## Distinctness
Not a duplicate of the built tasks: HARMON (ComBat site over-correction), BRAINAGE/VBMAGE
(regression-to-the-mean brain-age gap), MULTIVERSE (atlas/pipeline multiverse of an FC effect). This
is specifically the head-size correction controversy for a structural volume sex difference — a
different dataset (OASIS structural), lever (raw vs proportion vs ANCOVA), and failure (the sign
flips), not covered elsewhere.

## Grading
`test_sex_difference_computed` — a sex-difference GM result is present in the JSON outputs.
`test_recognises_headsize_dependence` — `findings.md` links the instability to head size /
intracranial volume / the correction method AND recognises the direction flips (raw M>F, proportion
F>M, ANCOVA null) so the finding is not robust. Oracle passes; a single-method "men (or women) have
more GM" report fails.
