# Recover the ablation notebook's actual score provenance

This package extracts the visible Allen ablation route from the author's raw notebook and checks its calls against the loader, trainer and loss definitions at the same pinned revision. It reads source text and saved notebook output only. It does not import author modules, open the notebook's cache/checkpoint/result paths, execute cells, or construct numerical neural data.

The useful output is the concrete provenance of the saved score: packed cache dimensions, the loader being packed, re-split sizes, session identity handling, the training stage whose return is saved, unsupported call keywords, and the trainer's actual loader/return/penalty expressions. These facts distinguish the released notebook from the complete ten-session Table S1 objective. They cannot determine historical cache contents or the unpublished conversion to the reported total NLL.

With the four exact pinned source files in an external source directory, run:

```sh
python3 -I -B audit.py --source-root /operator/source --output /operator/new-audit.json
```

`source-pins.json` binds the exact bytes retrieved from commit-specific public jsDelivr URLs. The notebook path beneath that source directory must be `Reproduce_figures/SupTable_Ablation_experiments.ipynb`. All 17 code cells were independently compared with the previously cached documentary derivative and have identical parsed syntax; all three Python files also match their earlier byte hashes. The raw-host TLS failures and rate-limited official API attempt are retained separately. This retrieval does not establish publication-era execution or independently verify Git object identities. The output must not already exist. Run all commands under the project's current resource/test controls. No dependencies beyond Python 3.10+ standard library are needed.

The generated tests use invented source strings and arithmetic oracles. In particular, a seven-trial fixture distinguishes cumulative split boundaries (4/1/2) from independently floored ratios (4/0/3), and the saved-stage check distinguishes a stale second-stage return from the final training call. Source expressions containing calls or unbounded arithmetic are not evaluated.

Saved table entries are returned as printed strings with an explicit historical-output role. They are neither freshly evaluated scores nor reconstructed original arrays.

See [source recovery findings](../../docs/ablation-source-recovery-v1.md) for the recovered facts, exact primary-source locations and remaining scientific limits. The original evaluator and current task/improvement contracts remain unchanged.

Reproduction and exceeding the original result are separate first-class outcomes. This source inspection awards neither score and does not change either paired access condition: paper+data and paper+data+author-code.
