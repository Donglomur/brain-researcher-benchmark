# Complete declared-support S11 comparison

`compare_panel` connects the existing `source-decoder-v2` score records across
an operator-declared full S11 panel. Both arms must provide every declared
participant/parcel/context design in identical frozen order. Each entry retains
all six sample pairs, three consistency classes, five repeats, three signed
metrics, its original variable PC count and all 129 timepoints. No parcel, PC,
time, participant or repeat is selected or averaged by this component.

The manifest requires the 30 ordinal positions used by the pinned S11 figure:
1–34 excluding 12, 14, 19 and 21. It requires both Cue (`attn`) and Choice contexts
for each declared participant, and unique participant/parcel/context entries.
This validates a declared roster. It **does not authenticate** the mapping from
those ordinals to real participant IDs or establish that the supplied parcel/PC
list includes every original source entry. Those scientific source gates remain
open; there is deliberately no trusted `source_verified=true` input switch.

Each arm supplies an iterable of `{"design": design, "scores": scores}`. Scores
must come from the existing operator scorer after prediction freezing and its
behavior/fold replay. This component checks the frozen design digest and paired
identity, exact score axes, both prediction hashes, correlation domains, complete
fold arrays, the existing arithmetic mean over folds and all undefined cells.
Missing, repeated, reordered or extra panel entries fail. Nothing is returned
until both iterables end at the exact declared boundary.

The result contains candidate and author mean-fold arrays, signed elementwise
differences and separate definedness masks. An undefined correlation in either
arm remains undefined in the difference. Insufficient-row cells remain in their
original positions. There is no nanmean rescue, absolute-correlation conversion,
new overall mean, majority vote, win count, p-value or scalar superiority result.
`paper_win` is null; reproduction and same-task superiority remain unknown.

This is a comparison-arithmetic component, **not** the missing complete scientific
admission engine. A source-qualified manifest, original numerical reference,
competent author execution, provenance for source-equivalent folds, frozen
participant-level decision criterion, uncertainty/multiplicity policy, protected
predictions and resource-qualified full execution are still required. Hashes
bind supplied records; they do not prove authentic source membership, held-out
prediction, proper assistance conditions or model behavior. Input and output
identities/arrays stay in operator evidence, never in the public repository.

The output can be large because it retains source axes. The caller must reserve
memory/storage for the complete panel before native use; no authentic panel or
full scientific workload was executed here. Generated tests use 30 invented
identities, both contexts, variable PCs, unsupported source cells and fixed
correlation arrays. They establish construction behavior only.

The dependency is the existing `source-decoder-v2/decoder.py`, SHA-256
`ac5e646fcbf6a630b11aa4be09e74e9047064749fee76043582a8f699fd24871`.
The exact author source revision is
[`8b79caa`](https://github.com/DonnerLab/2025_Park_ConfirmationBias-through-Selective-Readout-of-Information-Encoded-in-Human-Parietal-Cortex/blob/8b79caa5b95fadce826ea39bf6c69828991a4b28/Figures/FigureS11_PK_Decoding_int12_cic_tc.m).
The figure's original `gCORR/gSCR` producer and upstream reduction remain unresolved;
this component does not substitute its arithmetic for that producer.

Run the focused `test_panel.py` with existing Python and NumPy through the project
two-slot generated-test pool. Public CI enrollment is a separate integration
action; adding this directory alone does not enroll it or change task readiness.
