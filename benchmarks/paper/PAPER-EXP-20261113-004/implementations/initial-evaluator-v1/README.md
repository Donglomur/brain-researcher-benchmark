# Initial reward-relative evaluator

Executable owner-side chronological splitting, neural-only query projection, and paired mouse-level cosine scoring for `PAPER-EXP-20261113-004`.

This original standard-library implementation is construction source. It does not execute a native model, implement the unresolved historical coordinate transform, or reproduce complete Figures 2–3. All score outputs retain scientific and reference qualification holds. Generated tests are engineering controls only.

See the [evaluator documentation](../../docs/initial-evaluator-v1.md) for source provenance, schemas, trust boundaries, prospective policies, and unresolved gates. No dependencies need installation.

From this directory, prepare the candidate query and protected owner plan using admitted owner input and an owner-held secret file of at least 32 bytes. Create the output directories first, and keep `protected/` and the secret outside candidate access:

```sh
python3 -B evaluator.py prepare --owner-input owner-input.json --secret-file owner-secret.bin --candidate-output candidate/input.json --owner-output protected/plan.json
```

After obtaining candidate and independently supplied comparator predictions under that same plan, score them:

```sh
python3 -B evaluator.py score --owner-plan protected/plan.json --candidate candidate-predictions.json --comparator official-predictions.json --output protected/score.json --bootstrap-repeats 2000 --seed 0
```

Run the generated engineering controls from this directory:

```sh
python3 -B -m unittest discover -s tests -v
```
