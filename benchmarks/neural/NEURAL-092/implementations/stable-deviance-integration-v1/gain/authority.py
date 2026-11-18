"""Original live coordinator registry; source selection is never a capability."""
class ScientificAuthorityUnavailable(RuntimeError):
    pass

def require_live(host, operation):
    from host092.custody import require
    try:return require(host,operation)
    except (RuntimeError,TypeError,KeyError)as error:
        raise ScientificAuthorityUnavailable('No acquired current coordinator: '+operation)from error
