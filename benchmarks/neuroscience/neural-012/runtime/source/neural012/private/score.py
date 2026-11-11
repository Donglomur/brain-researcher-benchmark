"""Bounded reconstruction CLI; report is never a clinical detector qualification."""
import argparse,hashlib
from pathlib import Path
import io_contract as io
from analysis import grade,detector_outcomes
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['input','submission','output','detector-output']:p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--input-sha256',required=True);a=p.parse_args()
 io.need(a.output.absolute()!=a.detector_output.absolute() and all(not p.exists() and not p.is_symlink()for p in(a.output,a.detector_output)),'two distinct fresh outcome paths before input access')
 raw=io.read(a.input,256000000,a.input_sha256);packet=io.strict(raw);submission=io.strict(io.read(a.submission))
 reconstruction=grade(packet,hashlib.sha256(raw).hexdigest(),submission);performance=detector_outcomes(packet)
 # Distinct outcomes; neither successful reconstruction nor high F1 issues qualification.
 io.write(a.output,reconstruction);io.write(a.detector_output,performance)
