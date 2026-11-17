"""Exact A/B views and F-before-exposure construction, never isolation claims."""
from pathlib import Path
from .custody import need, parse, pin, read_pin, write_json, write_new, new_directory


def stage(root, bindings, *, arm, mode, phase, packet_pin, destination, budget, parents):
    need(arm in ('A', 'B') and mode in ('F', 'I') and phase in ('author', 'replay'), 'closed view identity')
    include_packet = phase == 'replay' or mode == 'I'
    need(include_packet == (packet_pin is not None), 'F authoring cannot receive evaluation packet')
    spec = parse(read_pin(root, bindings['roles']['access_views'], 1_048_576, budget))
    source_root = bindings['legacy_package_root']
    seen = set(); written = []; total = 0
    def put(name, raw):
        nonlocal total
        pieces = name.split('/')
        need(not name.startswith('/') and all(x not in ('', '.', '..') for x in pieces)
             and name not in seen, 'closed unique public view target')
        total += len(raw)
        need(total <= 32_000_000, 'original complete32MB view domain')
        for index in range(1, len(pieces)):
            parent = Path(destination).joinpath(*pieces[:index])
            if not parent.exists():
                new_directory(parent.parent, parent.name, budget)
            need(parent.is_dir() and not parent.is_symlink(), 'owned view ancestry')
        written.append({'target': name, **write_new(Path(destination) / name, raw, budget, 24_000_128)})
        seen.add(name)
    for row in spec['files']:
        if row['arm'] not in ('both', arm):
            continue
        need(row['source'].startswith('public/'), 'public sources only')
        d = {'path': source_root + '/' + row['source'], 'bytes': row['bytes'], 'sha256': row['sha256']}
        put(row['target'], read_pin(root, d, 4_000_000, budget))
    if include_packet:
        raw = read_pin(root, packet_pin, 4_000_000, budget)
        packet = parse(raw)
        parents.protocol['validate_packet'](packet, parents.people)
        put('data/packet.json', raw)
        path = Path(packet_pin['path'])
        if not path.is_absolute():
            path = Path(root) / path
        from .custody import capture
        raw, actual = capture(path.with_name('features.npy'), 24_000_128, budget)
        need(actual['sha256'] == packet['features_sha256'], 'exact same observation packet')
        put('data/features.npy', raw)
    view = {'schema': 'neural098-full-view-v1', 'arm': arm, 'mode': mode, 'phase': phase,
            'evaluation_packet_included': include_packet, 'source_files': written,
            'benchmark_reference_included': False, 'isolation_attested_here': False}
    write_json(Path(destination) / 'VIEW.json', view, budget)
    return view


def paired_views(left, right):
    """Compare shared actual view bytes, excluding the B-only source directory."""
    def shared(view):
        out = {}
        for d in view['source_files']:
            name = d['target']
            if not name.startswith('source/'):
                out[name] = {k: d[k] for k in ('bytes', 'sha256')}
        return out
    need(shared(left) == shared(right), 'A/B shared bytes exactly equal')


def sealed_program(program_path, budget):
    from .custody import capture
    raw, actual = capture(program_path, 1_048_576, budget)
    need(raw and b'\0' not in raw, 'bounded ordinary Python candidate source')
    raw.decode('utf-8')
    return raw, actual
