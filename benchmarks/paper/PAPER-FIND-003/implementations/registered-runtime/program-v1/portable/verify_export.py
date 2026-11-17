"""Verify every standalone public source member before use."""
from pathlib import Path
import sys
import time
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from common import Budget,pin
from runner import source_admission
if __name__=="__main__":
    body=(ROOT/"SOURCE_MANIFEST.json").read_bytes()
    result=source_admission(pin(body)["sha256"],Budget(time.monotonic()+30,16*1024**2,1024))
    print("Verified "+str(len(result["files"])+1)+" exact public source files")

