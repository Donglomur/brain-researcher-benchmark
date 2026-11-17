# NEURAL-080 source recovery v2: scope and precedence

This is an inactive complete-scoped source construction checkpoint. It is not a registered runtime, an empirical result, a qualified decoder, a hardware-clock calibration or an active F/I controller. The canonical assignment is unchanged. `docs/RECOVERY_CONTRACT.md` names the current source entries and the explicit clip-time profile; the preserved legacy documents below describe the older source packet and are retained as historical method context. Their claims about metadata previously acquired do not mean that those bodies were read or copied in this recovery.

# Exact remaining audiovisual input gap

The stimulus access file directs users to the BOLD Moments stimulus route. Its current primary index lists a roughly3GB `stimulus_set.zip` and separate access terms. No video/audio archive, password file, decoded frames, model checkpoint or movie has been acquired here. No terms have been accepted by an automated downloader in this task.

The author feature script orders1,102 movie filenames lexicographically. Without the authoritative filenames/ID mapping and source byte identities, this package does not assume that arbitrary directory order is the published stimulus mapping. The1–1102 EEG/eye IDs are authenticated; their exact held media-byte join is not.

`prepare_stimuli.py` implements deterministic features **after** a future trusted decoder has supplied primitive frame-cell, frame-interval and audio arrays. It does not implement a qualified movie decoder or establish presentation latency. Required external operands are an immutable1,102-video mapping receipt, decoder-source pin and presentation-clock receipt. They must be supplied and reviewed; no placeholder hashes or guessed offsets are included. The schema alone does not prove that an operator-supplied clock, decoder or mapping is correct.

For each original movie the decoder must preserve actual video frame presentation intervals, convert its decoded RGB frames using `stimulus_core.spatial_cells`, and retain the native audio channel samples, sample rate and first sample's time relative to the presented clip. An audio track absent from a file is not a silent track. Variable frame rate, stream offsets, end padding and audio/video start offsets must be handled from actual metadata and the source presentation protocol, not from nominal3second duration. The fixed projector requires full[0,3) coverage and refuses gaps; it cannot repair missing provenance.

The feature converter checks original local media SHA256 against the externally frozen manifest and captures descriptor-bound primitive arrays. Its `source_bytes_sha256_verified` flag refers only to those local bytes. A declared clock-receipt hash remains a provenance pointer, not independent verification of hardware synchrony or original stimulus identity. The pool/preparation may only be scientifically admitted after these external facts have been established. Current data status remains partial regardless of whether a hypothetical manifest could satisfy the schema.

No model download is required for the declared low-level contrast. This avoids a missing learned checkpoint, but does not make the chosen acoustic/motion/static predictors complete controls or support a higher-level semantic claim.
