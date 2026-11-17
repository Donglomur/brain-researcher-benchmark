# Cerebellar contact-count contract component

This inactive source component belongs at `benchmarks/scientific_contracts/cerebellar/`. It supplies condition-isolated candidate views and paired evaluation for the existing NEURAL-030 assignment. It adds no benchmark, trained result, runnable task, scientific qualification or submission-readiness claim. The full scientific specification is in CANDIDATE_CONTRACT.md.

The candidate modules are original benchmark source. They depend on the exact small original `score.py` bundled here, copied unchanged from the existing public `benchmarks/neuroscience/neural-030/score.py`: 8,568 bytes, SHA-256 `4b4186e14063235f99f0eab8a09bb4edbc6d3cb1f0c9bd9184e194e89cbb7e0a`. This is an explicit dependency copy, not a new scoring method. The publication transaction must verify that body against public predecessor `c8195ee48a3054090689b3c42b1a4e5027d1d8ec` and the final publication parent. The existing exact `numpy==2.4.6` requirement and NOTICE.md are retained. No complete benchmark tree is duplicated.

The source question concerns expected measured contact-onset counts after a complete planned delay, using retrospective within-session inputs. The original paper is [Garcia-Garcia et al., Neuron 2024](https://doi.org/10.1016/j.neuron.2024.05.019); the author [source repository](https://github.com/wagnerlabnih/garcia-garcia-neuron-2024/tree/124c83e1af83e9680e05f9827448579d02345fa3) remains an external scientific reference. Its MATLAB code is not bundled and no redistribution grant is inferred. Dryad's declared CC0-1.0 data terms are separate from software rights and do not establish source access, identity, or possession. No authentic neural, contact, behavioral, identity or model-weight data is distributed here. All existing scientific/native/access/runtime holds remain.

With the declared NumPy dependency available, the minimal portable engineering command from repository root is:

```sh
python3.11 -I -B benchmarks/scientific_contracts/cerebellar/smoke_contract.py
```

It checks local imports, the exact copied scorer identity, one strict response and one tiny invented arithmetic example. It does not fit a model, load a native dataset, run the full scientific protocol or prove a candidate is isolated. The full source contract was independently reviewed; this packaging smoke adds only evidence that this separate directory resolves its explicit dependencies.
