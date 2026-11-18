#!/usr/bin/env python3
"""Portable fixed-original Movie10 input acquisition and unchanged-preparer handoff.

POSIX and an operator-selected curl 8.7.1 are required for fetch. No network is
used by plan/prepare-command. Authentic execution needs separately qualified
outer supervision; this module makes no hard OS RAM/closure guarantee.
"""
from __future__ import annotations
import argparse,hashlib,json,os,re,selectors,signal,stat,subprocess,sys,time,types
from contextlib import ExitStack
from pathlib import Path
HERE=Path(__file__).resolve().parent
MANIFEST_SHA="916cdc9b0f0f0f4ccbc8a92c7dfb7cb3ca40d906fe5f67f8e68b4205cd4cc1b2"
ENV={"PATH":"/usr/bin:/bin","LANG":"C","LC_ALL":"C","OMP_NUM_THREADS":"1",
     "OPENBLAS_NUM_THREADS":"1","MKL_NUM_THREADS":"1","VECLIB_MAXIMUM_THREADS":"1"}
STATUS=r"%{stderr}N039_STATUS\nhttp_code=%{http_code}\nexitcode=%{exitcode}\nnum_redirects=%{num_redirects}\nsize_download=%{size_download}\nurl_effective=%{url_effective}\nssl_verify_result=%{ssl_verify_result}\nN039_END\n"

def require(ok,message):
    if not ok:raise ValueError(message)
