# Mandatory endpoint clarification

CONTRACT.json defines classification of **presegmented, state-homogeneous calcium
windows**. Protected target annotations determine segment boundaries before
windows and guards are constructed. The endpoint does not test continuous state
transition detection, online state monitoring or forecasting a change before it
occurs. This is a deliberate prospective design choice, not evidence that a
candidate receives the state labels themselves. Report this conditioning whenever
presenting a score; retain the full segmentation and exclusion provenance.

This clarification changes no case-construction code, metric or test criterion.
The parent accepted the complete V2 implementation and its identity/privacy
correction. The scorer's 20 passed invented controls remain the current result.
