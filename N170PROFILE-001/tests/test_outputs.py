"""One production source-bound validation; authoring mutations are not scoring."""
import os


def test_source_bound_n170(original_reference, private_modules):
    result = private_modules['proof_of_work'].validate_bundle(
        os.environ.get('OUTPUT_DIR', '/app/output'), original_reference)
    assert result['status'] == 'accepted' and result['n_subjects'] == 37
