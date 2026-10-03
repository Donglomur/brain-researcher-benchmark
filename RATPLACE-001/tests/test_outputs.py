"""Only this source-bound production case is scored."""
import grader_bootstrap

def test_source_bound_ratplace():
    assert grader_bootstrap.validate()['status']=='verified'
