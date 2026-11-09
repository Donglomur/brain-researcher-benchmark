"""Exact sandbox reference entry; called only after separate native admission."""
import importlib.metadata,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).absolute().parent))
from program.common import need,decode,canonical
from program.references import run
EXPECTED={"numpy":"2.2.6","scipy":"1.15.3","scikit-learn":"1.6.1","joblib":"1.4.2","threadpoolctl":"3.6.0"}
def main():
    need(len(sys.argv)==3 and sys.argv[1]=="--reference" and sys.argv[2] in ("R0","R1","R2"),"Selected reference")
    need(sys.version_info[:2]==(3,11),"Qualified Python3.11")
    for name,version in EXPECTED.items():need(importlib.metadata.version(name)==version,"Exact native dependency "+name)
    body=Path("/input/case.json").read_bytes();need(len(body)<=64000000,"Complete input cap")
    prediction,report=run(decode(body),sys.argv[2],observe=lambda event:print(json.dumps(event,sort_keys=True),flush=True))
    for name,value in [("prediction.json",prediction),("reference.json",report)]:
        with (Path("/output")/name).open("xb") as f:f.write(canonical(value))
if __name__=="__main__":main()

