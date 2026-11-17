"""Load the frozen helper modules after independent source/environment admission.

The support helper uses an absolute `support` import. This loader binds only the
authenticated sibling package while loading it and restores the prior namespace.
It does not grant execution authority or read any numerical operand.
"""
import importlib.util
from pathlib import Path
import sys


def load_stores(guard):
    guard()
    base=Path(__file__).resolve().parent
    from . import support
    old=sys.modules.get('support')
    sys.modules['support']=support
    try:
        spec=importlib.util.spec_from_file_location(__package__+'.packet_store',base/'support/store-v1/packet_store.py')
        packet=importlib.util.module_from_spec(spec);spec.loader.exec_module(packet)
    finally:
        if old is None:sys.modules.pop('support',None)
        else:sys.modules['support']=old
    spec=importlib.util.spec_from_file_location(__package__+'.artifact_store',base/'reference/artifact-store-v1/artifact_store.py')
    artifact=importlib.util.module_from_spec(spec);spec.loader.exec_module(artifact)
    return packet,artifact
