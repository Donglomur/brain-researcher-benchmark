"""One generated public-location control; never run the existing18 methods.

The fixture generator and composer are unchanged sibling files. All neural/image
operands are invented metadata in memory. Path.open observation covers helper
dependency loading, not Python/NumPy library I/O or OS isolation.
"""
from pathlib import Path
import os
import sys
from unittest.mock import patch

# Existing numerical runtime is a transitive helper import; no array is created.
import numpy  # noqa: F401


def main():
    support = Path(__file__).resolve().parent.parent
    implementations = support.parent
    composer_root = implementations / 'target7-composition-v1'
    sys.path.insert(0, str(composer_root))
    import test_target7_composition as fixtures
    composer = fixtures.c
    assert Path(fixtures.__file__).resolve() == composer_root / 'test_target7_composition.py'
    assert Path(composer.__file__).resolve() == composer_root / 'target7_composition.py'
    original_open = Path.open
    opened = []

    def observed_open(path, *args, **kwargs):
        resolved = path.absolute()
        assert resolved.is_relative_to(implementations), 'external artifact path opened'
        opened.append(resolved)
        return original_open(path, *args, **kwargs)

    with patch.dict(os.environ, {
        'MINDBRIDGE_OPERATOR_ROOT': '/forbidden-legacy-operator-root',
        'MINDBRIDGE_IMPLEMENTATIONS_ROOT': '/forbidden-legacy-implementation-root',
    }), patch.object(Path, 'open', observed_open):
        deps = composer.load_dependencies(support / 'private', implementations)
    assert len(opened) == len(set(opened)) == 15, 'complete bounded dependency topology'
    assert support / 'public/protocol.py' in opened, 'original public/private protocol alias'
    for name in ('io', 'protocol', 'provision'):
        assert Path(deps[name].__file__).is_relative_to(support / 'private')
    assert Path(deps['source_protocol'].__file__).is_relative_to(implementations / 'source-protocol-v2')
    assert Path(deps['panel'].__file__).is_relative_to(implementations / 'original-panel-v1')

    # Reuse only the existing generator, never setUpClass or any of its18 tests.
    plan, receipt, bundle = fixtures.fixture(deps)
    assert len(receipt['source_files_verified']) == 88 and len(plan['cases']) == 32
    pins = {name: {'bytes': 1, 'sha256': 'a' * 64} for name in ('plan', 'receipt', 'bundle')}
    packet = composer.compose_panel(plan, receipt, bundle, deps, input_pins=pins)
    assert packet['source_kind'] == 'generated_engineering_control'
    assert len(packet['rows']) == 6 and len(packet['test_image_ids']) == 982
    assert packet['preparation_composition']['finding_count'] == 48
    assert packet['preparation_composition']['scientific_qualification'] is False
    assert packet['preparation_composition']['original_membership_authenticated'] is False
    assert packet['information_condition'] == 'paper_data'
    assert all([image['image_id'] for image in row['images']] == packet['test_image_ids']
               for row in packet['rows'])
    print('PASS: one public-location composition control;15 local dependency reads;88 files/32 cases/6 conditions/982 gallery; no legacy operator path, arrays, or18-method replay.')


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        # Keep the combined pool log bounded even if a metadata assertion fails.
        print(('FAIL: ' + type(error).__name__ + ': ' + str(error))[:6000])
        raise SystemExit(1)
