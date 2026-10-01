# Local repair validation

Estimator declaration now binds the headline to the declared participant column; missing,
unknown, conflicting labels, duplicate IDs and incomplete cohorts fail. Both legitimate
estimators remain accepted. Scientific estimates and retained reference were not changed.

Run `python -m pytest MOVIESYNC-001/authoring/test_repair.py -q`.
These are verifier fixtures against the existing reference, not a new oracle run.
Pending: freeze/check upstream image/confound/atlas hashes in a build receipt, clean offline
container build, in-container oracle reward, and full grading fixture matrix before calibration.
