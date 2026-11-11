"""Pure fixed configuration encoding; never installs or certifies a deployment."""
from .operator_records import validate_operator_record
from .operator_intake import canonical,require

def encode_installed_profile_module_v1(profile):
    validate_operator_record('InstalledOperatorProfileV1',profile)
    raw=canonical(profile);require(len(raw)<=65536,'complete installed configuration bound')
    return ('# External qualified installed-entry configuration; no runtime setter.\nPROFILE_RAW = '+repr(raw)+'\n').encode('utf-8')
