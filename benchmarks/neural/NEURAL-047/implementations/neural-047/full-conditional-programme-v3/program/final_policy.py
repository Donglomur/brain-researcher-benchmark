"""Final observed-resource acceptance, separate from active polling."""
from .common import need
def final_native(receipt,limits,now,cutoff):
    need(receipt.get("final_counters_complete") is True,"Complete final native resource observation")
    for k in ("cpu_us","memory_peak"):
        need(type(receipt.get(k)) is int and receipt[k]>=0,"Known final "+k)
    need(receipt["cpu_us"]<=limits["cpu_us"],"Final leaf CPU exceeded")
    need(receipt["memory_peak"]<=limits["memory_bytes"],"Final leaf memory exceeded")
    need(receipt["cpu_us"]>=receipt.get("last_polled_cpu_us",0),"Native counter regression")
    memory=receipt["memory_events"];pids=receipt["pids_events"]
    need(all(type(memory.get(k,0)) is int and memory.get(k,0)==0 for k in ("oom","oom_kill","oom_group_kill")),"Final native OOM event")
    need(type(pids.get("max",0)) is int and pids.get("max",0)==0,"Final native PID event")
    need(now<cutoff,"Original final native cutoff")
    need(receipt["root_waited"] and receipt["subtree_empty"],"Final native process closure")
def final_outer(obs,spec,now,cutoff):
    cpu=obs["subtree_cpu_us"];own=obs["outer_own_cpu_seconds"];memory=obs["memory_peak_bytes"]
    need(type(cpu) is int and cpu>=0 and type(own) in (float,int) and own>=0,"Known final CPU costs")
    need(cpu+own*1e6<=spec["cpu_us"],"Final outer plus subtree CPU exceeded")
    need(type(memory) is int and 0<=memory<=spec["memory_bytes"],"Final outer memory exceeded")
    need(all(type(obs["memory_events"].get(k,0)) is int and obs["memory_events"].get(k,0)==0 for k in ("oom","oom_kill","oom_group_kill")),"Final outer OOM event")
    need(type(obs["pids_events"].get("max",0)) is int and obs["pids_events"].get("max",0)==0,"Final outer PID event")
    need(now<cutoff and obs["root_waited"] and obs["subtree_empty"],"Original final outer interval/process closure")

