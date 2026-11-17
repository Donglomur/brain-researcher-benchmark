"""Inactive complete Trial operator; root must separately select deployment."""
import argparse,json
from programme.full_driver import run_selected
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--selection',required=True);p.add_argument('--bytes',required=True,type=int);p.add_argument('--sha256',required=True);p.add_argument('--controller-wall-ms',type=int,required=True);p.add_argument('--controller-cpu-usec',type=int,required=True);a=p.parse_args()
 run_selected(a.selection,{'bytes':a.bytes,'sha256':a.sha256},controller_caps={'wall_ms':a.controller_wall_ms,'cpu_usec':a.controller_cpu_usec})
