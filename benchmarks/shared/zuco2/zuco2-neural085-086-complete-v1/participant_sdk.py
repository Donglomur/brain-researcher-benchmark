"""File-based participant helpers; no hidden target/reference access."""
import json,hashlib
from pathlib import Path

def load_request(path):return json.loads(Path(path).read_text())
def write(path,obj):
    b=(json.dumps(obj,sort_keys=True,allow_nan=False)+"\n").encode()
    with Path(path).open("xb") as f:f.write(b)
    return {"path":Path(path).name,"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest()}
def fit_result(output,state_files,analysis_trace=()):return write(Path(output)/"result.json",{"status":"fit_complete","state_files":list(state_files),"analysis_trace":list(analysis_trace)})
def infer_result(output,request,probabilities,analysis_trace=()):return write(Path(output)/"result.json",{"identity":request["identity"],"state_sha256":request["state_sha256"],"probabilities":probabilities,"analysis_trace":list(analysis_trace)})
