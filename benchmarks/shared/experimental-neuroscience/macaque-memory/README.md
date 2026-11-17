# Macaque memory scorer prototype

**NOT READY for authentic benchmark evaluation.** This package contains a prospective finite-cohort scorer, proposed paper/data and paper/data/code prompts, and invented software controls. It contains no authentic case roster, neural data, paper, official code, fitted reference or isolated runner.

The primary score compares equally weighted condition/session/animal log losses against a nested linear-SVM reference supplied by a trusted evaluator. Historical decoding reproduction is specified separately and is not implemented by this scorer. Read CONTRACT.md and CANDIDATE_PACKET_ADDENDUM_V2.md together.

The public scorer uses stable aliases `animal_1` and `animal_2` for the 18/17-session roster roles. A future evaluator must authenticate and privately bind the original-to-alias mapping. This export does not claim the private intake already supports that mapping. Case IDs and sessions in tests are invented.

From this directory, run `python3 -B -m unittest -v test_score`. Once an authentic protected manifest, roster and three references have been separately admitted, the evaluator CLI is `python3 -I -S -B score.py --manifest MANIFEST.json --submission PREDICTIONS.json --baselines REFERENCES.json --roster ROSTER.json`. These file names are placeholders; no authentic inputs are supplied.

Remaining work includes full MAT/roster and trial-event admission, train-only feature projection, fixed temporal splits, scientific runtime, both historical and protected references, official-code access terms and complete isolated execution. Public historical labels may have been exposed during model training. A positive finite score alone is neither population inference nor a frontier result.
