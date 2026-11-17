"""Optional generated MATLAB I/O controls; requires existing NumPy and SciPy."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import contract as c
import native
import numpy as np
from scipy.io import savemat


def specimen():
    rows=[]
    for group in (0,1):
        for i,value in enumerate((1000., float('nan')),1):
            rows.append(dict(mouse='generated',session='generated',trial_number=group*10+i,
                             success=1,optoProblem=0,wrongGrabFirst=0,optoTrial=group,
                             grabTimeC=None if np.isnan(value) else value,liftTimeC=0.))
    return c.reconstruct(rows)


def matlab(value):
    value=copy.deepcopy(value)
    for row in value['trials']:
        row['trial_number']=float(row['trial_number']);row['selected']=float(row['selected'])
        if row['contact_seconds'] is None:row['contact_seconds']=float('nan')
    value['trials']=np.array(value['trials'],dtype=object)
    return value


class NativeTests(unittest.TestCase):
    def test_matlab_struct_roundtrip(self):
        expected=specimen()
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'submission.mat';savemat(path,{'submission':matlab(expected)})
            actual=native.read_submission(path)
            self.assertEqual(c.compare(expected,actual)['contact_rmse_seconds'],0)
            self.assertEqual(c.compare(expected,actual)['histogram_probability_rmse'],0)

    def test_extra_matlab_variable_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'submission.mat';savemat(path,{'submission':matlab(specimen()),'extra':1})
            with self.assertRaises(c.ContractError):native.read_submission(path)

    def test_selected_nan_rejected(self):
        expected=specimen();candidate=matlab(expected);candidate['trials'][0]['contact_seconds']=float('nan')
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'submission.mat';savemat(path,{'submission':candidate})
            with self.assertRaises(c.ContractError):c.compare(expected,native.read_submission(path))

    def test_generated_input_cannot_claim_authentic_mat(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'optoData.mat';savemat(path,{'optoData':{'animalID':'generated'}})
            with self.assertRaises(c.ContractError):native.extract(path)


if __name__=='__main__':unittest.main()
