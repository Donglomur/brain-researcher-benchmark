"""Bounded parser regressions only; full scientific positives live in builder/."""
import pytest
from proof_of_work import read_table

def test_duplicate_identity_is_not_an_average(tmp_path):
    path=tmp_path/'rows.csv'
    path.write_text('subject,n400_uv\n1,-4\n1,-6\n')
    with pytest.raises(AssertionError,match='duplicate'):
        read_table(path,['subject','n400_uv'],('subject',))

def test_original_subject_id_not_digit_stripped(tmp_path):
    path=tmp_path/'rows.csv'
    path.write_text('subject,n400_uv\nsubject1,-4\n')
    with pytest.raises(AssertionError):
        read_table(path,['subject','n400_uv'],('subject',))

def test_numeric_id_and_extra_column_are_harmless(tmp_path):
    path=tmp_path/'rows.csv'
    path.write_text('note,n400_uv,subject\nanything,-4.0,1e0\n')
    assert read_table(path,['subject','n400_uv'],('subject',))[(1,)]['n400_uv']==-4
