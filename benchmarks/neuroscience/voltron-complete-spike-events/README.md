# Voltron complete spike-event scoring

This standalone scientific source component belongs to the existing draft `NEURAL-DISC-20261114-VOLTRON-SPIKES`. It adds no benchmark ID and requires only the Python standard library. It contains the event scorer, complete input/output contract, and invented tests. It contains no optical or electrical recordings, private answers, animal identities or model weights.

## Authentic-data applicability: not yet qualified

The fixed seven-animal and exact 400/1000 Hz interface is a proposed mathematical contract, not an authenticated description of the deposited recordings. Do not use successful source tests as evidence that this interface fits the real collection.

The complete metadata census now records six declared subjects, twelve cells and 34 movies. The paper's seven experimental mice remain a distinct reported scope. This older scorer requires seven groups and must not be applied to the six-subject deposit without an explicit successor contract. See [the complete data-scope update](../../../docs/neuroscience-benchmarks/VOLTRON_DATA_SCOPE.md).

The version-pinned [author notebook](https://doi.org/10.25378/janelia.14141609.v1) defines recorded frame timestamps relative to electrophysiology at exposure midpoints. Its retained example reports `movie_frame_rate=401.60642570281124` and electrophysiology `sample_rate=10000`. The complete movie metadata also reports native rates near 401.606 and 996.016 Hz. These metadata findings show why nominal rates and paper-level acquisition rates cannot substitute for the actual time vectors; the signal arrays themselves remain unvalidated. Do not reconstruct timing with `arange/rate`, silently round the observed rate, or resample onto an assumed common grid. A future scientific interface must specify timestamp precision, conversion error and treatment of events near the five-millisecond boundary before claiming exact physical-time matching.

The notebook uses an interactively drawn ROI and reads only the first thirteen TIFF chunks in its example. It is a usage demonstration, not the complete deterministic extractor required by this benchmark. Freeze optical-only ROI/background/motion choices without held electrophysiology, retain every movie and extraction failure, and qualify the complete optical/electrical support before scoring.

All twelve version-one cell deposits advertise CC BY 4.0 and a total of **170,740,637,908 archive bytes**. This is a metadata sum, not downloaded or authenticated signal data. Complete directory and JSON inspection is now finished: 2,271 entries and all 263 selected metadata members. Signal decoding and the deposited processing/clock relationship remain unresolved. The scorer and its 34 invented tests remain unchanged; real biological/clock qualification is still pending.

`event_score.py` implements inclusive five-millisecond, one-to-one maximum-cardinality spike matching; complete movie/core/cell coverage; optical/electrical validity intersection; grouped animal-fold validation; and paired candidate/reference metrics. `CONTRACT.md` specifies the interface, aggregation and scientific limits. `PUBLIC_SOURCE_PINS.json` pins these source files. All matched-role predictions are admitted before the trusted evaluator's single private-reference callback.

Run the invented controls from this directory:

```sh
python3 -I -S -B test_events.py
```

The 34 test methods include an independent exhaustive matching oracle over 1,024 tiny event-set pairs and complete fictional twelve-cell/seven-group cases. These are source controls, not additional benchmarks or biological results.

The public API is `grade(public, predictions, private_loader)`. The loader belongs to the trusted evaluator, never the candidate. Actual signal extraction, physical clock conversion, animal mapping, strict serialized-artifact parsing, candidate isolation, baseline generation and resource admission must be supplied and qualified separately. This library does not launch programs, read datasets, authenticate biological evidence or grant permission to run an experiment.

The complete census supports six declared subjects; the paper's different seven-mouse scope remains unexplained. Complete input/rights/extraction checks and independently qualified baseline results are still required. Successful source tests do not establish full-paper reproduction, neural understanding, improvement, SOTA, submission readiness or native containment.
