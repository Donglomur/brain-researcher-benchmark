"""Original operator Namespace owns failures and admitted read prefixes."""
import argparse
from pathlib import Path
from .core import Attempt,need,identity
from .native.io import read,parse,relative
from .deployment import authenticate
class ReadBudget:
    def __init__(self,cap):
        need(type(cap)is int and cap>0,"Original aggregate host read ceiling")
        self.cap=cap;self.reserved=0;self.attempted=0;self.returned=0;self.bodies={}
    def admit(self,descriptors):
        n=sum(d["bytes"]for d in descriptors)
        need(all(type(d["bytes"])is int and d["bytes"]>=0 for d in descriptors),"Known finite read extents")
        need(self.reserved+n<=self.cap,"Aggregate reads admitted before effects")
        self.reserved+=n
    def capture(self,name,path,pin):
        need(self.attempted+pin["bytes"]<=self.reserved,"Each read consumes a prior aggregate reservation")
        self.attempted+=pin["bytes"]
        b=read(path,pin["bytes"],pin);self.bodies[name]=b;self.returned+=len(b);return b
def run(args):
    owner=Attempt("bootstrap");args.original_owner=owner;budget=ReadBudget(args.host_read_bytes);owner.originals["read_budget"]=budget
    try:
        prefix=[{"bytes":args.profile_bytes,"sha256":args.profile_sha256},{"bytes":32,"sha256":args.signature_sha256},
                {"bytes":args.key_bytes,"sha256":args.key_sha256}]
        budget.admit(prefix)
        p=budget.capture("profile",args.profile,prefix[0]);s=budget.capture("signature",args.signature,prefix[1])
        k=budget.capture("key",args.key,prefix[2])
        deployment=authenticate(p,s,k,args.key_sha256);owner.originals["deployment"]=deployment
        need(deployment.body["host_read_bytes"]==args.host_read_bytes,"CLI ceiling equals signed profile before source reads")
        source=deployment.body["controller_source"];budget.admit(source["files"])
        # Host code has already started: startup/import physical costs remain a qualification gate.
        for row in source["files"]:
            budget.capture("source:"+row["path"],Path(source["root"])/relative(row["path"]),row)
        from .entry import execute
        return execute(deployment,args,owner)
    except BaseException as error:owner.fail("bootstrap",error);owner.raise_first()
def main():
    p=argparse.ArgumentParser()
    for name in("profile","signature","key","profile-sha256","signature-sha256","key-sha256","root"):
        p.add_argument("--"+name,required=True)
    for name in("profile-bytes","key-bytes","host-read-bytes"):p.add_argument("--"+name,required=True,type=int)
    p.add_argument("--phase",choices=("prepare","evaluate","literal_a"),required=True)
    run(p.parse_args())
if __name__=="__main__":main()

