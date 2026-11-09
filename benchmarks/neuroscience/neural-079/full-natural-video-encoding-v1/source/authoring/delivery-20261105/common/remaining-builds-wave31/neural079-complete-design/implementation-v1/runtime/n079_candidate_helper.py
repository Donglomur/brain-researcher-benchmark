"""Same packaged numerical helper callable by F code and I tool execution.

Only the fit-helper arm receives this source and the one immutable public
configuration file. This is untrusted sandbox computation, not a protected
score or semantic proof; the supervisor accounts its actual process scope.
"""
import hashlib
import json
import os
import stat


def require(value, message):
    if not value:
        raise ValueError(message)


def configuration(descriptor):
    require(type(descriptor) is dict and set(descriptor) == {'path','bytes','sha256'} and
            type(descriptor['bytes']) is int and descriptor['bytes'] > 0, 'selected complete helper configuration descriptor')
    # The path is fixed by the source-owned view; caller aliases never choose
    # another file. All numerical ceilings come from its admitted contents.
    fd = os.open('/common/helper-configuration.json', os.O_RDONLY | os.O_NOFOLLOW); error = None
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == descriptor['bytes'], 'ordinary complete helper configuration')
        raw = os.read(fd, descriptor['bytes'] + 1)
        require(len(raw) == descriptor['bytes'] and os.read(fd, 1) == b'' and hashlib.sha256(raw).hexdigest() == descriptor['sha256'],
                'same whole immutable helper configuration')
        after = os.fstat(fd)
        require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns) ==
                (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns), 'stable helper configuration identity')
        def pairs(rows):
            out={}
            for k,v in rows:
                require(k not in out,'duplicate helper configuration key');out[k]=v
            return out
        value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite configuration')))
        require(type(value) is dict and set(value)=={'schema','numeric_pin','source_bytes','mapping_bytes','block_columns','limits'}, 'closed shared helper configuration')
        require(value['schema']=='n079_shared_sandbox_helper_configuration_v1','shared F/I numerical helper schema')
        require(set(value['limits'])=={'max_rows','max_query_rows','max_columns','max_matrix_elements','max_live_float_slots'},'complete explicit helper limits')
        require(all(type(v) is int and v>0 for v in list(value['limits'].values())+[value['source_bytes'],value['mapping_bytes'],value['block_columns']]),
                'finite future-selected helper ceilings; no default capacity')
        require(set(value['numeric_pin'])=={'bytes','sha256'} and type(value['numeric_pin']['bytes']) is int and
                value['numeric_pin']['bytes']>0 and value['numeric_pin']['bytes']<=value['source_bytes'], 'full selected numerical source identity')
        return value
    except BaseException as exc:
        error=exc;raise
    finally:
        try:os.close(fd)
        except BaseException as exc:
            if error is None:raise
            error.add_note('Secondary sandbox helper configuration close: '+type(exc).__name__)


def run_helper(request, helper_request):
    """Return actual fit/predictions/state using only the permitted mounts."""
    require(request['helper_configuration'] is not None,'packaged helper is unavailable in the basic arm')
    chosen=configuration(request['helper_configuration'])
    from n079_fit_helper import load_numeric, compute
    numeric=load_numeric('/source/n079_numeric_r1.py',chosen['numeric_pin'],chosen['source_bytes'])
    return compute({**request,'helper':helper_request},numeric,chosen['limits'],
                   column_block=chosen['block_columns'],mapping_limit=chosen['mapping_bytes'])
