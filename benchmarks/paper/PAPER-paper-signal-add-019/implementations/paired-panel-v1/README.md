# Paired original contrast-panel reports

This operator-only component pairs the existing `contrast-panel-v2` outputs for paper+data and paper+data+author-code. Both arms must supply the same outcome set, one shared fixed target payload and the same complete three-law reference operands. Each arm is evaluated through the unchanged source scorer, retaining separate behavioral/HMP populations, original global contrast folds, all participants' predictions, nine targets and both instructions.

Reference parity compares all supplied reference operands and metadata after ordering keyed prediction rows and fit-contrast declarations. It does not compare only aggregate scores: two changed participant predictions that cancel at the group mean still fail. Candidate methods may have different names and arbitrary equations. Their supplied reference bank must remain identical. The operator must freeze and authenticate that bank independently; a digest does not attest source fitting, chronology or scientific competence.

The report includes both original arm results and descriptive differences in the direction **author-code minus paper+data**. Candidate results retain all18 original RMSE cells, plus separately named full-data R² diagnostics. Reproduction retains all126 source findings:54 RMSE,54 latency R² and18 Fechner accuracy R² cells. Missing/undefined companion values remain `null` with an explicit `undefined_in` list; no common-defined subset or scalar average is substituted. Lower RMSE is favorable; higher R² is favorable. Neither direction is a significance or paper-win rule.

```sh
python3 -I -S -B benchmarks/paper/PAPER-paper-signal-add-019/implementations/paired-panel-v1/pair.py \
  /external/operator/targets.json \
  /external/operator/paper-data-predictions.json \
  /external/operator/paper-data-author-code-predictions.json \
  --output /external/operator/paired-report.json
```

The CLI records exact input-file hashes and refuses to overwrite an existing result. Inputs use the unchanged target/submission schemas documented in `contrast-panel-v2/README.md`. The API is `evaluate_pair(targets, paper_data, paper_data_author_code)`. The latter two arguments must name their corresponding access labels. All results and inputs are operator-private: reports contain answer-bearing references, target means and participant-level support. This code does not enforce participant isolation or implement assistance delivery.

The source dependencies are exact-hash checked before import. Generated tests exercise a complete26-person geometry, ragged observed support, separate B/H populations, all18/126 result cells, undefined companions, changed references with unchanged scores, order invariance, missing predictions, wrong-arm labels, independent reproduction/improvement use, CLI pins and output preservation. Run:

```sh
python3 -I -S -B -m unittest discover \
  -s benchmarks/paper/PAPER-paper-signal-add-019/implementations/paired-panel-v1/tests -v
```

The integrator must enroll this command with `pair.py`, its test, and the unchanged panel/parser dependencies. It does not activate itself through predecessor discovery. No authentic data, HMP inference, optimizer or participant trial was executed. Authentic512-Hz target/cohort lineage, original fitting parity, source qualification, protected access, matched resource budgets, strongest-comparator preselection, tolerances, joint18-cell improvement and participant uncertainty remain unresolved. Historical contracts and Table1/Results discrepancies are unchanged. The component assigns no reproduction pass, paper win, SOTA claim or readiness promotion.
