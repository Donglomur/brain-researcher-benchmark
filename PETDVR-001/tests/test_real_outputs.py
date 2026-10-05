"""Parent-generated real artifacts only; no additional original fits or bank writes."""
import copy
import csv
import json
import os
from pathlib import Path
import shutil
import pytest
import proof_of_work as q

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def original():
    path=os.environ.get('REPAIR_ORACLE_OUTPUT')
    if not path:pytest.skip('Parent-generated genuine source outputs required')
    return Path(path)

@pytest.fixture
def output(original,tmp_path):
    target=tmp_path/'output';shutil.copytree(original,target);return target

def table(output,name):
    with (output/name).open(newline='') as handle:
        reader=csv.DictReader(handle);return reader.fieldnames,list(reader)

def write(output,name,fields,rows):
    with (output/name).open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(rows)

def edit_json(output,name,mutator):
    path=output/name;value=json.loads(path.read_text());mutator(value);path.write_text(json.dumps(value,allow_nan=False))

def test_genuine_original(original):q.validate_output_directory(original)

def test_genuine_independent():
    path=os.environ.get('REPAIR_INDEPENDENT_OUTPUT')
    if not path:pytest.skip('Parent-run independently recomputed outputs required')
    q.validate_output_directory(path)

def test_order_columns_and_harmless_extras(output):
    for name in q.KEYS:
        fields,rows=table(output,name)
        for row in rows:row['note']='ungraded'
        write(output,name,['note']+fields[::-1],rows[::-1])
    def mutate(summary):
        summary['paired_changes'].reverse();summary['group_windows'].reverse()
        summary['targets'].reverse();summary['start_min'].reverse();summary['end_policies'].reverse()
        for row in summary['group_windows']:
            for key in ('defined_scans','represented_subjects','defined_pair_subjects'):row[key].reverse()
    edit_json(output,'summary.json',mutate);q.validate_output_directory(output)

def test_scientific_notation_ids_preserve_values(output):
    for name in q.KEYS:
        fields,rows=table(output,name)
        for row in rows:
            for field in q.INTS&set(row):
                if row[field]:
                    value=q.integer(row[field]);row[field]=format(value,'.17e');assert q.integer(row[field])==value
        write(output,name,fields,rows)
    q.validate_output_directory(output)

def test_numerical_rounding_within_public_precision(output):
    for name in q.KEYS:
        fields,rows=table(output,name)
        for row in rows:
            for field,value in row.items():
                if value and field not in q.STRINGS|q.INTS|q.BOOLS|q.TIMES:
                    row[field]=format(float(value),'.12g')
        write(output,name,fields,rows)
    q.validate_output_directory(output)

def test_honest_alternate_software_free_prose_optional_comparator(output):
    def mutate(meta):
        meta['software_versions']={'independent solver':'actual alternate implementation'}
        meta['source_observed']['scans'].reverse()
        meta['source_observed']['extra']='ungraded'
        meta['source_observed']['scans'][0]['extra']='ungraded'
    edit_json(output,'run_metadata.json',mutate)
    edit_json(output,'summary.json',lambda value:value.update(optional_two_term_comparator={'estimate':123456,'ungraded':True}))
    (output/'findings.md').write_text('The requested measurements and descriptive comparisons are supplied.')
    q.validate_output_directory(output)

def test_public_template_identity(original):
    metadata=json.loads((original/'run_metadata.json').read_text())
    assert metadata['method_contract']==json.loads((ROOT/'environment/method_contract.json').read_text())
    assert metadata['method_contract_sha256']==q.sha(ROOT/'environment/method_contract.json')

@pytest.mark.parametrize('name',list(q.KEYS))
@pytest.mark.parametrize('kind',['missing','duplicate','wrong_subject','wrong_session'])
def test_complete_matrix_membership(output,name,kind):
    fields,rows=table(output,name)
    if kind=='missing':rows.pop()
    elif kind=='duplicate':rows.append(dict(rows[0]))
    elif kind=='wrong_subject':rows[0]['subject']='sub-03'
    else:rows[0]['session']='ses-fabricated'
    write(output,name,fields,rows)
    with pytest.raises(AssertionError):q.validate_output_directory(output)

@pytest.mark.parametrize('name',[*q.KEYS,'summary.json','run_metadata.json','findings.md'])
def test_missing_required_file(output,name):
    (output/name).unlink()
    with pytest.raises((AssertionError,FileNotFoundError)):q.validate_output_directory(output)

