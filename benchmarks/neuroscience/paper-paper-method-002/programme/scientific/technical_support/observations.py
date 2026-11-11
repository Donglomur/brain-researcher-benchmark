"""Actual local observations, explicitly not an external native resource issuer."""
def synchronize(tree):
 import jax
 for leaf in jax.tree_util.tree_leaves(tree):
  if hasattr(leaf,'block_until_ready'):leaf.block_until_ready()
 return tree
def snapshot():
 import resource,sys,time,jax
 devices=[]
 for device in jax.devices():
  stats=device.memory_stats()
  devices.append({'platform':device.platform,'device_kind':device.device_kind,'id':device.id,'memory_stats':stats})
 usage=resource.getrusage(resource.RUSAGE_SELF)
 return {'monotonic_ns':time.monotonic_ns(),'process_peak_rss_bytes':int(usage.ru_maxrss*(1 if sys.platform=='darwin'else 1024)),
         'user_seconds':usage.ru_utime,'system_seconds':usage.ru_stime,'devices':devices,
         'extent':'process lifetime high-water; device allocator statistics when supported, not whole native parent peak'}
def measure(ctx,fn,*args,sync=True):
 ctx.checkpoint();before=snapshot()
 value=fn(*args)
 if sync:synchronize(value)
 after=snapshot();ctx.checkpoint()
 return value,{'before':before,'after':after,'elapsed_ns':after['monotonic_ns']-before['monotonic_ns'],
              'synchronized':sync,'external_native_qualification':False}
