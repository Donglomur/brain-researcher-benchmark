"""Small invented packet and write-once controls, for the isolated preparer."""
import io
import tempfile
from pathlib import Path

GUARD_NAMES = (
    'canonical_ascii_newline_and_duplicate_rejection',
    'strict_hash_pins_allow_empty_only_when_declared',
    'complete_uint32_observation_schema',
    'finite_increasing_relative_clock_schema',
    'count_only_projection_has_exact_members_values_and_dtypes',
    'maximum_uint32_projection_preserves_counts',
    'bounded_write_once_publication_rejects_existing_final',
    'post_rename_directory_sync_failure_cannot_overwrite_final',
)


def run(core, count_packet, np, tick=None):
    names = []
    def check(name, condition):
        if tick is not None:
            tick()
        if not condition:
            raise AssertionError(name)
        names.append(name)
    def rejected(fn):
        try:
            fn()
        except (ValueError, OSError):
            return True
        return False
    body = b'{"a":"\\u00e9","z":1}\n'
    check(GUARD_NAMES[0], core.canonical({'z': 1, 'a': '\u00e9'}) == body and
          core.parse(body, canonical_required=True) == {'a': '\u00e9', 'z': 1} and
          rejected(lambda: core.parse(b'{"x":1,"x":2}\n')) and
          rejected(lambda: core.parse(b'{"x":NaN}\n')) and
          rejected(lambda: core.parse(b'{ "x":1}\n', canonical_required=True)))
    empty = core.digest(b'')
    check(GUARD_NAMES[1], not core.valid_pin(empty) and core.valid_pin(empty, allow_empty=True)
          and not core.valid_pin({'bytes': True, 'sha256': '0' * 64}, allow_empty=True)
          and not core.valid_pin({'bytes': 0, 'sha256': '0' * 64}, allow_empty=True))
    observation = {'target_bin': 3000, 'counts': [0, 4294967295] + [1] * 94}
    check(GUARD_NAMES[2], core.observation(observation, 3000) == observation['counts'] and
          rejected(lambda: core.observation({'target_bin': 3000, 'counts': [0] * 95}, 3000)) and
          rejected(lambda: core.observation({'target_bin': 3000, 'counts': [True] + [0] * 95}, 3000)) and
          rejected(lambda: core.observation(observation, 3001)))
    check(GUARD_NAMES[3], core.interval([60., 60.02]) == [60., 60.02] and
          rejected(lambda: core.interval([60., 60.])) and
          rejected(lambda: core.interval([60., float('inf')])) and
          rejected(lambda: core.interval([False, 60.02])))
    counts = np.zeros((2, 96), dtype=np.uint32)
    edges = np.asarray([745., 745.02, 745.04], dtype=np.float64)
    raw = count_packet(counts, edges)
    with np.load(io.BytesIO(raw), allow_pickle=False) as saved:
        correct = len(saved.files) == 2 and set(saved.files) == {'counts', 'bin_edges_seconds'}
        correct &= saved['counts'].dtype == np.dtype('uint32') and np.array_equal(saved['counts'], counts)
        correct &= saved['bin_edges_seconds'].dtype == np.dtype('float64') and np.array_equal(saved['bin_edges_seconds'], edges)
    check(GUARD_NAMES[4], bool(correct))
    counts[:] = 4294967295
    raw = count_packet(counts, edges)
    with np.load(io.BytesIO(raw), allow_pickle=False) as saved:
        correct = np.array_equal(saved['counts'], counts) and saved['counts'].dtype == np.dtype('uint32')
    check(GUARD_NAMES[5], bool(correct))
    with tempfile.TemporaryDirectory() as folder:
        writer = core.Writer(folder, {'x.json': 16})
        pin = writer.write('x.json', b'{}\n')
        check(GUARD_NAMES[6], pin == core.digest(b'{}\n') and writer.completed == 1 and
              rejected(lambda: writer.write('x.json', b'{"x":1}\n')) and
              (Path(folder) / 'x.json').read_bytes() == b'{}\n')
    with tempfile.TemporaryDirectory() as folder:
        writer = core.Writer(folder, {'x.json': 16})
        original_sync = writer.sync
        calls = 0
        def fail_after_rename():
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('invented post-rename directory sync failure')
            original_sync()
        writer.sync = fail_after_rename
        first_failed = rejected(lambda: writer.write('x.json', b'{}\n'))
        writer.sync = original_sync
        second_failed = rejected(lambda: writer.write('x.json', b'{"x":1}\n'))
        check(GUARD_NAMES[7], first_failed and second_failed and writer.pins == {} and
              (Path(folder) / 'x.json').read_bytes() == b'{}\n' and
              not (Path(folder) / 'x.json.next').exists())
    if tuple(names) != GUARD_NAMES:
        raise AssertionError('Exact packet guard roster')
    return {'status': 'packet_controls_passed', 'checks': len(names), 'names': names,
            'invented_only': True, 'empirical_inputs_opened': 0, 'model_fits': 0}
