# EEG waveform response interface

This component delivers source for the existing NEURAL-077 direct waveform condition: all 400 development queries, the same four demonstrations, and one fresh no-tools model context per query. It includes no recordings or evaluator labels and creates no new benchmark ID.

Read [the operator guide](portable/README.md) and [the task contract](portable/TASK.md). The unchanged [prompt](portable/prompt.txt) is the model input template. The [condition map](portable/representation_conditions.json) distinguishes this waveform condition from ordinary Python feature analysis and the separate compressed-feature model study; it is operator documentation, not added model context.

The collector requires every response before creating a submission. Its destination handling now refuses suffix-free paths and creates the exact file exclusively. The existing response parser, response schema and prompt are unchanged.

Run the six focused, standard-library-only source controls:

```sh
python -I -S -B -m unittest discover -s . -p 'test_collector_destination.py' -v
```

Those controls use invented responses and a mocked NumPy writer. They establish destination and coverage behavior, not native serialization, model-service isolation or scientific performance. A qualified NumPy runtime and the separately admitted existing evaluator are required for actual collection and scoring.

All assessed participants are exposed development material. No completed no-tools waveform model study, target-harness qualification or submission readiness is claimed.
