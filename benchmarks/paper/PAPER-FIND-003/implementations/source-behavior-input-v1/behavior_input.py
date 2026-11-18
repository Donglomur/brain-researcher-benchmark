"""Construct original behavioral-R input and an offline layout descriptor.

No fit, subprocess, source execution, MATLAB reduction or scientific decision.
The CSV is canonical interchange, not historical writetable/read.table parity.
"""
from __future__ import annotations
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath

VALIDATOR_SHA256 = 'd7b5af7656de468acc4d4d98096423870c8d3dba4e4242afe376a8b9ff6d2555'
VALIDATOR_BYTES = 10613
SOURCE_SHA256 = 'cdd9da7e359448cc54ccbb3ce1ec9da434296d6d37d441d4fb92eab38183abf7'
SOURCE_BYTES = 1390
SOURCE_REF = 'f143b0b7dca77bf9b09d5c7f39352fc5332c83c0'
SOURCE_PATH = 'ripple/R_scripts/LearnR_predict_performance.R'
MAX_CSV_BYTES = 64 * 1024 * 1024


class BehaviorInputError(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise BehaviorInputError(message)


def _validator():
    path = Path(__file__).resolve().parent.parent / 'source-subject-export-v1' / 'validate_export.py'
    with path.open('rb') as stream:
        body = stream.read(VALIDATOR_BYTES + 1)
    need(len(body) == VALIDATOR_BYTES and hashlib.sha256(body).hexdigest() == VALIDATOR_SHA256,
         'exact accepted sibling subject-export validator required')
    spec = importlib.util.spec_from_file_location('find003_native_subject_validator', path)
    module = importlib.util.module_from_spec(spec)
    # Execute the verified bytes, not a later second file read.
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


def _absolute_posix(value, label):
    need(type(value) is str and 0 < len(value) <= 4096 and value.startswith('/') and
         not value.startswith('//') and '\\' not in value and
         not any(c in value for c in ('\x00', '\r', '\n')), label + ': explicit absolute POSIX path')
    need(not any(part in ('.', '..', '') for part in value.split('/')[1:]),
         label + ': canonical path components')
    return PurePosixPath(value)


def check_source_file(path):
    """Future caller check of source code only; never load R or scientific data."""
    with Path(path).open('rb') as stream:
        body = stream.read(SOURCE_BYTES + 1)
    need(len(body) == SOURCE_BYTES and hashlib.sha256(body).hexdigest() == SOURCE_SHA256,
         'exact original behavioral R source required')
    return {'bytes': len(body), 'sha256': SOURCE_SHA256, 'source_executed': False}


def describe_layout(*, initial_cwd, rscript_executable, source_file):
    """Describe source-derived paths for an explicitly declared initial getwd.

    This does not establish how the unacquired RUN_R_Script sets its working
    directory. argv is data only; there is intentionally no executor here.
    """
    cwd = _absolute_posix(initial_cwd, 'initial working directory')
    exe = _absolute_posix(rscript_executable, 'Rscript executable')
    script = _absolute_posix(source_file, 'original source file')
    results = cwd.parent / 'Results'
    output = results / 'LearnR_predict_infer'
    models = []
    for phase in ('stimulus', 'feedback', 'interval'):
        for outcome in ('eleMemory_perf', 'eleInfer_perf'):
            models.append({'ordinal': len(models)+1, 'formula': outcome+'~'+phase,
                           'data': 'D', 'function': 'lmrob', 'setting': 'KS2014'})
    return {'schema': 'ripple-original-behavior-layout/v1', 'declared_platform': 'POSIX',
            'initial_cwd': str(cwd), 'argv': [str(exe), str(script)],
            'source': {'revision': SOURCE_REF, 'repository_path': SOURCE_PATH,
                       'bytes': SOURCE_BYTES, 'sha256': SOURCE_SHA256},
            'results_directory': str(results),
            'input_csv': str(results / 'dt_sublevel_LearnR_behav.csv'),
            'output_directory': str(output),
            'output_csv': str(output / 'learnR_predict_feature_performance.csv'),
            'models_in_source_order': models,
            'source_postprocessing': [
                'rbind summary(model)$coefficients in the six-call order',
                'H <- ifelse(cef[,4]<0.05,"Sig","")',
                'cef <- cbind(cef,H); native character coercion is preserved',
                'out <- subset(cef, rownames(cef) != "(Intercept)")',
                'write.csv(out,"learnR_predict_feature_performance.csv") with original defaults'],
            'source_transforms_added': [], 'source_default_overrides_added': [],
            'source_file_check_performed': False,
            'execution_status': 'not_executed',
            'original_helper_cwd_qualified': False,
            'native_R_reader_and_fit_qualified': False,
            'required_before_execution': [
                'Verify source_file bytes with check_source_file; source path alone proves nothing.',
                'Provide and qualify R/robustbase runtime and explicitly select the initial working directory.',
                'Resolve original RUN_R_Script behavior before claiming original invocation reproduction.',
                'Qualify native CSV parsing/types/missing values and original input/support provenance.']}


def _numeric(value, validator):
    state = validator.scalar(value)
    if state[0] == 'finite':
        return repr(state[1])
    return {'nan': 'NaN', 'positive_infinity': 'Inf', 'negative_infinity': '-Inf'}[state[0]]


class _BoundedCSV(io.StringIO):
    def __init__(self):
        super().__init__(newline=''); self.byte_count = 0
    def write(self, value):
        self.byte_count += len(value.encode('utf8'))
        need(self.byte_count <= MAX_CSV_BYTES, 'complete CSV exceeds adapter limit; no partial output returned')
        return super().write(value)


def build_input(packet, *, initial_cwd, rscript_executable, source_file):
    """Return (canonical_csv_bytes, manifest) without writing or running anything.

    All joined rows, selected native GroupCount and native column order survive.
    NaN/Inf rows remain; R's original missingness/runtime behavior is not replaced.
    """
    validator = _validator()
    try:
        support = validator.validate_packet(packet)
    except ValueError as exc:
        raise BehaviorInputError('invalid original subject-stage export: ' + str(exc)) from exc
    layout = describe_layout(initial_cwd=initial_cwd, rscript_executable=rscript_executable,
                             source_file=source_file)
    columns = list(packet['native_tables']['joined']['columns'])
    output = _BoundedCSV()
    # Quoting every field protects identities containing # and apostrophes from
    # the intended reader's comment/quote rules. Native compatibility is unrun.
    writer = csv.writer(output, quoting=csv.QUOTE_ALL, lineterminator='\n')
    writer.writerow(columns)
    rows = packet['joined']
    for row in rows:
        selected = packet['subjects'][row['subject_row_id'] - 1]
        fields = {'subject': row['subject'], 'GroupCount': str(selected['group_count']),
                  'eleInfer_perf': _numeric(row['inference'], validator),
                  'eleMemory_perf': _numeric(row['memory'], validator)}
        fields.update({phase: _numeric(row['values'][phase], validator)
                       for phase in ('stimulus', 'feedback', 'interval')})
        writer.writerow([fields[name] for name in columns])
    body = output.getvalue().encode('utf8')
    representation = json.dumps(packet, sort_keys=True, separators=(',', ':'),
                                ensure_ascii=False, allow_nan=False).encode('utf8')
    manifest = {'schema': 'ripple-original-behavior-input/v1', 'layout': layout,
                'csv': {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
                        'columns': columns, 'rows': len(rows), 'encoding': 'UTF-8',
                        'line_ending': 'LF', 'quoting': 'all_fields',
                        'row_name_index_included': False,
                        'historical_matlab_csv_byte_identity': False,
                        'native_R_read_table_parity': 'unqualified'},
                'input_packet_representation_sha256': hashlib.sha256(representation).hexdigest(),
                'subject_rows': [{'csv_data_row': n, 'subject': row['subject'],
                                 'native_subject_row_id': row['subject_row_id'],
                                 'native_joined_row_id': row['row_id']}
                                for n, row in enumerate(rows, 1)],
                'native_joined_row_names': list(packet['native_tables']['joined']['row_names']),
                'upstream_support': support,
                'interpretation': 'Canonical source-input transport only; no row filtering, scaling, imputation, fit or score.',
                'reproduction_qualified': False, 'same_task_improvement_qualified': False}
    return body, manifest
