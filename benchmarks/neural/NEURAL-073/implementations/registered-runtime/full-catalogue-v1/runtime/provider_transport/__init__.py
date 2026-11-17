"""Pinned, source-owned stdio model transport; no import-time effects."""
from .protocol import AdapterAdmission,SourcePin,TransportError,encode_frame,decode_frame
from .stdio import ModelAdapterSession
