"""Invented complete five-product wire fixture; no authentic morphology."""
import copy,csv,io,json
import schema as S
rows = {name: [] for name in S.TABLES}
for index, cell in enumerate(S.CELLS):
    components = 2 if index in (1, 2, 3) else 1
    nbranches = 3 if index == 0 else components
    cell_row = {c: '0' for c in S.TABLES['cells.csv']['columns']}
    cell_row.update(cell_id=cell, species='mouse' if cell.startswith('Mse_') else 'human',
                    n_nodes=str(4 if index == 0 else 2 * components),
                    n_components=str(components), n_tips=str(nbranches), n_segments=str(nbranches),
                    max_order='1', graph_length_um='1e308' if index == 0 else str(components),
                    author_sholl_length_um='1e308' if index == 0 else str(components),
                    analysis_eligible='1', has_author_sections='1', author_retained_sections='1',
                    author_retained_length_um='1', declared_diameter_thin_fraction='1',
                    reloaded_size_thin_fraction='1')
    rows['cells.csv'].append(cell_row)
    if index == 0:
        branches = [(1, 2, 1, '0'), (1, 3, 1, '1e308'), (1, 4, 1, '1')]
    else:
        branches = [(1 + 2*j, 2 + 2*j, 1 + 2*j, '1') for j in range(components)]
    for first, last, root, length in branches:
        rows['branches.csv'].append(dict(cell_id=cell, start_id=str(first), end_id=str(last),
            component_root=str(root), order='1', terminal='1', n_edges='1',
            length_um=length, mean_edge_diameter_um='0' if length == '0' else '1'))
    rows['author_sections.csv'].append(dict(cell_id=cell, section_id='1', original_nodes='2',
        length_um='1', declared_diameter_um='1', reloaded_size_um='0.5', order='1'))
    for j in range(components):
        rows['components.csv'].append(dict(cell_id=cell, root_id=str(1 + 2*j),
            n_nodes=str(4 if index == 0 else 2),
            length_um='1e308' if index == 0 else '1', n_tips=str(3 if index == 0 else 1)))
thresholds = ['edge_thin_fraction_1.0', 'edge_thin_fraction_1.310202', 'edge_thin_fraction_1.6']
species_summary = {k: 0 for k in ['mean_length_um','sd_length_um','mean_segments','sd_segments','mean_max_order'] + thresholds}
species_summary['n_cells'] = 5
section_summary = {'n_cells': 5, 'mean_declared_diameter_thin_fraction': 1,
    'sd_declared_diameter_thin_fraction': 0, 'mean_reloaded_size_thin_fraction': 1,
    'sd_reloaded_size_thin_fraction': 0}
matched_summary = {'n_cells': 5, **{k: 0 for k in thresholds}}
summary = {
    'schema_version': 1,
    'analysis_scope': 'post_inspection_source_consistent_subset_descriptive',
    'species': {k: copy.deepcopy(species_summary) for k in ('human', 'mouse')},
    'human_mouse_length_ratio': 1,
    'leave_one_cell_out': [{'omitted_cell': c, 'length_ratio': 1, 'edge_thin_difference': 0} for c in sorted(S.CELLS)],
    'section_estimator_conventions': {k: copy.deepcopy(section_summary) for k in ('human', 'mouse')},
    'matched_annotated_edge_estimator': {k: copy.deepcopy(matched_summary) for k in ('human', 'mouse')},
    'excluded_from_subset': [],
    'paper_reported_n_individuals': {'human': 3, 'mouse': 2},
}
def files(table_rows):
    out = {}
    for name, spec in S.TABLES.items():
        buffer = io.StringIO(newline='')
        writer = csv.DictWriter(buffer, fieldnames=spec['columns'], lineterminator='\n')
        writer.writeheader()
        writer.writerows(table_rows[name])
        out[name] = buffer.getvalue().encode()
    out['summary.json'] = json.dumps(summary, sort_keys=True).encode()
    return out
reference = files(rows)
