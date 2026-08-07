# APERIODIC-001 — proposal

## Topic → paper
Topic: **EEG** (spectral analysis). Anchor: Donoghue et al. 2020, *Nature Neuroscience* —
"Parameterizing neural power spectra into periodic and aperiodic components" (specparam/FOOOF), one of
the most influential recent EEG-methods papers. A distinct EEG axis found by continued searching.

## The un-cued trap (aperiodic 1/f confound of band power — empty cell)
The task asks to measure resting alpha-band (8-12 Hz) oscillation power — without mentioning the 1/f
background. The trap: band power is the sum of a periodic (oscillatory) peak AND the broadband aperiodic
(1/f) component. Parameterizing the spectrum (EEGBCI, 20 subjects):

| state | aperiodic fraction of 'alpha power' | periodic (true oscillation) |
|---|---|---|
| **eyes-open** | **131%** | ≈ 0 (no alpha peak) |
| eyes-closed | 41% | genuine alpha emerges |

So the eyes-open 'alpha power' is **entirely the 1/f background** — there is no genuine alpha oscillation
— yet naive band power reports it as alpha. The honest, un-cued move is to VOLUNTEER the aperiodic
confound and parameterize the spectrum before claiming an oscillation.

## Distinctness
A genuinely distinct EEG axis (spectral parameterization / aperiodic confound) in an empty cell: not
EEGVC (volume conduction), not EEGMC (multiple comparisons), not the fMRI axes. Third EEG task
(EEGVC/EEGLEAK/APERIODIC), each a different failure.

## Honest risk (for the difficulty gate)
The exact aperiodic fraction depends on the 1/f fit method (I used a robust log-log linear fit excluding
7-13 Hz; FOOOF would refine it), but the qualitative finding — eyes-open alpha band power is
dominated by / entirely aperiodic, no oscillatory peak — is stable across 20 subjects (frac 1.26 at
n=10, 1.31 at n=20).

## Grading
`test_alpha_computed` — an alpha-power result is present. `test_recognises_aperiodic` — findings.md names
the aperiodic / 1/f / periodic-vs-aperiodic / spectral-parameterization issue AND that band power does
not by itself reflect an oscillation. Oracle passes; a naive "substantial alpha band power = strong alpha
oscillation" report fails.
