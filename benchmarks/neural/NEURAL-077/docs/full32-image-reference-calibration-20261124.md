# Full32 fixed-image reference calibration — 24 November 2026

The attempted complete calibration produced **no performance result**. The second attempt fitted the four-demo reference and completed 61 query captures, then stopped because the next image contained no visible post-marker support. A label-free diagnostic traced that refusal to clipping in the fixed display. It did not establish an AI reasoning or neural-understanding failure.

This is the predefined full32 complement: 32 people and 200 queries per person, totaling 6,400. It is separate from the original 400-case, two-person development condition and is not the entire 40-person source collection. The selected reference uses four fixed demonstrations and the initial Cz/Pz image at 20 native units/division, the full [-250,750) ms window, and no display filter. The [reference source](../implementations/four-demo-image-reference-v1/reference.py) remained unchanged between attempts.

| Attempt | Outcome | Complete query captures | Queries scored |
|---|---|---:|---:|
| 1 | Runtime admission failed before fitting or query processing: the selected executable did not satisfy the existing single-link rule. | 0 | 0 |
| 2 | An existing compatible interpreter passed admission. Four-demo fitting succeeded; the unchanged reference later refused an unsupported image. | 61 | 0 |

Attempt 2 made 62 query attempts: 61 complete captures, one refusal, and 6,338 unattempted cases. It stopped after 15.806 seconds, including 0.439 seconds for fitting and 15.267 seconds for the run stage. Private scoring never began. All 62 owned query children were reaped and their captured streams closed. Full-arm admission and containment of escaped descendants are not claimed. Neither attempt was silently retried or converted into a partial benchmark result.

The subsequent diagnostic inspected only the refused image, its public rendering metadata and the four fixed demo images. The unchanged extractor ran once on each image, without fitting, predictions, existing prediction inspection or target access. Both query baselines were visible, but both post-marker panels contained 0 of 840 possible visible trace columns. All 30 query features were explicitly missing; all 120 demo features were defined. The exact renderer-blue mask agreed with the extractor, and decoded query scanlines matched the original rendering identity.

At this display gain the renderer clips segments beyond ±60 native stored units and marks clipping in the image. The inspected image loses all post-marker trace information used by this reference. Empty image regions do not establish absent neural activity, reveal the query's class, or recover its underlying amplitude. Physical amplitude calibration remains unresolved. The diagnostic covers one exposed failure and four demonstrations, not the remaining population.

The five-image diagnostic took 0.812 seconds and 44.1 MB maximum RSS. Native peak RSS was not measured. Preparation, both failed attempts and the diagnostic were conservatively charged 10 MiB of artifacts and 704 MiB of named reads; these are accounting allowances, not measured kernel I/O or peak storage. There were no downloads or paid model calls. Exact aggregate counts, timing and cost semantics are in the [structured report](full32-image-reference-calibration-20261124.json).

Two separately versioned source followups are being developed: an explicit uncertainty response for valid fixed images with no shared support, and an observation condition using the existing permitted gain controls. A larger permitted display range can still clip, and unclipped plots can lose detail through quantization. These followups do not change either historical failure, authorize a new authentic run, or establish accuracy. They must preserve all original cases, declare their information budgets and undergo complete qualification before a competence claim.

This remains exposed-development evidence: prior full32 and pilot evidence and the failed observation have already been inspected. No accuracy, independent generalization, native-versus-tool comparison, paper improvement, or newly completed scientific benchmark is reported.
