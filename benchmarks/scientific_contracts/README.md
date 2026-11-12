# Scientific contract companions

These four source components make the scientific claims of existing benchmark assignments more explicit. They supply descriptive comparisons, reproduction and improvement checks, or links between report claims and evidence. They are additional components of existing tasks; they add no benchmark count, completed experiment, scientific qualification, or submission-readiness claim.

| Component | Scientific purpose | Important boundary |
|---|---|---|
| [ERP neural contribution](neural005/README.md) | Equal-person history-minus-ERP loss, all signed contrasts, and participant sensitivity. | Absolute ERP ranking stays unchanged. Exact full-history matching has no movable cases; no null test or p-value is claimed. |
| [Neuroformer](neuroformer/README.md) | Separate released-code replay, version-specific paper reproduction, and protected improvement. | Full scope and both published Table 1 versions remain; matching declarations do not prove isolation or provenance. |
| [Cerebellar contact decoding](cerebellar/README.md) | Isolate candidate input views and compare matched context and joint predictions. | Retrospective within-session decoding; beating a fixed behavioral reference alone does not establish neural contribution. |
| [Language report claims](language/README.md) | Check numerical claims against complete report support and distinguish external scientific judgments. | Numerical agreement is separate from causal, population, neural-understanding, or meaningful-improvement claims. |

Zero, negative, unavailable, and discrepant outcomes remain valid where specified. The components require trusted upstream inputs and operator controls described in their contracts. They do not run trained models or authenticate empirical data merely from supplied metadata. Original task packages and their admission states are unchanged.

The CI checks use invented engineering inputs only. ERP, Neuroformer, and language use the Python standard library. The cerebellar smoke also uses the exact `numpy==2.4.6` dependency and the small original scorer bundled with its notices. No authentic neural recordings, targets, model weights, paper PDFs, or private review evidence are included.

From a fresh checkout with Python 3.11:

```sh
python -I -S -B benchmarks/scientific_contracts/neural005/test_scientific_contribution.py -v
python -I -S -B -m unittest discover -s benchmarks/scientific_contracts/neuroformer -p test_compare_v2.py
python -B benchmarks/scientific_contracts/language/test_claim_evidence.py
python -I -m pip install --only-binary=:all: --no-deps -r benchmarks/scientific_contracts/cerebellar/requirements.txt
python -I -B benchmarks/scientific_contracts/cerebellar/smoke_contract.py
```

The language check creates `language/CONTROL_RESULT_V3.json` exclusively and requires a fresh component copy without that generated file. These commands test implementation and portable imports; they do not execute or qualify a scientific benchmark.
