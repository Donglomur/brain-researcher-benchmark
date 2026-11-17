"""Actual future Linux PID/start/boot identity; independently qualified clock map required."""
import os
import stat
from .common import need,closed,integer,failure

def kernel_read(path,cap,meter):
    meter.charge("read_bytes",cap+1);fd=None;primary=None;raw=b""
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        need(stat.S_ISREG(os.fstat(fd).st_mode),"selected kernel ordinary interface")
        while len(raw)<=cap:
            chunk=os.read(fd,min(65536,cap+1-len(raw)))
            if not chunk:break
            raw+=chunk
        need(len(raw)<=cap,"bounded complete kernel metadata")
    except BaseException as error:
        primary=error;meter.own_error(error,"kernel_read")
    if fd is not None:
        closing,fd=fd,None
        try:os.close(closing)
        except BaseException as error:
            meter.cleanup_errors.append(failure(error))
            if primary is None:primary=error;meter.own_error(error,"kernel_close")
    if primary is not None:raise primary
    return raw

def process_identity(pid,*,launch_nonce,source,parent_launch,mapping,meter):
    integer(pid,1)
    closed(mapping,("schema","source","qualification","clock_ticks","tick_to_monotonic_offset_ns","boot_id"))
    need(mapping["schema"]=="four_linux_start_clock_mapping_v1","separately qualified original clock mapping")
    integer(mapping["clock_ticks"],1)
    need(os.sysconf("SC_CLK_TCK")==mapping["clock_ticks"],"actual kernel tick domain")
    boot=kernel_read('/proc/sys/kernel/random/boot_id',128,meter).decode('ascii').strip()
    need(boot==mapping["boot_id"],"same selected actual Linux boot")
    raw=kernel_read('/proc/'+str(pid)+'/stat',8192,meter)
    end=raw.rfind(b')');begin=raw.find(b'(')
    need(begin>0 and end>begin and int(raw[:begin].strip())==pid,"actual process stat owner")
    fields=raw[end+2:].split()
    need(len(fields)>=20,"complete original process start field")
    ticks=int(fields[19]);integer(ticks)
    offset=mapping["tick_to_monotonic_offset_ns"]
    need(type(offset) is int,"qualified integer clock-domain translation")
    start=ticks*1000000000//mapping["clock_ticks"]+offset;integer(start,1)
    return {"boot_id":boot,"pid":pid,"start_monotonic_ns":start,"launch_nonce":launch_nonce,
            "source":source,"parent_launch":parent_launch}

