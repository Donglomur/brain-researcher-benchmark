"""One isolated program, immutable capture, then the unchanged scalar/envelope score.

The request, preparation and runtime receipts are trusted maintainer inputs.
They are not a candidate-supplied claim or a replacement for scientific review.
"""
import hashlib
import os
from pathlib import Path
import resource
import signal
import stat
import time
from common import Budget, decode, encode, need, pin, plain, read, write, signature
import configuration as cfg
import docker_owner as docker
from numeric import envelope, scalar

MIB=1024**2
ROOT=Path(__file__).resolve().parent
READ_LIMIT=32*MIB
WRITE_LIMIT=16*MIB

def tree_names(root, budget):
    root=plain(root)
    names=set()
    for count,path in enumerate(root.rglob("*"),1):
        budget.check()
        need(count<=256,"bounded source members including directories")
        need(not path.is_symlink(), "no source symlink")
        if path.is_dir():
            continue
        s=path.lstat()
        need(stat.S_ISREG(s.st_mode) and s.st_nlink==1, "ordinary source member")
        names.add(path.relative_to(root).as_posix())
        need(len(names)<=128, "bounded public source tree")
    return names

def source_admission(expected_sha, budget):
    path=ROOT/"SOURCE_MANIFEST.json"
    size=path.lstat().st_size
    body=read(path,{"bytes":size,"sha256":expected_sha},budget,65536)
    value=decode(body,65536)
    need(type(value) is dict and set(value)=={"schema","files"} and
         value["schema"]=="human-ripple-public-source/v1","source manifest schema")
    rows=value["files"]
    need(type(rows) is dict and len(rows)<=127 and
         tree_names(ROOT,budget)==set(rows)|{"SOURCE_MANIFEST.json"},"exact source set")
    for name,p in rows.items():
        relative=Path(name)
        need(not relative.is_absolute() and ".." not in relative.parts and
             relative.as_posix()==name, "source relative path")
        read(ROOT/relative,p,budget,1048576)
    return value

def source_member(name, manifest, budget, cap):
    # Authenticate the actual second read used after whole-source admission.
    return read(ROOT/name,manifest["files"][name],budget,cap)

def stage_public(input_root, files, output, budget):
    source=plain(input_root);output=plain(output)
    need(source.is_dir() and set(p.name for p in source.iterdir())==set(cfg.PUBLIC_NAMES),
         "exact five input entries")
    need(type(files) is dict and set(files)==set(cfg.PUBLIC_NAMES),"fixed input roles")
    output.mkdir(mode=0o755)
    for name in cfg.PUBLIC_NAMES:
        cap=1200000 if name.endswith(".csv") else 32768
        body=read(source/name,files[name],budget,cap)
        write(output/name,body,budget,mode=0o444)
    os.chmod(output,0o555)
    public=decode(read(output/"INPUT_IDENTITY.json",files["INPUT_IDENTITY.json"],budget,32768),32768)
    envelope.public_identity(public)
    need(public["input_raw_bytes"]==files[cfg.PUBLIC_NAMES[0]]["bytes"] and
         public["input_raw_sha256"]==files[cfg.PUBLIC_NAMES[0]]["sha256"],
         "public identity joins exact original raw bytes")
    return public

def grade_closed(episode, public, private_descriptor, output, budget):
    docker.require_closed_episode(episode)
    if type(episode) is docker.ClosedFailure:
        result={"task_id":cfg.TASK_ID,"status":"candidate_execution_failed",
                "reason":episode.reason,"scientific_success":None,
                "private_bundle_reads":0}
        return result,write(output/"SCORE.private.json",encode(result),budget)
    docker.require_closed(episode)
    descriptor=episode.submission
    body=cfg.load(descriptor,budget,envelope.MAX_BYTES)
    # The recorded commitment precedes the sole lazy private callback.
    commit=write(output/"OUTCOME_COMMIT.private.json",encode({
        "schema":"human-ripple-closed-outcome/v1","submission":descriptor,
        "lifecycle":episode.lifecycle,"complete_capture_and_cleanup":True}),budget)
    def load_reference():
        return decode(cfg.load(private_descriptor,budget,1048576),1048576)
    result=envelope.grade(body,public,load_reference,scalar)
    need(len(encode(result))<=envelope.MAX_REPORT_BYTES,"complete score report limit")
    score=write(output/"SCORE.private.json",encode(result),budget)
    return result,{**score,"outcome_commit":commit}

