# TMS paired-EEG fixed-region reconstruction

**Profile:** `PAPER-paper-signal-add-021.fixed-regions-v1`  
**Parent paper task:** `PAPER-paper-signal-add-021`  
**Status:** selected-host local construction complete; public specification, scorer and portable owner source; assets are separately provisioned.

Reconstruct a complete, explicitly specified analysis of released TMS/EEG derivatives. The task compares two matched delivery conditions: paper plus data, and paper plus data plus reviewed official code. Both conditions receive the same numerical method. The scientific unit is a paired source position, with the joint cross-condition order stated as an assumption.

Read [TASK.md](TASK.md), [METHOD.json](METHOD.json) and [SUBMISSION_SCHEMA.json](SUBMISSION_SCHEMA.json). The full output covers twelve declared regions, 36 effects and 540 leave-one-position-out summaries. These are coordinates of one coherent task, not separate benchmarks. [VALIDATION.md](VALIDATION.md) describes the completed local evidence; [PROFILE.json](PROFILE.json) records the scope in machine-readable form.

This source release contains the exact accepted task, method, schema and pure scorer, plus an authored [portable owner/provisioner](portable/README.md). It contains no neural data, article, official code, private reference, candidate answers, frozen complete solution or selected runtime/grant. The scorer is an importable protected-evaluation component. The bundled owner template preserves isolated delivery and protected evaluation; a reviewed, owner-selected binding is still required before it can run. It requires externally provisioned, frozen candidate bytes and an authenticated private reference after both candidate processes have closed. Its source may be audited publicly, but it must not be mounted into candidate episodes and it reveals no reference values in reports.

[PROVISIONING.md](PROVISIONING.md) specifies the asset boundary; [portable/README.md](portable/README.md) gives the executable plan/build/select procedure. This release is not a self-contained runnable benchmark and does not establish public-data redistribution rights or arbitrary-host compatibility. No ready benchmark count is added by publishing these files.

The declared fixed-region analysis is distinct from the paper's primary FieldTrip cluster inference and the older 248-output behavioral profile. It does not replace either. Both frozen construction programs reproduced the complete reference exactly; no LLM was evaluated, and no advantage from access to official code was measured.

The associated paper is [Dake and Curtis, Nature Communications (2025)](https://www.nature.com/articles/s41467-025-57882-8). Follow its official data and code availability links for the research sources. The included MIT [LICENSE](LICENSE) covers this repository's authored software and documentation; it grants no rights in separately acquired research assets.
