"""Concrete Linux bubblewrap/cgroup command construction, never a success callback."""
import os
import sys
from .strict import require, relative, integer, Root
from .errors import SourceGap

def command(binding, roots, limits, clock):
    if sys.platform != "linux":
        raise SourceGap("Authentic execution requires independently qualified Linux isolation")
    require(binding.get("sandbox")=="bubblewrap_cgroup_v2", "qualified sandbox binding")
    require(binding.get("rootfs_immutable") is True, "immutable dependency snapshot required")
    require(set(roots)=={"rootfs","program","inputs","output"}, "exact sandbox mount roles")
    # Open directory descriptors, not mutable path strings, are the operands.
    for root in roots.values():
        require(root.fd is not None, "held root required")
    bwrap=binding["bwrap_path"]
    require(bwrap.startswith("/") and binding.get("bwrap_sha256"), "bwrap identity")
    require(binding.get("executable_immutable_evidence"),"immutable executable qualification")
    parent,leaf=os.path.split(bwrap)
    with Root(parent) as binary_root:
        binary_root.authenticate(leaf,{"bytes":binding["bwrap_bytes"],"sha256":binding["bwrap_sha256"]},cap=16*1024*1024,clock=clock)
    args=[bwrap,"--unshare-all","--new-session","--die-with-parent","--clearenv",
          "--ro-bind",f"/proc/self/fd/{roots['rootfs'].fd}","/",
          "--ro-bind",f"/proc/self/fd/{roots['program'].fd}","/program",
          "--ro-bind",f"/proc/self/fd/{roots['inputs'].fd}","/inputs",
          "--bind",f"/proc/self/fd/{roots['output'].fd}","/output",
          "--proc","/proc","--dev","/dev","--tmpfs","/tmp",
          "--setenv","HOME","/tmp","--setenv","PATH","/runtime/bin",
          "--setenv","PYTHONDONTWRITEBYTECODE","1","--chdir","/program"]
    require(binding.get("network") is False, "no evaluation internet")
    if binding.get("requires_gpu"):
        # GPU access is not inferred from ordinary CPU cgroups.
        require(binding.get("qualified_gpu_isolation") and binding.get("gpu_observer"),"GPU isolation/accounting not qualified")
        raise SourceGap("Remote/multiple-GPU device binding is not implemented by this local CPU adapter")
    entry=relative(binding["entrypoint"])
    argv=binding.get("argv")
    require(type(argv) is list and all(type(x) is str and "\x00" not in x for x in argv),"exact producer argv")
    require(argv==["/runtime/bin/python","-I","-S","-B","/program/"+"/".join(entry),"/inputs/invocation.json","/output"],"unreviewed producer command")
    args+=["--",*argv]
    return args, tuple(root.fd for root in roots.values())

class Cgroup:
    """An exclusively created child below the separately qualified delegated parent."""
    def __init__(self, parent, attempt, limits, clock):
        require(len(relative(attempt))==1,"one attempt component")
        if limits.get("io_max") is None:raise SourceGap("Qualified whole-I/O limit missing")
        for name in ("memory_bytes","pids","cpu_quota_us","cpu_period_us"):integer(limits[name],name,1)
        clock.check()
        os.mkdir(attempt,0o700,dir_fd=parent.fd)
        self.fd=os.open(attempt,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent.fd)
        self.parent=parent;self.attempt=attempt;self.clock=clock
        try:
            self.write("memory.max",str(limits["memory_bytes"]))
            self.write("memory.swap.max","0")
            self.write("pids.max",str(limits["pids"]))
            self.write("cpu.max",f"{limits['cpu_quota_us']} {limits['cpu_period_us']}")
            self.write("io.max",limits["io_max"])
        except BaseException as exc:
            self.close();exc.add_note("Preserve exclusively created empty cgroup as failed admission evidence.");raise
    def write(self,name,value,cleanup=False):
        require(name in {"memory.max","memory.swap.max","pids.max","cpu.max","io.max","cgroup.procs","cgroup.kill"},"cgroup control")
        self.clock.check(cleanup)
        fd=os.open(name,os.O_WRONLY|os.O_NOFOLLOW,dir_fd=self.fd)
        try:
            b=(value+"\n").encode();require(os.write(fd,b)==len(b),"shortcgroupwrite")
        finally:os.close(fd)
    def read(self,name,cleanup=False):
        require(name in {"cgroup.events","memory.peak","memory.current","memory.events","cpu.stat","io.stat","pids.current"},"cgroup observation")
        self.clock.check(cleanup)
        fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=self.fd)
        try:
            b=os.read(fd,65537);require(len(b)<=65536,"cgrouprecord bound");return b.decode()
        finally:os.close(fd)
    def populated(self,cleanup=False):
        return dict(x.split() for x in self.read("cgroup.events",cleanup).splitlines())["populated"]=="1"
    def kill(self):self.write("cgroup.kill","1",True)
    def snapshot(self,cleanup=False):
        return {n:self.read(n,cleanup) for n in ("memory.peak","memory.events","cpu.stat","io.stat","pids.current")}
    def close(self):
        if self.fd is not None:os.close(self.fd);self.fd=None

