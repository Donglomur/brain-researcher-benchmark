# Neuroformer benchmark source — unfinished

This package contains 74 reviewed source roles for one neuroscience paper
assignment. Its scope remains 46 case slots, 85 condition cells and seven wider
paper families. None is scientifically qualified or submission-ready. Source
files, conditions and engineering controls are not additional benchmarks.

The new protected generation component starts each current sequence from SOS,
calls the model without targets and builds later neural history from generated
ID/time pairs. It preserves complete ordered support, explicit episode resets,
empty windows and EOS or capacity termination. Output window identities use the
released float32 representation required by the existing evaluator.

This component is an explicit source amendment. The original generation-history
defect remains intact for historical reproduction. Empty initial history and the
other protected protocol choices are documented separately; they do not recover
an original ablation configuration or demonstrate improved model performance.
Native numerical parity, authentic execution, physical isolation, original run
and metric mapping, comparator recipes and wider paper coverage remain open.

Start with [the task](source/public/TASK.md),
[run composition](source/operator/RUN_COMPOSITION.md) and
[protected generation](source/operator/PROTECTED_ROLLOUT.md).
[PUBLIC_SCOPE.json](PUBLIC_SCOPE.json) records the current scope and holds.
Historical 10 ms, protected source-amended 10 ms and prospective 5 ms conditions
remain distinct. The paper + data versus paper + data + official code comparison
is retained.

All 26 original official scientific bodies are preserved. Of those, 24 files are
byte-identical and two have comment-only license headers. Source readers verify
the distributed bytes and recover the original SHA-256 and Git blob identities
before compiling original definitions. Code-access staging carries all seven
additional attribution and license files. Source verification imports no
original model module:

```sh
python3 source/operator/author_source.py --check-source
```

The release contains source, contracts and notices. The paper is an external
operator requirement; observations, answers, trained weights and private build
history are not bundled. The operator directory contains implementation source
and templates, with no private observations or targets. Upstream machine paths
and legacy launch defects remain original-source evidence, not portable setup
instructions.

[Third-party notices](source/public/official_code/THIRD_PARTY_NOTICES.md) and
[rights provenance](UPSTREAM_RIGHTS.json) retain the previous source-specific
terms. The wrapper MIT license does not override paper, data, weight or
third-party code terms. Publication does not install or register a runnable task.
