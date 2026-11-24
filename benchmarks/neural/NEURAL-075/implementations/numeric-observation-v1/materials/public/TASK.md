# Perception-to-imagery object-category decoding (NEURAL-075)

Predict the **instructed object category** from each blinded imagery fMRI row,
using perception support from the same person. This is one prospective decoding
task on the complete five-person Generic Object Decoding public development
release. It is not a new-person transfer task, an imagined-photograph truth task,
or an exact replay of the 2017 paper's pairwise identification statistic.

## Fixed scientific scope

Horikawa and Kamitani, *Generic decoding of seen and imagined objects using
hierarchical visual features*, Nature Communications 8,15037 (2017),
https://doi.org/10.1038/ncomms15037. Official code revision
`b0cecdc962e392d2d7c7eabee7eee6c95db516c4`; processed release
https://doi.org/10.6084/m9.figshare.7387130.v8. Use corrected native-space SPM5
`Subject1.h5` through `Subject5.h5`, not the alternative fMRIPrep files or the
stale pre-correction links in the Python demo README.

The designated panel is all five participants, each with all 1,200 perception
support images from150 categories (eight images/category), all500 imagery rows
(50 categories×10), and all1,750 perception-test rows (same50×35). The50 test
categories are absent from decoder support. These are genuine observed release
counts, not a sampled subset. The same person receives native-space VC voxels;
there is no assumed voxel alignment across people. This assignment fixes the
full `ROI_VC` and **all1,000 stored `cnn7` units** before any outcomes. NEURAL-076
separately investigates the full ROI/feature hierarchy on the same cohort;
neither task is another independent dataset.

The primary endpoint is equal-participant mean,50-way imagery **trial Top1
identification**, with exact ties receiving1/(number tied for maximum). The
primary is continuous; there is no scientific success threshold. Report all
five participant values, midrank and half-tie pairwise rank as well. The same
perception-test endpoint is a separate transfer diagnostic, never tuning data.
All2500 imagery rows and8750 perception-test rows remain in their original
participant. Repeats/categories are nested, not extra independent people.

## Candidate interface and three matched arms

Each isolated invocation receives `case.json` and `inputs.npz`. It writes one
`prediction.json` following `prediction.schema.json`: exact context SHA256,
case ID, candidate-category order, opaque trial IDs and one finite50-score row
per trial. Scores need not be probabilities; larger means more likely.
Allowed range is[-1,000,000,1,000,000]. Output is at most4MiB. No missing,
duplicate, extra or reordered rows/categories, NaN, infinity or Boolean scores.
The same category bank and score convention apply to every arm and phase.

* `neural`: train_x[1200,V], train_y[1200,1000], bank[50,1000], opaque support
  category groups, support run IDs, and query_x[N,V]. Query metadata includes
  **no source row, original order, run/block, stimulus ID, cue/category label or
  vividness response**. The operator privately shuffles complete query rows;
  label-based averaging before prediction freeze is forbidden.
* `no_neural`: the same train_y,bank, support group/run design and query count/IDs,
  but no train_x or query_x. This supports category/feature-geometry or declared
  language-prior controls. The supplied simple reference emits the same
  mean-support-feature versus bank similarity for every trial.
* `training_permuted`: same neural support and query, but complete eight-image
  training-category feature blocks are deranged with an operator-held key. No
  category retains its own block; no query labels enter this transformation.
  Refit all target-dependent preprocessing, voxel selection and regression.
  This removes learned support correspondence; it is not proof of a uniquely
  neural mechanism or a causal cue-free imagery signal.

Freeze a single program/analysis recipe before query access. The complete
collection is5 people×3 arms×2 phases=30 files, in `protocol.case_ids()` order.
`collection.schema.json` records file pins and declared program identity.
Identity fields are bindings, **not proof that code ran**. A trusted external
executor must enforce fresh processes, exact views, no network/other data,
producer closure and program identity. This package supplies no controller or
claim of sandbox qualification. Do not mount the entire operator preparation
tree. Held imagery/perception labels cannot be read for model choice, stopping,
features, trial selection or calibration. If tuning is added to a submitted
recipe, keep all eight images of a support category together and all recurring
image/run dependencies within training-only validation; report the policy.

The trusted grader validates all30 submissions before opening any labels.
Only afterward it also averages **score vectors** by true category and reports
a50-row secondary endpoint. This is not the original method's feature-vector
averaging before correlation. It separately names the historical strict-greater
rank fraction, whose all-tied value is1; that diagnostic is never substituted
for multiclass accuracy (all-tied=.02) or half-tie rank (all-tied=.5).

## Reference source and access conditions

The provided `reference_program.py` is a fixed prospective baseline: support-only
standardization, top1000 available VC voxels by mean squared training
feature correlation (ties original column order), shared multioutput ridge with
alpha1, and Pearson similarity across decoded units to the fixed category bank.
Zero-variance standardization scales become1; constant similarity vectors map
to0, giving explicitly tied category scores. No fit has been run during build.
This differs from the paper's per-unit sparse-regression selection/2,000
iterations, the MATLAB demo's200iterations and Python's100-unit OLS demo. It
does not claim numerical equivalence to those procedures.

Access A supplies this task/specification, the pinned source-paper citation,
fixed generic reference-tool source and the exact case data. Access B adds only
the selected original author config/prediction/identification code and MIT
license in `author_code/`. Both use identical data and task. The older author
program is for inspection/adaptation; its original dependencies and answer-
using analysis path are not a runnable candidate closure. The stager does not
supply a paper PDF/full-text file; if an operator later supplies the article,
the same authenticated material must go to both arms. Access controls supplied
materials, not prior model knowledge. Separate A/B collections; never mix them
or claim a measured code-access advantage from this build.

## Interpretation limits

The released values are trial-averaged, shifted3seconds, outlier-processed,
within-run detrended and scaled fMRI in native3mm voxels; they are not raw BOLD
volumes or physical neural firing rates. Centered/run-level preprocessing and
the category-name cue preceding imagery prevent a causal online/cue-free claim.
Imagery `stimulus_id` in these actual files stores the corresponding test-image
decimal ID; its category prefix labels the instruction, **not a verified image
the person mentally pictured**. No prediction is a ground-truth reconstruction
of private experience.

The supplied image features are the source's MatConvNet/AlexNet features;
re-extracting with an arbitrary Caffe/PyTorch checkpoint is not interchangeable.
The original metadata flags20/50 test images as ILSVRC2012 training images and
18/50 test categories as training categories. "Unseen" applies to this neural
decoder's support, not necessarily to vision/LLM pretraining. Photographs are
not bundled/requested and their rights do not follow from the code license.
Five exposed participants support a finite within-person transfer comparison,
not independent new-person generalization, clinical inference, SOTA or a full
paper reproduction. Source/build integrity does not establish difficulty,
model execution or research qualification.