@pytest.mark.parametrize('kind',['source_scale_coherent','source_target_swap','reference_substitution','frame_shift','single_source_value','wrong_integral','wrong_ratio','clipped_slope','compensating_slopes','infinity_start','bool_frame','sparse_predictions','zero_undefined','undefined_flag','wrong_residual_sign','wrong_rank_threshold','window_label_swap','wrong_ratio_support'])
def test_source_and_method_fabrications(output,kind):
    if kind in ('source_scale_coherent','source_target_swap','reference_substitution','frame_shift','single_source_value'):
        name='source_frames.csv';fields,rows=table(output,name)
        if kind=='source_scale_coherent':
            for row in rows:
                for field in ['reference',*q.TARGETS]:row[field]=str(float(row[field])*2)
            gf,gr=table(output,'graph_points.csv')
            for row in gr:
                for field in ('integral_target_bq_min_per_ml','integral_reference_bq_min_per_ml'):row[field]=str(float(row[field])*2)
            write(output,'graph_points.csv',gf,gr)
        elif kind=='source_target_swap':
            for row in rows:row['left_putamen'],row['right_putamen']=row['right_putamen'],row['left_putamen']
        elif kind=='reference_substitution':
            for row in rows:row['reference']=row['highbinding']
        elif kind=='frame_shift':rows[0]['frame_start_s']=str(float(rows[0]['frame_start_s'])+1)
        else:
            # Deterministically alter one source value; do not assume real data has negatives.
            rows[0]['reference']=str(float(rows[0]['reference'])+1)
    elif kind in ('wrong_integral','wrong_ratio'):
        name='graph_points.csv';fields,rows=table(output,name)
        if kind=='wrong_integral':rows[0]['integral_target_bq_min_per_ml']=str(float(rows[0]['integral_target_bq_min_per_ml'])+1)
        else:next(row for row in rows if row['ratio_status']=='ok')['target_over_reference']='999'
    elif kind in ('sparse_predictions','wrong_residual_sign','bool_frame'):
        name='fit_points.csv';fields,rows=table(output,name)
        if kind=='sparse_predictions':rows.pop()
        elif kind=='bool_frame':rows[0]['frame_index']='true'
        else:
            row=next(row for row in rows if row['residual_y_min'] and abs(float(row['residual_y_min']))>1e-5)
            row['residual_y_min']=str(-float(row['residual_y_min']))
    else:
        name='window_fits.csv';fields,rows=table(output,name)
        if kind=='clipped_slope':
            for row in rows:
                if row['fit_status']=='ok':row['logan_slope']='1'
        elif kind=='compensating_slopes':
            valid=[row for row in rows if row['fit_status']=='ok']
            first=valid[0];other=next(row for row in valid if (row['subject'],row['session'])!=(first['subject'],first['session']) and all(row[k]==first[k] for k in ('target','end_policy','start_min')))
            first['logan_slope']=str(float(first['logan_slope'])+.5);other['logan_slope']=str(float(other['logan_slope'])-.5)
        elif kind=='infinity_start':rows[0]['start_min']='Infinity'
        elif kind=='zero_undefined':next(row for row in rows if row['fit_status']!='ok')['logan_slope']='0'
        elif kind=='undefined_flag':next(row for row in rows if row['fit_status']!='ok')['fit_status']='ok'
        elif kind=='wrong_rank_threshold':
            row=next(row for row in rows if row['rank_threshold_min2']);row['rank_threshold_min2']=str(float(row['rank_threshold_min2'])*2)
        elif kind=='window_label_swap':rows[0]['end_policy']='invented'
        else:rows[0]['n_ratio']=str(int(rows[0]['n_ratio'])+1)
    write(output,name,fields,rows)
    with pytest.raises(AssertionError):q.validate_output_directory(output)

@pytest.mark.parametrize('kind',['extra_hash','wrong_hash','wrong_method','wrong_manifest','wrong_units','wrong_counts','missing_observed','empty_stack','pilot_status'])
def test_metadata_forgery(output,kind):
    def mutate(meta):
        if kind=='extra_hash':meta['source_sha256']['invented']='0'*64
        elif kind=='wrong_hash':meta['source_sha256'][next(iter(meta['source_sha256']))]='0'*64
        elif kind=='wrong_method':meta['method_contract']['ols']['minimum_graph_frames']=2
        elif kind=='wrong_manifest':meta['source_manifest_sha256']='0'*64
        elif kind=='wrong_units':meta['source_observed']['scans'][0]['analysis_time_unit']='s'
        elif kind=='wrong_counts':meta['source_observed']['scans'][0]['n_frames']+=1
        elif kind=='missing_observed':del meta['source_observed']['scans'][0]['native_end_s']
        elif kind=='empty_stack':meta['software_versions']={}
        else:meta['status']='resource_pilot'
    edit_json(output,'run_metadata.json',mutate)
    with pytest.raises(AssertionError):q.validate_output_directory(output)

@pytest.mark.parametrize('kind',['missing_pair','duplicate_group','one_scan_pair','group_count','constant_means','missing_null_pair','missing_null_group','four_subjects'])
def test_summary_support_and_aggregation(output,kind):
    def mutate(value):
        if kind=='missing_pair':value['paired_changes'].pop()
        elif kind=='duplicate_group':value['group_windows'].append(dict(value['group_windows'][0]))
        elif kind=='one_scan_pair':next(row for row in value['paired_changes'] if row['pair_status']=='incomplete_pair')['rescan_minus_baseline']=0
        elif kind=='group_count':value['group_windows'][0]['n_defined_scans']+=1
        elif kind=='constant_means':
            for row in value['group_windows']:
                if row['mean_logan_slope'] is not None:row['mean_logan_slope']=1.
        elif kind=='missing_null_pair':del next(row for row in value['paired_changes'] if row['rescan_minus_baseline'] is None)['rescan_minus_baseline']
        elif kind=='missing_null_group':del next(row for row in value['group_windows'] if row['mean_logan_slope'] is None)['mean_logan_slope']
        else:value['n_subjects']=4
    edit_json(output,'summary.json',mutate)
    with pytest.raises(AssertionError):q.validate_output_directory(output)

def test_empty_findings(output):
    (output/'findings.md').write_text('  ')
    with pytest.raises(AssertionError):q.validate_output_directory(output)
