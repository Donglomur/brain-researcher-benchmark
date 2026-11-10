"""Exact image-mounted provider-only entry; never mounted into candidate realms."""
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, '/program')
from transport.provider_worker import serve
if __name__ == '__main__':
    serve()
