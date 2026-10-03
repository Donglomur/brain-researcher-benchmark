"""Production scoring: one source-bound validation, no authoring QA closure."""
from score_submission import score


def test_source_bound_socialbrain():
    assert score() == {'status': 'pass', 'task_id': 'SOCIALBRAIN-001'}
