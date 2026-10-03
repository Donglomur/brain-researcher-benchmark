"""Production draft: one complete source/certificate decision; no QA imports."""
from grader_bootstrap import grade


def test_source_bound_gradient():
    assert grade()['status'] == 'accepted'
