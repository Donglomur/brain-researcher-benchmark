# Experimental neuroscience task components

**These four experimental components are not ready benchmarks.** They contain independently authored scorers, protocols and likelihood helpers for proposed neuroscience tasks. They do not add registered, qualified or submission-ready tasks. No model performance or scientific improvement has been measured with this export.

| Component | Proposed question | Implemented | Required before authentic evaluation |
|---|---|---|---|
| [Macaque memory](macaque-memory/README.md) | Reproduce historical decoding; improve within-session temporal-block old/new prediction | Prospective weighted scorer and failure checks | Complete trial/feature joins, protected split and references, runtime, rights, isolated runner |
| [Dendritic morphology](dendrites/README.md) | Reproduce FL/PL feature curves; predict lobe in held biological groups | Prospective group-weighted scorer and complete-census checks | Authentic donor/animal mapping, complete features, data terms, references and runner |
| [Calcium state](calcium-state/README.md) | Compare matched workflows on presegmented held-animal state classification | Metadata windows, opaque-ID projection, descriptive scorer | Complete signal/animal/label/context admission, references, uncertainty and runner |
| [NeuralFlow likelihood](neuralflow-likelihood/README.md) | Evaluate held-neuron intensity predictions and normalized spike likelihoods | Single-query masking, explicit cubic likelihood and complete projected-case scoring | Authentic complete trial admission, fitted references, historical parity, shared geometry, uncertainty and isolated runner |

Tests use invented observations and probabilities. Their success checks software behavior, not scientific validity or a candidate's skill. The paper-task scorers implement prospective improvement metrics; they do not score every requested historical reproduction output. The likelihood component does not implement a latent-model fitting engine or establish reference competence. No paper, upstream implementation, dataset, authentic target or private source history is included.

Use each family README for commands and scientific limits, plus its contract where supplied. For calcium, the mandatory scope addendum discloses target-conditioned segmentation. Public data can be pretraining-exposed even when a future runner protects labels during execution.