def digest(b):return hashlib.sha256(b).hexdigest()
def canonical(x):return (json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
def unique(pairs):
    d={}
    for k,v in pairs:
        require(k not in d,"Duplicate JSON field")
        d[k]=v
    return d
def ordinary(path,cap,empty=False):
    path=Path(path).absolute()
    require(not any(x.is_symlink() for x in (path,*path.parents)),"No symlink path")
    s=path.lstat()
    require(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and (empty or s.st_size>0)
      and s.st_size<=cap,"Bounded ordinary single-link file")
    return s
def read(path,cap):
    s=ordinary(path,cap)
    with Path(path).open("rb") as f:b=f.read(cap+1)
    require(len(b)==s.st_size,"Stable file extent")
    return b
def write(path,b,cap):
    require(len(b)<=cap,"Output byte limit")
    path=Path(path).absolute()
    require(not any(x.is_symlink() for x in (path,*path.parents)),"No linked output")
    with path.open("xb") as f:f.write(b);f.flush();os.fsync(f.fileno())
def load_manifest():
    b=read(HERE/"original-sources.v1.json",16384)
    require(digest(b)==MANIFEST_SHA,"Fixed original manifest changed")
    return json.loads(b,object_pairs_hook=unique)
def identity(s):return [s.st_dev,s.st_ino,s.st_size,s.st_nlink,s.st_mtime_ns,s.st_ctime_ns]
def hashes(path,row,end,prior=None):
    s=ordinary(path,row["bytes"]);before=identity(s)
    require(s.st_size==row["bytes"],"Original extent mismatch")
    if prior:require(prior["identity"]==before,"Input custody changed")
    md5=hashlib.md5(usedforsecurity=False);sha=hashlib.sha256();n=0
    with Path(path).open("rb") as f:
        require(identity(os.fstat(f.fileno()))==before,"Opened input changed")
        while True:
            require(time.monotonic()<end,"Identity-check deadline")
            b=f.read(65536)
            if not b:break
            n+=len(b);require(n<=row["bytes"],"Input grew")
            md5.update(b);sha.update(b)
    require(identity(Path(path).stat())==before and n==row["bytes"],"Input changed during hashing")
    require(md5.hexdigest()==row["md5"],"Original MD5 mismatch")
    result={"identity":before,"bytes":n,"md5":md5.hexdigest(),"sha256":sha.hexdigest()}
    if prior:require(result==prior,"Input digest changed")
    return result

def group_absent(pid):
    try:os.killpg(pid,0);return False
    except ProcessLookupError:return True
    except PermissionError:return False

def bounded_client(argv,output,log,body_cap,log_cap,end):
    """Task-specific mature-client subprocess; retain every bounded failed prefix."""
    require(os.name=="posix","POSIX acquisition profile required")
    event={"argv":argv,"stdout_received":0,"stdout_written":0,"stderr_received":0,
      "stderr_written":0,"exit_code":None,"closed":False,"write_accounting_exact":True}
    proc=None;selector=selectors.DefaultSelector()
    try:
        with ExitStack() as stack:
            out=stack.enter_context(Path(output).open("xb"))
            err=stack.enter_context(Path(log).open("xb"))
            proc=subprocess.Popen(argv,env=ENV,stdin=subprocess.DEVNULL,
              stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
            event["pid"]=proc.pid
            for name,stream in (("stdout",proc.stdout),("stderr",proc.stderr)):
                os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,name)
            try:
                while selector.get_map():
                    require(time.monotonic()<end,"Mature-client deadline")
                    for key,_ in selector.select(min(.05,max(.001,end-time.monotonic()))):
                        b=os.read(key.fileobj.fileno(),65536)
                        if not b:selector.unregister(key.fileobj);continue
                        stream=key.data;cap=body_cap if stream=="stdout" else log_cap
                        target=out if stream=="stdout" else err
                        event[stream+"_received"]+=len(b)
                        keep=b[:max(0,cap-event[stream+"_written"])]
                        try:n=target.write(keep)
                        except BaseException:
                            event["write_accounting_exact"]=False
                            raise
                        event[stream+"_written"]+=n
                        require(n==len(keep) and len(keep)==len(b),"Mature-client output limit")
                proc.wait(timeout=max(.001,min(1,end-time.monotonic())))
                event["exit_code"]=proc.returncode
            finally:
                try:
                    for target in (out,err):target.flush();os.fsync(target.fileno())
                except BaseException:
                    event["write_accounting_exact"]=False
                    raise
    except BaseException as exc:
        event["failure"]=type(exc).__name__+": "+str(exc)[:180]
    finally:
        selector.close()
        if proc is not None:
            try:
                if proc.poll() is None:
                    require(os.getpgid(proc.pid)==proc.pid,"Owned client group identity")
                    os.killpg(proc.pid,signal.SIGKILL)
                proc.wait(timeout=1)
                event["exit_code"]=proc.returncode
                event["closed"]=group_absent(proc.pid)
            except BaseException as exc:event["cleanup_failure"]=type(exc).__name__+": "+str(exc)[:120]
            proc.stdout.close();proc.stderr.close()
    event["cleanup_uncertain"]=proc is not None and not event["closed"]
    if event["cleanup_uncertain"]:
        event["no_retry"]=True
        event["external_closure_required"]="Client leader exited or cleanup could not prove group absence; never signal a potentially reused leader PID. Resolve with the qualified outer owner."
    return event

def curl_argv(curl,row):
    return [str(curl),"--disable","--fail","--silent","--show-error","--proto","=https",
      "--proto-redir","=https","--proxy","","--retry","0","--max-redirs","0",
      "--connect-timeout","10","--max-time","150","--max-filesize",str(row["bytes"]),
      "--header","Accept-Encoding: identity","--output","-","--write-out",STATUS,"--url",row["url"]]

def status_values(log,row,n):
    text=read(log,8192).decode("utf8")
    require(text.startswith("N039_STATUS\n") and text.endswith("N039_END\n")
      and text.count("N039_STATUS\n")==1 and text.count("N039_END\n")==1,"Complete unambiguous curl status")
    lines=text[len("N039_STATUS\n"):-len("N039_END\n")].splitlines()
    keys=("http_code","exitcode","num_redirects","size_download","url_effective","ssl_verify_result")
    require(len(lines)==len(keys),"Exact curl status fields")
    values={}
    for key,line in zip(keys,lines):
        k,sep,v=line.partition("=");require(sep and key==k,"Ordered curl status");values[k]=v
    require(values["http_code"]=="200" and values["exitcode"]=="0" and
      values["num_redirects"]=="0" and values["ssl_verify_result"]=="0","HTTPS response not accepted")
    require(values["url_effective"]==row["url"],"URL changed")
    require(re.fullmatch("[0-9]+",values["size_download"]) and
      int(values["size_download"])==n==row["bytes"],"Response extent mismatch")
    return values

def _fetch(manifest,data,evidence,curl,client=bounded_client,version_check=True,client_sha256=None):
    """Internal dependency seam for generated controls; CLI always fixes manifest."""
    start=time.monotonic();end=start+680
    data=Path(data).absolute();evidence=Path(evidence).absolute();curl=Path(curl).absolute()
    require(data!=evidence and data not in evidence.parents and evidence not in data.parents,
      "Evidence must be outside the exact data directory")
    for path in (data,evidence):
        require(not path.exists() and not any(x.is_symlink() for x in (path,*path.parents)),
          "Fresh ordinary output roots required")
    data.mkdir(mode=0o700);evidence.mkdir(mode=0o700)
    result={"schema":"neural039_original_input_receipt_v1","manifest_sha256":MANIFEST_SHA,
      "data_dir":str(data),"status":"failed","files":{},"requests":[],
      "not_attempted":[r["subject"] for r in manifest["files"]],"raw_written_bytes":0,
      "all_four_custody_verified":False,"HDF5_decoded":False,
      "curl_path":str(curl),"curl_sha256":client_sha256}
    def check_client():
        if client_sha256 is not None:
            require(digest(read(curl,33554432))==client_sha256,"Mature client identity changed")
    try:
        if version_check:
            check_client()
            result["version_check"]={"started":True,"closed":False}
            event=client([str(curl),"--disable","--version"],evidence/"curl-version.txt",
              evidence/"curl-version.log",4096,1024,min(end,time.monotonic()+2))
            result["version_check"]=event
            require(event["closed"] and event["exit_code"]==0 and "failure" not in event,
              "Curl version probe failed")
            require(read(evidence/"curl-version.txt",4096).startswith(b"curl 8.7.1 "),"Reviewed curl 8.7.1 required")
        for row in manifest["files"]:
            require(time.monotonic()<end,"Whole acquisition deadline")
            check_client()
            result["not_attempted"].remove(row["subject"])
            partial=data/(row["filename"]+".partial");log=evidence/(row["subject"]+".log")
            attempt={"subject":row["subject"],"started":True,"closed":False,"write_accounting_exact":False}
            result["requests"].append(attempt)
            event=client(curl_argv(curl,row),partial,log,row["bytes"],8192,min(end,time.monotonic()+150))
            event["subject"]=row["subject"];attempt.update(event)
            result["raw_written_bytes"]+=event["stdout_written"]
            require(event["closed"] and event["exit_code"]==0 and "failure" not in event
              and event["write_accounting_exact"],"Request failed; prefix retained; later subjects not attempted")
            status_values(log,row,event["stdout_written"])
            record=hashes(partial,row,end)
            os.chmod(partial,0o400);target=data/row["filename"];partial.rename(target)
            record["identity"]=identity(ordinary(target,row["bytes"]))
            hashes(target,row,end,record);result["files"][row["subject"]]=record
        require({p.name for p in data.iterdir()}=={r["filename"] for r in manifest["files"]},"Exact four-file directory")
        for row in manifest["files"]:hashes(data/row["filename"],row,end,result["files"][row["subject"]])
        result.update(status="verified_original_inputs",all_four_custody_verified=True)
    except BaseException as exc:result["failure"]=type(exc).__name__+": "+str(exc)[:240]
    result["wall_seconds"]=time.monotonic()-start
    result["raw_accounting_exact"]=all(x.get("write_accounting_exact") is True for x in result["requests"])
    result["cleanup_uncertain"]=any(x.get("closed") is not True for x in result["requests"])
    if "version_check" in result and result["version_check"].get("closed") is not True:
        result["cleanup_uncertain"]=True
    result["raw_charge_if_uncertain"]=536870912
    result["raw_cumulative_charge"]=result["raw_written_bytes"] if result["raw_accounting_exact"] and not result["cleanup_uncertain"] else 536870912
    result["charge_semantics"]="Tracked writes are a lower bound if accounting or closure is uncertain. The full prospective reservation is then retained, not reported as measured disk use; no retry or promotion."
    result["network_accounting"]="One version probe plus at most four GET invocations; no retry/follow/HEAD. Wire bytes unmetered."
    write(evidence/"receipt.json",canonical(result),65536)
    return result

def verified_receipt(manifest,data,receipt,expected_sha):
    b=read(receipt,65536);require(digest(b)==expected_sha,"Operator-frozen receipt digest")
    r=json.loads(b,object_pairs_hook=unique);data=Path(data).absolute()
    require(r.get("schema")=="neural039_original_input_receipt_v1" and r.get("manifest_sha256")==MANIFEST_SHA
      and r.get("status")=="verified_original_inputs" and r.get("all_four_custody_verified") is True
      and r.get("data_dir")==str(data),"Complete original-input receipt required")
    require(set(r.get("files",{}))=={x["subject"] for x in manifest["files"]},"All four receipt identities")
    require(not any(x.is_symlink() for x in (data,*data.parents)) and
      {p.name for p in data.iterdir()}=={x["filename"] for x in manifest["files"]},"Exact ordinary source root")
    end=time.monotonic()+60
    for row in manifest["files"]:hashes(data/row["filename"],row,end,r["files"][row["subject"]])
    return r

def converter_sources(manifest,preparer):
    preparer=Path(preparer).absolute()
    require(preparer.name=="prepare_panel.py","Existing converter basename")
    bodies={}
    for name,pin in manifest["preparer"]["files"].items():
        b=read(preparer.parent/name,pin["bytes"])
        require(len(b)==pin["bytes"] and digest(b)==pin["sha256"],"Existing converter source changed")
        bodies[name]=b
    return bodies

def preparation_command(manifest,data,receipt,receipt_sha,preparer,panel):
    verified_receipt(manifest,data,receipt,receipt_sha)
    converter_sources(manifest,preparer)
    panel=Path(panel).absolute();data=Path(data).absolute()
    require(panel.parent!=data and data not in panel.parents,"Panel must be outside original input directory")
    require(not panel.exists() and not any(x.is_symlink() for x in (panel,*panel.parents)),"Fresh ordinary panel output")
    runner=HERE/"acquire.py"
    return [sys.executable,"-I","-B",str(runner),"prepare","--runner-sha256",digest(read(runner,65536)),
      "--data-dir",str(data),"--receipt",str(Path(receipt).absolute()),"--receipt-sha256",receipt_sha,
      "--preparer",str(Path(preparer).absolute()),"--panel",str(panel)]

def execute_preparer(manifest,args,execute=exec):
    """Execute the unchanged, freshly re-pinned converter bytes, only on explicit prepare."""
    require(digest(read(HERE/"acquire.py",65536))==args.runner_sha256,"Frozen forwarding source changed")
    preparation_command(manifest,args.data_dir,args.receipt,args.receipt_sha256,args.preparer,args.panel)
    bodies=converter_sources(manifest,args.preparer)
    directory=str(Path(args.preparer).absolute().parent)
    sys.path.insert(0,directory)
    module=types.ModuleType("evaluate");module.__file__=str(Path(directory)/"evaluate.py")
    execute(compile(bodies["evaluate.py"],module.__file__,"exec"),module.__dict__)
    sys.modules["evaluate"]=module
    sys.argv=[str(Path(args.preparer).absolute()),"--output",str(Path(args.panel).absolute()),
      "prepare","--source-root",str(Path(args.data_dir).absolute())]
    execute(compile(bodies["prepare_panel.py"],str(Path(args.preparer).absolute()),"exec"),
      {"__name__":"__main__","__file__":str(Path(args.preparer).absolute())})

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest="action",required=True)
    sub.add_parser("plan")
    f=sub.add_parser("fetch");f.add_argument("--data-dir",type=Path,required=True)
    f.add_argument("--evidence-dir",type=Path,required=True);f.add_argument("--curl",type=Path,required=True)
    f.add_argument("--curl-sha256",required=True)
    for name in ("prepare-command","prepare"):
        q=sub.add_parser(name);q.add_argument("--data-dir",type=Path,required=True)
        q.add_argument("--receipt",type=Path,required=True);q.add_argument("--receipt-sha256",required=True)
        q.add_argument("--preparer",type=Path,default=HERE.parent/"movie10-evaluator-v1/prepare_panel.py")
        q.add_argument("--panel",type=Path,required=True)
        if name=="prepare":q.add_argument("--runner-sha256",required=True)
    a=p.parse_args();manifest=load_manifest()
    if a.action=="plan":
        print(json.dumps({"manifest":manifest,"network_executed":False,"ready":False},indent=2));return 0
    if a.action=="fetch":
        curl=a.curl.absolute()
        require(digest(read(curl,33554432))==a.curl_sha256,"Operator-selected mature client digest")
        r=_fetch(manifest,a.data_dir,a.evidence_dir,curl,client_sha256=a.curl_sha256)
        print(json.dumps({"status":r["status"],"receipt":str(a.evidence_dir/"receipt.json")}))
        return 0 if r["status"]=="verified_original_inputs" else 1
    if a.action=="prepare-command":
        argv=preparation_command(manifest,a.data_dir,a.receipt,a.receipt_sha256,a.preparer,a.panel)
        print(json.dumps({"argv":argv,"preparation_executed":False,"runtime_qualified":False}));return 0
    execute_preparer(manifest,a);return 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except (ValueError,OSError) as exc:
        print(json.dumps({"status":"refused","error":str(exc)}),file=sys.stderr);raise SystemExit(1)
