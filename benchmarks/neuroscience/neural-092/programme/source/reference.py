"""Observed-data reference reconstruction; no private target or fitted model access."""
import argparse
from pathlib import Path
from io_contract import load
from packet_io import get_json,get_npz,write_json
from analysis import reconstruct,numeric_report

def main():
 p=argparse.ArgumentParser();p.add_argument('--public-index',required=True);p.add_argument('--packet-root',required=True);p.add_argument('--output',required=True);a=p.parse_args();idx=load(a.public_index);sessions={};root=Path(a.packet_root)
 if idx['task_id']!='NEURAL-092':raise ValueError('investigation task required')
 for entry in idx['sessions']:
  meta=get_json(root,entry['metadata']);observed=get_npz(root,entry['counts']['QUERY'],{'counts'})['counts'];sessions[entry['session_id']]=numeric_report(reconstruct(meta,observed))
 write_json(Path(a.output),{'schema':'neuropixels_state_submission_v1','task_id':'NEURAL-092','sessions':sessions})
if __name__=='__main__':main()
