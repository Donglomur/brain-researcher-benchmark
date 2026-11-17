"""Future operator reference computation; never invoked during construction."""
import argparse
from pathlib import Path
from interface import write_json_fresh
ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 if a.output.exists()or a.output.is_symlink():raise ValueError('fresh output required')
 from data_io import load_packet
 from encoding_core import analyze
 subjects,features,manifest_sha=load_packet(ROOT)
 result={'task_id':'NEURAL-052','input_manifest_sha256':manifest_sha,'analysis':analyze(subjects,features,draws=1000,strict=True)}
 write_json_fresh(a.output,result,cap=4000000)
if __name__=='__main__':main()
