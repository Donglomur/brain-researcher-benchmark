# Helsinki recorded-grid construction

This package constructs and scores a neonatal EEG task on the author's exported record/sample grid. It preserves 79 infants and three expert annotation streams. Each case uses the 30 stored records ending at index k, with k = 29 through T−1. The task makes no claim about reconstructed clinical clocks, TAL timing or uninterrupted physical acquisition.

The production path authenticates the complete 82-file [Zenodo v4 release](https://doi.org/10.5281/zenodo.4940267), exact source/header profiles, calibration and annotation layout. It admits only the three specifically bound EDF+C export exceptions; the generic strict parser remains available. Both exact Ref and REF suffixes are supported. The CSV parser requires the single ordered 1..79 metadata header; the following record is second zero. No infant, expert, supported second or recorded zero is discarded.

The five owner modules preserve train/query separation, grouped fitting, source/profile lineage, opaque HMAC case identities, prediction commitments, original quality flags and macro-averaged Brier scoring. The two evaluation conditions are adaptive investigation and a programme fixed before prediction. Amplitude-only and training-noise conditions are controls of the same task. Conditions, folds, files and engineering checks do not create additional benchmarks.

## What this publication establishes

This is source construction and synthetic engineering verification. The programme currently has 205 registered drafts/contracts and zero scientifically qualified benchmarks; this package adds no task or qualification. No scientific or agent-performance result is claimed.

The original complete synthetic harness contains 109 checks: 80 component checks and 29 integrated checks. It generates all 82 invented files for 79 invented infants, uses 80 primary cases, completes 30 sessions across two arms, three signal conditions and five folds, and commits 480 invented predictions. It tests the actual constructor, signal/window processing, train-only baselines, controller and scorer. Its FixtureCorpus and EngineeringSession use a distinct lineage; production interfaces reject those objects. The programme condition checks commitment behavior; it does not execute a submitted native prediction programme.

The core numerical modules and both harness bodies are unchanged from the accepted construction source. Three profile documents remove private provenance-location sections, and helsinki_profile.py changes only their three SHA256 constants. Public source identity consequently changes; earlier execution evidence is not relabeled as a result for this projection. PROJECTION_MANIFEST.json records the exact correspondence. The Linux workflow must verify these projected bytes before platform compatibility is claimed.

## Running the engineering checks

The supported bounded route is the helsinki-recorded-grid-controls job in .github/workflows/neuroscience-source-integrity.yml. It uses Ubuntu 24.04 and CPython 3.11.18, authenticates CI_SOURCE_SELECTION.json, and invokes check_synthetic.py once with the selected source directory and a fresh invented-fixture directory. CI_USAGE.md describes its complete ownership, limits, diagnostics and artifact admission.

The harness and reference modules require only Python's standard library. The CI route installs no scientific package and retrieves no neural data or model. It does not run check_existing_metadata.py or the private two-check launcher; those are deliberately outside this public projection.

## Remaining scientific work

Complete authentic waveform custody and production Corpus intake, protected real participant execution, native programme execution, competent authentic references, matched real-data controls, grouped uncertainty and end-to-end evaluation remain distinct gates. The fixed trusted CI harness is not an arbitrary-agent sandbox. A production deployment still needs protected owner storage, participant isolation and independently measured resource use.

Public profiles contain published source filenames/checksums and technical layout identities. No raw EEG, annotation values, patient-identifying header text, private communications, signed acquisition URLs or local provenance paths are included.
