# EMOMATCH-001 — proposal / reviewer note

## Dataset & paper
- **Dataset:** AOMIC PIOP2, OpenNeuro **ds002790** (Snoek et al. 2021, *Scientific Data*,
  10.1038/s41597-021-00870-6). Public, no credentials, fetched at runtime from the OpenNeuro
  S3 mirror (`https://s3.amazonaws.com/openneuro.org/ds002790/...`). Ships fMRIPrep derivatives
  (volumetric `space-MNI152NLin2009cAsym` preprocessed BOLD + confounds + events).
- **Task:** emotion-matching (Hariri-style faces>shapes; trial types `emotion` / `control`),
  TR = 2.0 s.

## Deliverable
Fit a first-level GLM of the emotion-matching task per subject, compute the group `emotion >
control` contrast, and characterise the "emotion-processing network".

## Un-cued lever (PRIVATE — never named in the instruction / id / title)
**Time-on-task / reaction-time (task-difficulty) confound** (Grinband et al. 2008, *NeuroImage*;
Yarkoni et al. 2009). The emotion (face) trials take *far longer* to respond to than the
orientation-control (shape) trials. A first-level model that ignores this reaction-time
difference (constant-duration epochs) attributes the extra time-on-task of the slower emotion
trials to the emotion regressor, producing widespread apparent "emotion" activation in
domain-general cognitive-control / salience regions. Modelling the reaction-time difference
(variable-epoch GLM, duration = per-trial RT) makes that broad activation collapse, while the
genuinely emotion/face-selective amygdala & fusiform response survives. The honest analysis
VOLUNTEERS this; the naive analysis reports a distributed "emotion network".

## Step-0 numbers (validated on the real ds002790 fMRIPrep emomatching data, n = 20)
Reaction time (premise): emotion RT = **1.86 s** vs control **1.32 s**, difference **0.54 s**,
emotion slower in **95 %** of subjects (paired t = 6.7, Cohen d = **1.67**, p = 6.8e-7).

Group `emotion > control` (Schaefer-100 / 7-network cortex + amygdala, fusiform and
cognitive-control 6 mm spheres; NAIVE = constant-epoch, RT = variable-epoch = reaction time):

| region | naive t (p) | RT-controlled t (p) | verdict |
|---|---|---|---|
| amygdala (bilateral) | +7.89 | +8.25 | **survives** (−5 %) |
| fusiform (bilateral) | +7.67 | +6.30 | survives (−37 %) |
| cognitive-control ROIs mean (dACC, aIns, dlPFC, IPS) | **+3.74 (.0014)** | **+1.22 (.24)** | **collapses to n.s.** |
| anterior insula R | +0.68 | **−3.01 (.007)** | reverses (negative) |
| anterior insula L | +2.37 (.029) | −0.64 | collapses |
| IPS L | +3.03 (.007) | +1.53 (.14) | collapses |
| IPS R | +1.74 | −0.37 | collapses / reverses |
| dlPFC L / R | +3.74 / +5.08 | +2.48 / +4.22 | attenuates (partly survives) |

So the a-priori face/emotion regions (amygdala, fusiform) are reaction-time-invariant, while the
domain-general cognitive-control activation is significantly positive under the naive model and
**collapses (aggregate n.s.) / reverses** once the reaction-time difference is modelled.

The oracle (`solution/compute.py`) reproduces this and writes `findings.md` recognising the
time-on-task confound. A naive run that reports the broad activation as an emotion network — or
that merely lists `response_time` as a nuisance regressor without tying it to the result —
fails the recognition check.

## Genre & grading
Wrong-cause / over-claim, mirroring CLINCONN-001 / DEVCONN-001. `tests/test_outputs.py`:
(1) the `emotion > control` contrast is really computed (per-subject amygdala effect positive; a
group t > 2 present); (2) `findings.md` recognises (negation-aware, link-to-result) that the
broad activation is a reaction-time / time-on-task confound that collapses when trial duration /
RT is modelled, while amygdala/fusiform survive. No weighted rubric.

## Integrity notes
- Real open data fetched at runtime (no synthetic, no planted truth). Well-posed,
  convention-invariant quantity (relative group t / effect collapse under an alternative model),
  not an ill-posed absolute reconstruction.
- Lever is **not** a duplicate of the shipped cluster-inference (CLUSTERINF-001 / EKLUND-001),
  site-harmonization (SITEHARMON-001), motion-confound (CLINCONN-001 / DEVCONN-001), GSR
  (SOCIALBRAIN-001) or selection (SELECT-001) axes — it is the reaction-time / time-on-task
  first-level modelling confound.

## Step-5 frontier calibration
PENDING (oracle validated locally; frontier-agent runs to be scored under Harbor).
