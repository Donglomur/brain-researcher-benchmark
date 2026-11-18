# MindBridge original-method invocation bindings

This offline builder connects six target7 condition declarations to checkpoint
roles and existing source command interfaces. It opens no model, data, source
module or cache and launches nothing. Its checks detect contradictory metadata;
they cannot detect mislabeled checkpoint contents if the declarations also change.

The source1/2/5 pretraining declaration must exclude target7, preserve8559 training
and300 validation examples per source, and bind the source script's
`mindbridge_subj125/last.pth` role. Each of the six conditions has a distinct model
path, matching scratch/reset case ID, original500/1500/4000 budget, target7 and the
appropriate declared source exposure. Checkpoint hashes, lengths and training
receipt hashes are required declarations, not verified file identities or evidence
that the weights were trained on the stated population.

Only the checked-in reset4000 training invocation is emitted. Its expanded argv
is kept separately from the explicit interpreter/data-view binding. The command
preserves the script's CUDA device and wandb default; it does not silently replace
logging behavior or alter source hyperparameters. `main.py` multiplies the learning
rate by actual accelerator process count, which remains a runtime obligation.

Pretrain125, every limited-data scratch recipe and reset500/1500 training argv
remain null. This does not mean those methods cannot be parameterized. The paper
supports200 epochs for new-subject adaptation and the same K examples from every
source and target; these facts are retained as prospective condition metadata.
The exact historical launch/checkpoint lineage is not recovered. The checked-in
pretraining script contains target7 (1257/eight processes), and the single-subject
script is subject1/full-data/600 epochs/two processes. Neither justifies inventing
a limited-data target7 Vanilla schedule.

The builder distinguishes two reconstruction interfaces:

- Original `recon.py` is an operator-only reference route, explicitly parameterized
  from a subject1 script to target7, the bound model, private reference data and
  the complete982-image range. It generates eight images, performs target-aware
  selection, and saves only the chosen reconstruction. It cannot supply the
  eight-candidate panel transport.
- Existing `native_predict.py` is the separate high-level-only adapter. Its argv
  binds a target-free case view, checkpoint/pin files, cache manifest and output
  allowance. It retains all eight generation-ordered draws and discards its dummy
  selection; the real operator selection must happen once after the draws freeze.
  This adapter is not asserted equivalent to an original low-level img2img run.

`admit_transport` rejects selected-only producers, fewer than eight retained draws,
selection before freeze, or a changed declared capture-helper hash. The source
contract pin must also match. These are declaration checks, not file inspection.
The original reference route also retains the dependency on
`train_logs/None/epoch120.pth`: its presence changes the source autoencoder branch.
The original code preloads73000 captions and can download model assets or log to
wandb. Access-qualified captions, offline caches, state compatibility, actual source
lookup, historical runtime/weights and sufficient output storage remain unresolved.
No command in the result is approved for execution.

`build(binding)` accepts the explicit schema exercised by the generated fixture in
`test_invocation_manifest.py`. `python invocation_manifest.py BINDING OUTPUT`
reads at most64KiB of JSON, rejects duplicate keys and writes a fresh metadata file
of at most64KiB. Paths are explicit, canonical absolute paths. The author root must
match an existing `native_bridge` lookup layout beside the operator root; if its
second-choice `public/author_code` layout is selected, the preferred
`source/official` tree must be absent or independently proven identical.

Both `paper_data` and `paper_data_author_code` are preserved as information
conditions, separate from Vanilla/MindBridge source arms. All manifests remain
operator-private. All runtime, exposure, identity and scientific qualification
flags stay false; reproduction and improvement stay unknown.

The13 new generated controls cover role and budget contradictions, contaminated
pretraining declarations, fixed-script argv expansion, selected-only transport,
reference/capture separation, access conditions and malformed metadata. They do
not replay the earlier composition or portability controls. Source scripts are
read as text for one independent argv check, never executed. Use only the existing
test pool with the explicit retained-author-source path supplied to the test.
