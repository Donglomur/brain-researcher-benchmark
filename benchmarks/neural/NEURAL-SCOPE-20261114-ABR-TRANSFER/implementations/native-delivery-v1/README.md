# ABR native delivery and manual sessions

This package prepares complete native ABR observations and provides a persistent operator CLI for the existing release-annotation agreement task. It does not add a benchmark, train a model or establish clinical accuracy.

The frozen task contains 936 cases from 104 animals: 16,226 traces with 1,953 samples each. All recorded traces and samples are retained. Both the direct and programme arms receive the same full numeric observations and complete case images; each arm has 936 first-final slots.

## Files and commands

- `prepare_delivery.py`: prepare the complete numeric store, then render complete case views on demand.
- `manual_session.py`: initialize the two-arm session, expose a case, capture each first final, retire its view, seal all 1,872 finals, and perform separately selected label-last arithmetic.
- `abr_release.py`, `raster.py`, `COMMON_DOCUMENTATION.txt`: the complete source/document closure used by those two CLIs.
- `SOURCE.json`: exact source identities.
- `validation.json`: bounded evidence and its limits.
- `OPERATOR_GUIDE.md`: concrete commands, custody and storage requirements.

The runtime uses the Python standard library; the manual CLI requires a POSIX system with `fcntl`. The retained runs used Python 3.11.6. No dependency installation or repository-wide import is required. Use the explicit dependency paths shown in the guide, rather than the legacy repository helper in `abr_release.py`.

## Required evaluator inputs

The package contains code and public instructions only. An intact admitted observation store is sufficient for complete case views and manual initialization through the 1,872-final seal. That store contains its completion manifest, public index and roster, common instructions, and all 936 numeric case packets. It does not need the private scratch, target annotations, or opaque-ID key for those operations. See `DISTRIBUTION.md` for the exact observation-only release recipe; no archive is claimed to be published yet.

Rebuilding the store from native files, or separately selected target scoring, requires the exact evaluator-controlled native bundle. Its original preparation uses an opaque-ID HMAC key; a different key changes case identities and the completion hash. An arbitrary newly generated bundle is not interchangeable with this frozen task. Private annotation/key distribution is excluded from the observation-only release. Supply operator-owned output/session locations and a separately frozen programme; the source does not invent credentials or waive the required input hashes.

## Scientific scope and custody

Axes are native sample index and native amplitude. Calibration into physical time or voltage is not established. The numeric annotation code 100 is retained exactly, without assuming censoring or a physiological interpretation. The endpoint is agreement with authentic release annotations; expert equivalence and clinical validity are not established.

Candidate-visible material is the current complete case view and common instructions, not the evaluator bundle, private scratch, target annotations, session internals or another case's answers. The CLI records operator attestations; it is not an OS sandbox, model transport or automated proof of candidate isolation. An actual participant or programme study needs its own resource and custody plan.

Each response attempt is consumed before bounded ingress. A short or invalid response cannot be repaired by deleting the journal or replacing the first final. All 1,872 slots and the complete seal precede separately selected annotation access. Restart preserves the one-shot scoring marker. Follow the guide for the actual guarantees and operator responsibilities.

## Evidence

The exact preparer completed the 936-case authentic store and one complete maximum-size case view. Images for the remaining cases are deterministic on-demand operations; the capacity view is not an all-case visual review or a neuroscience performance result.

Manual persistence evidence combines six passes from the preserved initial campaign with four passing corrected controls. The initial failed campaign remains part of the record. The corrected capture path uses an unbuffered read and rejects an incomplete expected prefix. The generated controls exercised all 1,872 final records and label-last restart behavior; they did not open authentic target annotations or run a participant/model study.

See `validation.json` for exact evidence identities and any separate packaging-entry result. None of these results promotes the original calibrated/expert task or scientific qualification flags.

## Recheck only package entry points

Run the five relocated-entry checks with a fresh generated output directory:

```sh
"$ABR_PYTHON" -I -S -B "$ABR_PACKAGE/tests/test_portable_entry.py" \
  --package "$ABR_PACKAGE" --output "$ABR_CONTROL_OUTPUT"
```

These checks use generated inputs and do not prepare the authentic store or replay the full manual persistence suite. Keep the operator guide, distribution recipe and source metadata out of participant instructions; participants receive only the fixed common instructions and their current case view.
