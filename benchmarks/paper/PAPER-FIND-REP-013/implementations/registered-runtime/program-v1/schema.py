"""Public wire schema; geometry definitions remain in TASK.md, not source syntax."""
CAPS={'cells.csv':500000,'branches.csv':4000000,'author_sections.csv':3000000,'components.csv':250000,'summary.json':200000,'interpretation.json':20000}
REQUIRED=tuple(n for n in CAPS if n!='interpretation.json')
TOTAL_CAP=8000000
TABLES={
'cells.csv':{'keys':['cell_id'],'columns':'cell_id species n_nodes n_components n_tips n_segments max_order graph_length_um author_sholl_length_um relative_export_difference analysis_eligible has_author_sections author_retained_sections author_retained_length_um declared_diameter_thin_fraction reloaded_size_thin_fraction edge_thin_fraction_1.0 edge_thin_fraction_1.310202 edge_thin_fraction_1.6'.split(),'rows':10},
'branches.csv':{'keys':['cell_id','start_id','end_id'],'columns':'cell_id start_id end_id component_root order terminal n_edges length_um mean_edge_diameter_um'.split(),'rows':100000},
'author_sections.csv':{'keys':['cell_id','section_id'],'columns':'cell_id section_id original_nodes length_um declared_diameter_um reloaded_size_um order'.split(),'rows':100000},
'components.csv':{'keys':['cell_id','root_id'],'columns':'cell_id root_id n_nodes length_um n_tips'.split(),'rows':10000}}
STRINGS={'cell_id','species'}
INTEGERS={'start_id','end_id','root_id','component_root','section_id','n_nodes','n_components','n_tips','n_segments','max_order','analysis_eligible','has_author_sections','author_retained_sections','order','terminal','n_edges','original_nodes'}
NULLABLE={'author_retained_sections','author_retained_length_um','declared_diameter_thin_fraction','reloaded_size_thin_fraction'}
CELLS=('H13_Poly_1','H13_Split_1','H13_Split_3','H14_Poly_2','Mse_Normative_1','Mse_Normative_2','Mse_Poly_1','Mse_Split_1','Mse_Split_2','T6051_Poly_1')
def unit(column):
 if column.endswith('_um'):return 'micrometres'
 if 'order' in column:return 'branch_order'
 if column in ('terminal','analysis_eligible','has_author_sections'):return 'binary_flag'
 if column in INTEGERS or column.startswith('n_') or column in ('mean_segments','sd_segments'):return 'count'
 return 'dimensionless'
