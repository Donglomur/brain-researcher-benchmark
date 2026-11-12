"""Reused exact strict missing-resource parser; no runtime contract changes."""
import json

def absence(returncode,stdout,stderr,kind,name):
    """Only exact direct or single-message JSON Docker missing-resource errors.

    Preserve resource-name case, reject ambiguous/extra keys, and never use
    substring matching. JSON does not convert a denied/transport error to absence.
    """
    if (type(returncode)is not int or returncode!=1 or type(stdout)is not str or type(stderr)is not str
            or len(stdout.encode())>64 or stdout.strip()not in ('','[]') or len(stderr.encode())>4096
            or kind not in ('volume','container') or type(name)is not str):return False
    observed=stderr.strip()
    bodies=({f'get {name}: no such volume'}if kind=='volume'else {f'No such container: {name}',f'no such container: {name}'})
    direct=({f'Error response from daemon: get {name}: no such volume',f'Error: No such volume: {name}',
             f'error response from daemon: get {name}: no such volume',f'error: no such volume: {name}'}if kind=='volume'
            else {f'Error: No such object: {name}',f'Error response from daemon: No such container: {name}',
                  f'error: no such object: {name}',f'error response from daemon: no such container: {name}'})
    if observed in direct:return True
    prefix='Error response from daemon: '
    if not observed.startswith(prefix):return False
    def unique_object(pairs):
        value={}
        for key,item in pairs:
            if key in value:raise ValueError('duplicate Docker error key')
            value[key]=item
        return value
    try:
        wrapper=json.loads(observed[len(prefix):],object_pairs_hook=unique_object)
    except (ValueError,TypeError,RecursionError):return False
    return type(wrapper)is dict and set(wrapper)=={'message'} and type(wrapper['message'])is str and wrapper['message']in bodies

