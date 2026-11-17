"""Read-only in-worker model client. No endpoints, credentials or host tools."""
import os
from morse_bootstrap import ToolClient

_client=None

def generate(messages, max_output_tokens):
    global _client
    if _client is None:
        read_fd=int(os.environ['OPENBMI_BROKER_READ_FD'])
        write_fd=int(os.environ['OPENBMI_BROKER_WRITE_FD'])
        frame_bytes=int(os.environ['OPENBMI_BROKER_FRAME_BYTES'])
        if read_fd<3 or write_fd<3 or read_fd==write_fd or not 1<=frame_bytes<=0xffffffff:
            raise ValueError('Fixed worker broker descriptors')
        _client=ToolClient(os.fdopen(os.dup(read_fd),'rb',buffering=0),
                           os.fdopen(os.dup(write_fd),'wb',buffering=0),frame_bytes)
    return _client.generate(messages,max_output_tokens)

def close():
    global _client
    if _client is not None:
        _client.input.close()
        _client.output.close()
        _client=None
