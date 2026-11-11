"""Materialize only admitted predecessor artifacts after their complete collection."""
import hashlib
import os
import stat
from .strict import require, integer

def copy_verified(source,destination,row,target_path,*,clock,byte_cap):
    integer(row["bytes"],"edge bytes");require(row["bytes"]<=byte_cap,"dataflow edge cap")
    src_parent,src_leaf=source.parent(row["path"])
    try:src=os.open(src_leaf,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=src_parent)
    finally:os.close(src_parent)
    dst=None;dst_parent=None
    try:
        before=os.fstat(src)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==row["bytes"],"dataflow source regularity")
        dst_parent,dst_leaf=destination.parent(target_path)
        clock.check();dst=os.open(dst_leaf,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=dst_parent)
        count=0;h=hashlib.sha256()
        while True:
            clock.check();body=os.read(src,65536)
            if not body:break
            count+=len(body);require(count<=byte_cap,"dataflow overflow");h.update(body)
            at=0
            while at<len(body):
                clock.check();n=os.write(dst,body[at:]);require(n>0,"dataflow shortwrite");at+=n
        after=os.fstat(src)
        require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),"dataflow source mutated")
        require(count==row["bytes"] and h.hexdigest()==row["sha256"],"dataflow source pin")
        os.fsync(dst);clock.check();os.fsync(dst_parent);clock.check()
        return {"path":target_path,"bytes":count,"sha256":h.hexdigest(),"role":"generated_input",
                "from_artifact_id":row["artifact_id"]}
    finally:
        os.close(src)
        if dst is not None:os.close(dst)
        if dst_parent is not None:os.close(dst_parent)

def materialize(stage,upstream,destination,*,clock,ledger,cap):
    rows=[]
    for edge in stage.get("upstream_inputs",[]):
        require(edge["from_stage"] in upstream,"uncollected native predecessor")
        previous=upstream[edge["from_stage"]]
        require(previous["collection"].get("complete") is True,"failed predecessor")
        if stage["role"]=="candidate":
            require(edge.get("candidate_visible") is True and edge.get("visibility_source_pin"),"unadmitted generated candidate input")
            require(edge.get("contains_assessment_target") is False and edge.get("contains_reference_method") is False,"private result/code in candidate input")
        match=[a for a in previous["collection"]["artifacts"] if a["artifact_id"]==edge["artifact_id"]]
        require(len(match)==1,"unknown predecessor artifact")
        from .strict import Root
        with Root(previous["output_root"],private=True) as source:
            row=copy_verified(source,destination,match[0],edge["to_path"],clock=clock,byte_cap=cap)
        ledger.charge(read_bytes=row["bytes"],output_bytes=row["bytes"]);rows.append(row)
    return rows
