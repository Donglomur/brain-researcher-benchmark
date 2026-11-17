"""Offline source gates; invented paper leaf only, no upstream execution."""
from pathlib import Path
import sys,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'private'))
import stage
class SourceClosure(unittest.TestCase):
    def test_A_never_opens_official_roots(self):
        with patch.object(stage,'approved_paper',return_value=b'invented paper'):
            with patch.object(stage,'source_root',side_effect=AssertionError('A touched official root')):
                self.assertEqual(stage.approved_sources('paper_and_data',official_source_root='/nonexistent'),[('paper.html',b'invented paper')])
    def test_B_refuses_absent_explicit_source(self):
        with patch.object(stage,'approved_paper',return_value=b'invented paper'):
            with self.assertRaises((ValueError,TypeError,FileNotFoundError)):
                stage.approved_sources('paper_data_official_code')
    def test_paper_is_external_required(self):
        with self.assertRaisesRegex(ValueError,'Explicit operator paper'):
            stage.approved_sources('paper_and_data')
    def test_unknown_arm_refuses_before_paper(self):
        with patch.object(stage,'approved_paper',side_effect=AssertionError('unexpected')):
            with self.assertRaises(ValueError):stage.approved_sources('not-an-arm')
if __name__=='__main__':unittest.main()
