"""Concrete future original-derivative extraction route using exact inherited feature functions.
No extraction, header access, image operation or native import is performed during construction.
"""
from pathlib import Path
import sys
import shutil
from .common import need, load, read, pin, put, relative, digest
from .spec import PEOPLE, DIMS, DOMAIN


def extract(admission, source_root, image_root, output, execution_selection):
    need(admission['execution_selection'] == execution_selection and admission['domain'] == DOMAIN, 'Exact execution selection')
    for kind in ('release_bridge', 'clock_geometry', 'preprocessing', 'native_environment', 'rights', 'immutable_mount'):
        need(admission[kind]['status'] == 'QUALIFIED' and admission[kind].get('evidence'), 'Unqualified preparation prerequisite: ' + kind)
    need(len(admission['derivatives']) == 64 and sum(x['kind'] == 'FIF' for x in admission['derivatives']) == 16 and
         sum(x['kind'] == 'EYE_CSV' for x in admission['derivatives']) == 48, 'All original 16+48 derivative objects')
    need(len(admission['images']) == 22248, 'All original authentic images')
    root = Path(source_root); images = Path(image_root); out = Path(output); out.mkdir(exist_ok=False)
    for record in admission['derivatives']:
        relative(record['path'])
    # Native imports occur only beyond separately selected authentic admission.
    import numpy as np
    legacy = Path(__file__).parent / 'legacy'
    sys.path.insert(0, str(legacy))
    import extract as inherited
    import delivery_io as legacy_io
    import array_io
    rows = load(root / admission['roster']['path'], 64 << 20, {k: admission['roster'][k] for k in ('bytes', 'sha256')})
    need(len(rows) == 108192, 'Complete original source trial dispositions')
    experimental = [r for r in rows if r['trial_type'] == 'exp']
    experimental.sort(key=lambda r: (PEOPLE.index(r['person']), r['epoch_index']))
    need(len(experimental) == 88992, 'Full experimental support')
    expected = admission['sensor_order']; need(len(expected) == len(set(expected)) == 271, 'Qualified sensor order')
    derivatives = [{k: x[k] for k in ('path', 'bytes', 'sha256')} for x in admission['derivatives']]
    states = inherited.verify_bundle(root, derivatives)
    neural = []; ocular = []; features = {}
    try:
        for person in PEOPLE:
            roster = [r for r in experimental if r['person'] == person]; need(len(roster) == 22248, 'Whole person')
            neural.append(inherited.meg(root, person, roster, expected))
            eyes = np.zeros((22248, 5, 24), dtype='<f4'); lookup = {r['image']: i for i, r in enumerate(roster)}
            for session in range(1, 13):
                subset = [r for r in roster if r['session'] == session]
                name = f'derivatives/preprocessed/eyes_epoched_cleaned_P{person[-1]}_S{session}.csv'
                record = next(x for x in derivatives if x['path'] == name)
                with legacy_io.verified_stream(root / name, {k: record[k] for k in ('bytes', 'sha256')}) as stream:
                    values = inherited.eye_file(stream, session, subset)
                for j, row in enumerate(subset): eyes[lookup[row['image']]] = values[j]
            ocular.append(eyes)
        image_order = []; visual = []; seen = set()
        expected_images = {r['image']: r['image_path'] for r in experimental}
        for record in sorted(admission['images'], key=lambda r: r['image']):
            need(record['image'] not in seen and expected_images.get(record['image']) == record['image_path'], 'Original image join')
            seen.add(record['image']); relative(record['local_path'])
            body = read(images / record['local_path'], 30 << 20, {k: record[k] for k in ('bytes', 'sha256')})
            visual.append(inherited.visual_features(body)); image_order.append(record['image'])
        need(seen == set(expected_images), 'Complete image identity support')
        for family, values in [('neural', np.concatenate(neural)), ('ocular', np.concatenate(ocular)), ('visual', np.stack(visual))]:
            filename = family + '.npy'
            descriptor = array_io.write(out / filename, values, 3 << 30)
            features[family] = {'path': filename, **descriptor, 'shape': list(values.shape)}
    finally:
        inherited.recheck(root, states)
    for name in ('roster', 'labels'):
        rec = admission[name]; body = read(root / rec['path'], 64 << 20, {k: rec[k] for k in ('bytes', 'sha256')})
        (out / (name + '.json')).write_bytes(body)
    result = {'domain': DOMAIN, 'execution_selection': execution_selection, 'generation': admission['generation'],
              'features': features, 'image_order': image_order,
              'roster': {'path': 'roster.json', **pin(read(out / 'roster.json', 64 << 20))},
              'labels': {'path': 'labels.json', **pin(read(out / 'labels.json', 4 << 20))},
              'target_commitment': admission['target_commitment'],
              **{k: admission[k] for k in ('release_bridge', 'clock_geometry', 'preprocessing')},
              'original_source_admission': digest(admission), 'scientifically_qualified': False}
    put(out / 'FEATURE_ADMISSION.json', result)
    return result
