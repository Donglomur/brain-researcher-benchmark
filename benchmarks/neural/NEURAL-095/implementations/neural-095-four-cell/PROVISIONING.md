# Exact data provisioning

The input recording is DANDI dandiset `000130`, version `0.241017.1448`, asset `c90cbccc-31a5-4815-88e6-822d8c5ca68c`, archive member `sub-Haydn/sub-Haydn_desc-train_ecephys.nwb`. Its immutable identity is 14,119,912 bytes and SHA256 `6212aaee2c978d1cd53fbfb433d11f418ed27cd83017b8b2befa4a1d7add5198`. The official unsigned download endpoint is shown below; no expiring signed object URL is stored in this package.

The original-data converter has completed one full conversion on Python 3.11.6 with NumPy 2.4.6 and h5py 3.16.0. It reproduced every byte of the seven registered base files and ten logical view files while retaining all 748 TRAIN trials, all 258 query trials, all 40 held-in units and four strictly pre-Set bins. This tested-host result does not prove compatibility on every other runtime. Any changed output hash remains a failure; do not silently change the session, split, target, ordering, units or frozen hashes.

## Required evaluator references and publication status

The converter also requires three unchanged authored reference metadata files, totaling 24,344 bytes. Their exact filenames, sizes, SHA256 hashes and planned release URLs are in `REFERENCE_ASSETS.json`. They preserve the full five-reference comparison, existing production commitment and arithmetic audit; no reference fitting is repeated. These are separate evaluator-only release assets, not ordinary source files or candidate inputs.

This documentation snapshot was authored before those release assets were published. The planned release is [neural-095-four-cell-reference-v1](https://github.com/Donglomur/brain-researcher-benchmark/releases/tag/neural-095-four-cell-reference-v1). Publication and full remote-hash verification must be recorded separately before claiming that a fresh user can obtain every operand. A source merge alone does not establish asset availability. The commands below describe the complete route after that release is published and verified; the converter never downloads missing operands itself.

The reference grades are derived from historical public development labels. In particular, condition 23 contains one query trial, so its five per-condition MAEs are individual absolute errors. These are not secret-test or contamination-free assets. The release has no personal/local filesystem paths or case-ID/prediction/target arrays, but it is not answer-level-free. Keep all reference metadata, original NWB and generated query targets outside candidate mounts and deny candidate network access. Public availability does not authorize a candidate to consult evaluation labels during a run.

## Obtain and convert

Run these operator-side commands from this task directory after release verification. Use a fresh output name. Python 3.11, NumPy and h5py are required.

```sh
mkdir -p dmfc_inputs
curl --fail --location --connect-timeout 15 --max-time 120 \
  --output dmfc_inputs/train.nwb \
  https://api.dandiarchive.org/api/assets/c90cbccc-31a5-4815-88e6-822d8c5ca68c/download/
dmfc_reference_base=https://github.com/Donglomur/brain-researcher-benchmark/releases/download/neural-095-four-cell-reference-v1
for dmfc_reference_name in reference_grade.json reference_commit.json reference_audit.json; do
  curl --fail --location --connect-timeout 15 --max-time 120 \
    --output "dmfc_inputs/$dmfc_reference_name" \
    "$dmfc_reference_base/$dmfc_reference_name" || exit 1
done
python3.11 -I -B provision.py \
  --source dmfc_inputs/train.nwb --out dmfc_provisioned \
  --reference-grade dmfc_inputs/reference_grade.json \
  --reference-commit dmfc_inputs/reference_commit.json \
  --reference-audit dmfc_inputs/reference_audit.json
```

The command authenticates the complete NWB and all three reference operands before using them, then requires exact whole-file equality for all seven base and ten view artifacts. It makes no download, fit or model call. It refuses an existing output directory. Failed conversion preserves partial output for diagnosis and does not retry or repair values.

The result has `packet/` (the original conversion), `views/cue_only/` and `views/neural/` (five public files per view), and `evaluator/` (the five exact scorer operands in `artifacts.json`). Mount only a cell's relevant five view files into a candidate, never the entire output tree. After all four candidate producers have stopped and their outputs are committed and publicly validated, the trusted scorer may use `--data-dir dmfc_provisioned/evaluator`. Do not run candidate code inside the evaluator environment.

`DATA_NOTICE.md` supplies the DANDI CC BY 4.0 attribution and derivative-change notice. `PROVISIONING_RECEIPT.json` is written only after every output identity check succeeds. The tested complete tree had 25 files and 1,667,649 bytes. The converter limits generated output to 4 MiB excluding the retained recording. An operator must still supply a finite process deadline/resource allocation and verify completion; the public provisioner is not an OS process owner or candidate sandbox. The historical exact `contract.json` status text is retained and is not a current readiness declaration.

This package now supports exact data conversion and offline scoring for one existing finite-session task. It does not implement the protected four-cell candidate-generation protocol, establish arbitrary-candidate matchedness, demonstrate an LLM capability or add a benchmark to the count.

Publication update (2026-11-15): all three evaluator assets are published and independent downloads matched their full byte counts and SHA256 hashes. See `PUBLICATION.json` for exact remote verification. The route above is now available; the scientific and candidate-isolation limitations still apply.
