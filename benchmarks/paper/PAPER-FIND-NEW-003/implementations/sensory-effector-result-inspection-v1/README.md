# Sensory-to-effector source-result inspection

This component reads the author-generated `*_body_part_similarity_data.csv` table for the recorded BANC sensory-to-effector analysis. It checks all 196 ordered pairs of the 14 recorded matched body parts, preserves target-row/source-column orientation, and separates the quantities used for statistical analysis from those used for the paired heatmap display.

This is an additive, unselected construction component for `PAPER-FIND-NEW-003`. It does not adopt Fig. 2e or ED4 as the benchmark's primary panel, change the current unavailable outcome contract, execute the original graph analysis, or determine reproduction or improvement. The legacy 96-panel runtime and secondary synapse-detection work retain their existing scopes.

## Why the quantities must stay separate

The retained author script first computes influence transforms and normalization across the mapped sensory groups. It forms `reordered_matrix` from those values. For metrics containing `minmax`, it then rescales each row of the paired subset a second time to produce the displayed heatmap. The later cosine, diagonal/off-diagonal and Pearson calculations instead use `paired_matrix`, extracted from the earlier matrix before that second rescaling. Display pixels and statistical operands can therefore differ even when both came from the same successful author run.

The parser takes the statistical values from the source CSV, verifies its cosine entries against the row profiles, and derives a separately named display matrix. It never replaces the statistical matrix with the displayed one. A generated regression case demonstrates that doing so can change the cosine calculation.

## Usage

```sh
python inspect_results.py /operator/path/influence_log_minmax_body_part_similarity_data.csv --metric influence_log_minmax
```

The accepted declarations are the script's three metric branches: `influence_log`, `influence_norm_log`, and `influence_log_minmax`. The CSV does not contain the metric name: its declaration and producer must be bound externally to an independently qualified author execution. A caller-supplied metric and an input SHA-256 do not authenticate either claim.

The reader accepts the exact five source columns, validates the R boolean flags, rejects duplicate/missing/unknown pairs and nonfinite values, and retains every matched body part. Input reads are bounded to 256 KiB plus one byte. Row order may differ with seriation; output order follows the recorded source mapping. The fixed `1e-10` cosine tolerance is a serialization/arithmetic consistency tolerance, not a biological effect threshold or paper reproduction tolerance. No p-value or superiority score is calculated.

The original script intersects available body parts and replaces matrix nonfinite values with zero before writing this table. The inspector cannot recover an upstream missingness mask or detect a missing original neuron from a finite CSV. Its complete 14-part requirement follows the retained mapping and script's 14-versus-182 companion description; it does not prove that the deposited graph produces that support.

## Qualification still required

The retained source revision is `2e78ce38e946ab80e120a42f504a019b3a567fef`. It has not been shown here to be identical to the Zenodo `v2.0.5` deposited archive. Original graph/metadata identities, neuron eligibility, influence-constructor behavior, full upstream mappings, and source-native execution remain separate requirements. The current task's exact primary panel and same-result improvement criterion remain unselected. Stronger diagonal contrasts, higher correlations or smaller p-values would not by themselves establish better biological explanation. All entries come from one fly; the 196 dependent graph cells are not 196 independent animals.

`test_inspect_results.py` uses generated numerical tables only. Its controls cover the full support, orientation, source/display distinction, zero-vector branch, column and boolean grammar, missing/duplicate pairs, nonfinite values and inconsistent cosine entries. These checks establish component behavior, not native R parity or authentic BANC results. The component still needs explicit enrollment in the repository's reviewed component test inventory before it is claimed to be covered by CI.

Numeric parsing accepts ASCII decimal/scientific tokens and rejects nonzero tokens that underflow to zero. Signed literal zero remains valid. The scaled cosine calculation avoids intermediate overflow, so it is an internal consistency check rather than a bitwise reproduction of native R arithmetic for extreme doubles.
