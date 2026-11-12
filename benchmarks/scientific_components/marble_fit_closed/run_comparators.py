"""Root-only future native operator. No runnable configuration is distributed."""
import argparse,json,time
from pathlib import Path
from contract import *
from campaign import bootstrap,run
def main():
    p=argparse.ArgumentParser(allow_abbrev=False)
    p.add_argument('action',choices=('inspect','construct','grade'))
    p.add_argument('--repo',type=Path);p.add_argument('--selection',type=Path)
    p.add_argument('--selection-bytes',type=int);p.add_argument('--selection-sha256')
    p.add_argument('--source-bytes',type=int);p.add_argument('--source-sha256')
    p.add_argument('--read-bytes',type=int);p.add_argument('--write-bytes',type=int)
    a=p.parse_args()
    if a.action=='inspect':
        print(json.dumps({'task':'PAPER-paper-method-034','fits':48,'queries':48,'comparator_embeddings':96,'generic_runner':None,'scientific_qualification':False}));return
    for name in ('repo','selection','selection_bytes','selection_sha256','source_bytes','source_sha256','read_bytes','write_bytes'):
        need(getattr(a,name)is not None,'explicit protected operand '+name)
    b=Budget(a.read_bytes,a.write_bytes);selection=parse(b.read(a.selection,a.selection_bytes,{'bytes':a.selection_bytes,'sha256':a.selection_sha256}))
    lib=bootstrap(ordinary(a.repo),Path(__file__).resolve().parent,{'bytes':a.source_bytes,'sha256':a.source_sha256},b)
    # Source caller authority is not scientific/native qualification.
    if a.action=='construct':
        need(a.read_bytes>=selection['read_bytes']and a.write_bytes>=selection['write_bytes'],'whole selected capacity')
        result=run(selection,lib,b)
    else:
        from grade_comparators import assess
        need(set(selection)=={'package','candidate','access_view','bank','bank_pin','output'},'exact grade selection')
        result=assess(lib,selection['package'],selection['candidate'],selection['access_view'],selection['bank'],selection['bank_pin'],b)
        b.write(selection['output'],encode(result))
    print(json.dumps({'status':'completed_source_route','scientific_qualification':False,'logical_read_reservations':b.reads,'logical_write_reservations':b.writes}))
if __name__=='__main__':main()

