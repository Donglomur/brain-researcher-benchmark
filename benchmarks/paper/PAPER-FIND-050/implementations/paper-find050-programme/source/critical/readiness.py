"""Scientific gates remain separate from source compilation or metadata validation."""
from .programme import contract
from .core import need
def gates():return contract("GATES.json")["gates"]
def unresolved():
 return [{"id":r["id"],"reason":r["requirement"]} for r in gates() if r["state"]!="qualified"]
def require_live_authority(authority,phase,source_sha256):
 # A JSON record or matching pin is not a live operator capability.
 from .sandbox import QualifiedHost
 need(type(authority) is QualifiedHost,"actual host producer required")
 authority.require(phase,source_sha256)
 return authority