def run(request_descriptor):
    need(signal.getitimer(signal.ITIMER_REAL)==(0.0,0.0),"no inherited timer")
    started=time.monotonic()
    budget=Budget(started+75,READ_LIMIT,WRITE_LIMIT)
    output=None;owned_namespace=False;result=None;failure=None;cli_calls=[]
    old_handlers={};original_command=docker.command
    def cancelled(signum,frame):
        raise RuntimeError("selected owner cancelled")
    def hard_stop(signum,frame):
        docker.kill_registered_clients()
        os._exit(124)
    try:
        for sig in (signal.SIGTERM,signal.SIGINT):
            old_handlers[sig]=signal.signal(sig,cancelled)
        old_handlers[signal.SIGALRM]=signal.signal(signal.SIGALRM,hard_stop)
        signal.setitimer(signal.ITIMER_REAL,75)
        resource.setrlimit(resource.RLIMIT_CPU,(60,resource.getrlimit(resource.RLIMIT_CPU)[1]))
        request=decode(cfg.load(request_descriptor,budget,65536),65536)
        manifest=source_admission(request["source_manifest_sha256"],budget)
        preparation=decode(cfg.load(request["preparation"],budget,65536),65536)
        runtime=decode(cfg.load(request["runtime"],budget,65536),65536)
        cap=decode(cfg.load(request["capacity"],budget,65536),65536)
        contract_body=source_member("PUBLIC_INPUT_CONTRACT.json",manifest,budget,65536)
        contract=decode(contract_body,65536)
        cfg.admit(request,preparation,runtime,cap,contract)
        program=cfg.load(request["program"],budget,65536)
        output=plain(request["output_root"])
        output.mkdir(mode=0o700);owned_namespace=True
        write(output/"REQUEST.private.json",encode(request),budget)
        write(output/"program.py",program,budget,mode=0o444)
        public=stage_public(request["input_root"],preparation["public_files"],output/"input",budget)
        task=output/"task";task.mkdir(mode=0o755)
        bridge=source_member("task/bridge.py",manifest,budget,32768)
        write(task/"bridge.py",bridge,budget,mode=0o444);os.chmod(task,0o555)
        # Source-only runtime admission does not install or pull an image.
        executable=plain(runtime["docker"])
        need(signature(executable.lstat())==tuple(runtime["docker_physical"]) and
             stat.S_ISREG(executable.lstat().st_mode) and os.access(executable,os.X_OK),
             "current canonical Docker executable")
        docker.DOCKER=str(executable);docker.DAEMON_SOCKET=plain(runtime["daemon_socket"])
        docker.DAEMON_GUARD=runtime["daemon_guard"]
        def guarded_command(*args,**kwargs):
            need(signature(executable.lstat())==tuple(runtime["docker_physical"]),
                 "unchanged Docker executable before call")
            observed=original_command(*args,**kwargs)
            cli_calls.append(observed[0])
            need(signature(executable.lstat())==tuple(runtime["docker_physical"]),
                 "unchanged Docker executable after call")
            return observed
        docker.command=guarded_command
        docker.configure_cli(output/"docker-config",budget)
        # Freshness is rechecked after snapshotting, before any Docker command.
        cfg.capacity(cap)
        episode=docker.run_candidate(root=output/"candidate",input_dir=output/"input",
            task_dir=task,program=output/"program.py",budget=budget,
            active_deadline=min(started+60,budget.deadline-15))
        result,score=grade_closed(episode,public,preparation["private_bundle"],output,budget)
        charged=max(75,time.monotonic()-started)
        return_value={"task_id":cfg.TASK_ID,"status":"closed_and_recorded",
                      "score_status":result["status"],"score":score,
                      "scientific_success":None,"benchmark_qualification":False,
                      "new_model_calls":0,"actual_candidate_fit_count":None,
                      "known_seconds_before":request["prior_known_seconds"],
                      "charged_seconds":charged,
                      "known_seconds_after":request["prior_known_seconds"]+charged,
                      "managed_read_bytes":budget.reads,
                      "reserved_write_bytes_before_final_result":budget.reserved,
                      "daemon_resources_are_not_host_RSS":True}
        write(output/"RESULT.private.json",encode(return_value),budget)
        return return_value
    except BaseException as error:
        failure={"class":type(error).__name__,"message":str(error)[:2000]}
        raise
    finally:
        docker.command=original_command
        if docker.registered_clients():
            docker.cleanup_registered_clients(min(budget.deadline,time.monotonic()+2))
        # A timeout or custody failure never becomes a scientific zero.
        if owned_namespace and failure and time.monotonic()<budget.deadline:
            try:
                write(output/"FAILURE.private.json",encode({
                    "task_id":cfg.TASK_ID,"failure":failure,"automatic_retry":False,
                    "known_seconds_before":request.get("prior_known_seconds"),
                    "charged_seconds":max(75,time.monotonic()-started),
                    "complete_container_cleanup":False,
                    "inspect_candidate_lifecycle_and_journal":True}),budget)
            except BaseException:
                pass
        signal.setitimer(signal.ITIMER_REAL,0)
        for sig,handler in old_handlers.items():
            signal.signal(sig,handler)

