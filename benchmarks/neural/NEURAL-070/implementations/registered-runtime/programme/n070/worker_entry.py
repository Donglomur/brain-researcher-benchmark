"""Only capsule entry point; imports numeric leaves after operation selection."""
import sys
from .native.io import parse,dump
from .core import need
def main():
    body=sys.stdin.buffer.read(1048577);need(len(body)<=1048576,"Request byte ceiling")
    request=parse(body);need(len(request)<128,"Finite request schema")
    operation=request["operation"]
    if operation=="convert":
        from .conversion import run
    elif operation=="features":
        from .feature_producer import run
    elif operation=="prepare":
        from .preparation import run
    elif operation=="reference":
        from .reference import run
    elif operation=="score":
        from .scorer import run
    elif operation=="literal_a":
        from .literal_a import run
    else:raise ValueError("Unsupported fixed evaluator operation")
    run(request)
if __name__=="__main__":main()

