"""Actual full-panel consolidation inside the protected controller scope."""
import importlib
from n079_common import require, integer, identity, close_all
from n079_arrays import MatrixReader, MatrixWriter, preflight
from n079_products import write_index
from n079_plan import bundles, QUERY, PERSONS, Q


def consolidate(context, repository, supervisor, output_fd, candidates, coordinate_pin, *, coordinate_block, max_open_files):
    require(integer(max_open_files, 1) >= 108, 'all102 actual query inputs and6 output writers before opening')
    width = integer(coordinate_block, 1); require(width <= Q, 'full-grid selected consolidation block')
    np = importlib.import_module('numpy'); results = []
    require(set(candidates['queries']) == set(candidates['fitted']) == set(candidates['reports']) == {b['id'] for b in bundles()},
            'all36 actual complete candidate bundles')
    for bundle in bundles():
        key = bundle['id']; query_records = candidates['queries'][key]
        require(set(query_records) == set(QUERY), 'all102 completed current-query identities')
        readers = []; writers = []; first = None; completed = []
        try:
            preflight(context.numeric_limits, 102, width, 6 * 102 * width * 4)
            for query in QUERY:
                row = query_records[query]; item = row['prediction']
                registration = supervisor.request('material_record', {'material_name': item['path']})
                require(registration['pin'] == {k: item[k] for k in ('bytes', 'sha256')}, 'actual observed query material registration')
                if item['path'] in repository.catalog:
                    require(repository.catalog[item['path']] == registration, 'unchanged existing query registry')
                else:
                    repository.catalog[item['path']] = registration
                matrix = {'object': item, 'shape': [6, Q], 'dtype': '<f8',
                          'rows_pin': identity(list(PERSONS), context.encoding_limits), 'columns_pin': coordinate_pin,
                          'lineage_pin': identity(row, context.encoding_limits)}
                readers.append(MatrixReader(context, repository, matrix, context.numeric_limits, 'controller'))
            for person in PERSONS:
                lineage = {'rows_pin': identity(list(QUERY), context.encoding_limits), 'columns_pin': coordinate_pin,
                    'lineage_pin': identity({'bundle': key, 'person': person,
                        'queries': [query_records[q] for q in QUERY], 'trained': candidates['fitted'][key]['evidence']}, context.encoding_limits)}
                writers.append(MatrixWriter(context, output_fd, key + '-' + person + '-prediction.f64', 102, Q, '<f8',
                                            context.numeric_limits, 'controller', lineage))
            for start in range(0, Q, width):
                stop = min(Q, start + width); b = stop - start
                preflight(context.numeric_limits, 102, b, 6 * 102 * b * 4)
                panels = np.empty((6, 102, b), dtype='float64')
                for position, reader in enumerate(readers):
                    panels[:, position, :] = reader.block(list(range(6)), start, stop)
                for person_index, writer in enumerate(writers):
                    writer.append_columns(start, panels[person_index])
            for person, writer in zip(PERSONS, writers):
                completed.append({'person': person, 'matrix': writer.finish()})
            report = candidates['reports'][key]
            report_object = write_index(context, output_fd, report['report'], 'controller', key + '-report.json')
            results.append({'id': key, 'predictions': completed, 'report_object': report_object,
                'report_record': report, 'fit_record': candidates['fitted'][key],
                'queries': [{'video_id': q, 'record': query_records[q]} for q in QUERY]})
        except BaseException as error:
            first = error; error.n079_prefix = {'complete_candidate_panels': results, 'active_bundle': key,
                                                'active_completed_person_outputs': completed}; raise
        finally:
            close_all([('candidate query reader', lambda reader=reader: reader.close(first)) for reader in readers] +
                      [('candidate panel writer', lambda writer=writer: writer.close(first)) for writer in writers], first)
    return results
