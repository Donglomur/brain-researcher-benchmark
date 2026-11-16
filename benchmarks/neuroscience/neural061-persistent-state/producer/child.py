"""Fixed isolated child entry. No participant state is serialized or returned."""
import os
from pathlib import Path
import sys


def load_participant(wire):
    """Normal module registration, inside the isolated child only.

    The inherited worker loader omitted registration before exec_module, which
    breaks dataclasses with deferred annotations. Keep its fixed path and ABI;
    the inherited fit/infer functions and scientific code are unchanged.
    """
    import importlib.util
    name = 'n061_participant_method'
    wire.need(name not in sys.modules, 'fresh participant module per child')
    spec = importlib.util.spec_from_file_location(name, '/participant/method.py')
    wire.need(spec is not None and spec.loader is not None, 'ordinary participant module')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        wire.need(callable(getattr(module, 'fit', None)) and callable(getattr(module, 'infer', None)),
                  'original fit and infer participant ABI')
        return module
    except BaseException:
        if sys.modules.get(name) is module:
            del sys.modules[name]
        raise


def serve(method, worker, wire, reader, writer, cap, binding):
    """One fresh child, one fit, ordered full query roster, one retirement."""
    need = wire.need
    sequence = 0; state = None; fitted = False; index = 0
    while True:
        request = wire.read_frame(reader, cap)
        need(type(request) is dict and set(request) == {'version', 'sequence', 'binding', 'operation', 'payload'},
             'closed request envelope')
        need(request['version'] == 'N061_CHILD_V1' and type(request['sequence']) is int and
             request['sequence'] == sequence and request['binding'] == binding, 'bound ordered request')
        operation, payload = request['operation'], request['payload']
        if operation == 'fit':
            need(not fitted and sequence == 0 and type(payload) is dict and set(payload) == {'source'}, 'fit once')
            views = payload['source']
            need(type(views) is tuple and len(views) == 423, 'all 423 source views')
            for sid, view in zip(binding['source'], views, strict=True):
                need(view['status'] in ('complete', 'unavailable'), 'source disposition')
                if view['status'] == 'complete':
                    need(view['session'] == sid and view['cell'] == binding['cell'] and
                         view['arm'] == binding['arm'] and all('values' in w for w in view['windows']),
                         'exact cell/arm source labels')
            state = worker.fit(method, views, None)
            fitted = True; result = {'state': binding['state']}
        elif operation == 'predict':
            need(fitted and index < len(binding['evaluation']) and type(payload) is dict and
                 set(payload) == {'session', 'query'}, 'one expected prediction')
            sid = binding['evaluation'][index]; query = payload['query']
            need(payload['session'] == sid and query['status'] == 'complete' and
                 query['session'] == sid and query['cell'] == binding['cell'] and
                 query['arm'] == binding['arm'] and all('values' not in w for w in query['windows']),
                 'exact unlabeled query')
            result = worker.infer(method, state, query, None); index += 1
        elif operation == 'skip':
            need(fitted and index < len(binding['evaluation']) and payload ==
                 {'session': binding['evaluation'][index]}, 'host-owned scientific-unavailable query position')
            index += 1; result = {'skipped': payload['session']}
        elif operation == 'retire':
            need(fitted and index == len(binding['evaluation']) and payload is None, 'complete query roster before retirement')
            state = None; result = {'retired': binding['state']}
        else:
            raise ValueError('Unknown child operation')
        writer.write(wire.frame({'version': 'N061_CHILD_V1', 'sequence': sequence,
                                'binding': binding, 'operation': operation, 'result': result}, cap))
        writer.flush(); sequence += 1
        if operation == 'retire':
            return


def main():
    if not sys.flags.isolated or Path(__file__) != Path('/trusted/child.py'):
        raise RuntimeError('Fixed isolated container entry only')
    # Bootstrap and accepted worker source are copied into the only trusted mount.
    # No host-side candidate import, dependency-directory import, or state loader.
    import types
    trusted = Path('/trusted')
    def load(name, filename):
        module = types.ModuleType(name); module.__file__ = str(trusted / filename)
        sys.modules[name] = module
        exec(compile((trusted / filename).read_bytes(), module.__file__, 'exec'), module.__dict__)
        return module
    wire = load('n061_wire', 'wire.py')
    package = types.ModuleType('n061'); package.__path__ = []; sys.modules['n061'] = package
    load('n061.contracts', 'contracts.py'); worker = load('n061.worker', 'worker.py')
    cap = int(sys.argv[1]); wire.need(0 < cap <= 2**31, 'selected frame cap')
    reader = os.fdopen(os.dup(0), 'rb', buffering=0)
    writer = os.fdopen(os.dup(1), 'wb', buffering=0)
    # Candidate stdout cannot accidentally corrupt the protocol; stderr remains
    # bounded by the outside supervisor and Docker's configured log ceiling.
    os.dup2(2, 1)
    hello = wire.read_frame(reader, cap)
    wire.need(type(hello) is dict and set(hello) == {'binding'}, 'fixed bootstrap binding')
    binding = hello['binding']
    wire.need(set(binding) == {'method', 'cell', 'arm', 'source', 'evaluation', 'state'} and
              len(binding['source']) == 423 and len(binding['evaluation']) == 29 and
              binding['arm'] in ('BR', 'BC'), 'complete A0 binding')
    method = load_participant(wire)
    serve(method, worker, wire, reader, writer, cap, binding)


if __name__ == '__main__':
    main()
