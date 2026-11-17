#!/usr/bin/env python3
"""One admitted complete native EEG producer; no dispatch without guard approval.

All scientific reads and every output write are delegated to GuardContext.
The pure orchestration entry point accepts a generated guard context for tests.
Existence of projection files is not success: the final member receipt commits
all three streams and its annotation projection; the cohort receipt is last.
"""
from collections import Counter
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import types
import zipfile

HERE = Path(__file__).resolve().parent
# Independently reviewed guard component; authentic execution still requires
# the exact root-admitted producer protocol and its owned active native lease.
GUARDS_SHA256 = '3ab7bf7d4e13818be3812391b0482e19f7e544b1908c62b2cf743d60925109cb'
MAX_MODULE = 65536
MAX_REPORT = 262144
MAX_RECEIPT = 131072
MAX_LEDGER = 4194304
MAX_EVENT_STREAM = 8388608
MAX_EVENT_LINE = 262144
EXPECTED_STREAM_WIDTHS = {'time':8, 'eeg':16, 'quality':2}
STREAM_SUFFIXES = {'time':'time.i64le.provisional', 'eeg':'eeg.f64le.provisional', 'quality':'quality.u8.provisional'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def unique_json(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, 'duplicate saved JSON field')
            result[key] = value
        return result
    def finite_float(token):
        value=float(token)
        require(math.isfinite(value),'nonfinite saved JSON number')
        return value
    return json.loads(raw, object_pairs_hook=pairs,parse_float=finite_float,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite saved JSON')))


def bounded_json(value, cap):
    chunks=[]; size=1
    encoder=json.JSONEncoder(sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(',',':'))
    for fragment in encoder.iterencode(value):
        encoded=fragment.encode('utf-8'); size+=len(encoded)
        require(size<=cap, 'bounded serialized event/report ceiling')
        chunks.append(encoded)
    return b''.join(chunks)+b'\n'


def exact_integer(value, minimum=0, maximum=2**63-1):
    require(type(value) is int and minimum<=value<=maximum, 'integer source count outside admitted range')
    return value


def sha(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}',value), 'SHA256 syntax')
    return value


def execution_binding(ctx):
    p=ctx.protocol
    return {'protocol':{'path':str(ctx.args.protocol),'sha256':sha(ctx.args.protocol_sha256)},
            'producer':{'path':p['producer_path'],'sha256':sha(p['producer_sha256'])},
            'guards':{'path':p['guards_path'],'sha256':sha(p['guards_sha256'])},
            'modules':{key:{'path':p[key+'_path'],'sha256':sha(p[key+'_sha256'])}
                       for key in ('numeric_policy','numeric_stream','annotation_adapter','zip_guard')}}


def unique_map(rows, key, count):
    require(type(rows) is list and len(rows)==count, 'complete source population size')
    result={}
    for row in rows:
        ident=row[key]
        require(type(ident) is str and re.fullmatch('[1-9][0-9]*',ident) and ident not in result, 'unique decimal recording ID required')
        result[ident]=row
    return result


def read_inputs(ctx):
    """Read each cohort-level scientific artifact once through the saved meter."""
    p=ctx.protocol
    count=exact_integer(p['full_scope_recordings'],171,171)
    loaded={key:ctx.load_json(Path(p[key+'_path']),p[key+'_sha256'],1048576)
            for key in ('cohort','census_supervisor','inventory','headers','manifest')}
    cohort,supervisor,inventory,headers,manifest=(loaded[k] for k in ('cohort','census_supervisor','inventory','headers','manifest'))
    require(cohort['schema']=='dosei_complete_private_annotation_row_census_v1' and cohort['status']=='succeeded', 'complete saved annotation cohort required')
    require(supervisor['schema']=='dosei_annotation_census_supervisor_receipt_v1' and supervisor['status']=='succeeded', 'successful saved census supervisor required')
    require(supervisor['cohort_report']['path']==p['cohort_path'] and supervisor['cohort_report']['sha256']==p['cohort_sha256'], 'saved supervisor/cohort binding')
    require(supervisor['complete_member_recordings']==cohort['complete_source_recordings']==count, 'saved census is not complete')
    require(inventory['schema']=='dosei_range_directory_inventory_v1' and inventory['status']=='succeeded', 'original directory inventory required')
    require(headers['schema']=='dosei_native_header_inventory_v1' and headers['status']=='succeeded', 'original header inventory required')
    require(manifest['schema']=='dosei_annotation_census_manifest_v1' and manifest['full_scope_recordings']==count, 'complete source manifest required')
    require(cohort['archive_sha256']==inventory['archive_sha256_verified_during_acquisition']==headers['archive_sha256']==p['archive_sha256'], 'archive hash lineage differs')
    require(inventory['archive_path']==p['archive_path'], 'archive path lineage differs')
    require(headers['source_inventory_sha256']==manifest['source_inventory_sha256']==p['inventory_sha256'], 'inventory lineage differs')
    require(manifest['source_headers_sha256']==p['headers_sha256'] and cohort['manifest_sha256']==p['manifest_sha256'], 'header/manifest lineage differs')
    require(inventory['csv_count']==headers['csv_header_lines_read']==count, 'incomplete source headers/directory')
    expected_total=exact_integer(p['total_source_rows'],1)
    require(exact_integer(cohort['totals']['source_data_rows'],1)==expected_total, 'whole original row count differs')
    records=unique_map(cohort['recordings'],'recording_id',count)
    members=unique_map([x for x in inventory['members'] if not x['directory']],'study_id',count)
    observed_headers=unique_map(headers['header_recordings'],'recording_id',count)
    manifest_records=unique_map(manifest['members'],'recording_id',count)
    require(set(records)==set(members)==set(observed_headers)==set(manifest_records), 'complete source ID sets differ')
    order=[]
    for index,row in enumerate(manifest['members']):
        rid=row['recording_id']; source=members[rid]; summary=records[rid]; header=observed_headers[rid]
        require(type(row['index']) is int and row['index']==index, 'manifest order changed')
        require(row['member_path']==source['path']==summary['member_path']==header['path'], 'original member path join differs')
        require(row['expanded_bytes']==source['expanded_bytes']==summary['expanded_bytes_read'], 'source member expanded-size join')
        require(row['compressed_bytes']==source['compressed_bytes'] and row['member_crc32']==source['crc32_from_directory_only']==summary['member_crc32'], 'source compressed/CRC join')
        require(row['header_sha256']==summary['header_sha256']==header['header_sha256'], 'source header join')
        exact_integer(summary['source_data_rows'],1,4000000)
        exact_integer(summary['protected_annotation_rows'],0,50000)
        sha(summary['member_sha256'])
        order.append({'recording_id':rid,'directory_member':source,'summary':summary})
    require(sum(r['summary']['source_data_rows'] for r in order)==expected_total, 'per-member source-row denominator differs')
    require(sum(r['summary']['expanded_bytes_read'] for r in order)==cohort['totals']['expanded_bytes_read']==manifest['total_expanded_bytes'], 'per-member expanded-byte denominator differs')
    require(sum(r['summary']['protected_annotation_rows'] for r in order)==cohort['totals']['protected_annotation_rows'], 'per-member saved annotation denominator differs')
    return loaded,order


def read_member_saved(ctx, entry, cohort):
    """Exactly one read each of this member's saved receipt/report/JSONL ledger."""
    p=ctx.protocol; rid=entry['recording_id']; summary=entry['summary']; stem='recording-'+rid
    directory=Path(p['cohort_path']).parent
    receipt_binding=summary['final_member_receipt']; report_binding=summary['member_census_report']; ledger_binding=summary['annotation_ledger']
    require(receipt_binding['path']==str(directory/(stem+'.receipt.json')) and report_binding['path']==str(directory/(stem+'.census.json'))
            and ledger_binding['path']==str(directory/(stem+'.annotations.provisional.jsonl')), 'saved member paths outside exact census population')
    receipt=ctx.load_json(Path(receipt_binding['path']),sha(receipt_binding['sha256']),MAX_RECEIPT)
    report=ctx.load_json(Path(report_binding['path']),sha(report_binding['sha256']),MAX_REPORT)
    require(receipt['schema']=='dosei_annotation_census_member_receipt_v1' and report['schema']=='dosei_private_annotation_member_census_v1', 'saved member schema')
    require(receipt['status']==report['status']=='succeeded' and receipt['error'] is None, 'saved member is incomplete')
    require(receipt['recording_id']==report['recording_id']==rid and receipt['protocol_sha256']==report['protocol_sha256']==cohort['protocol_sha256'], 'saved census identity')
    require(receipt['archive_sha256']==report['archive_sha256']==p['archive_sha256'] and receipt['archive_path']==report['archive_path']==p['archive_path'], 'saved source archive identity')
    require(receipt['member_path']==report['member_path']==entry['directory_member']['path'], 'saved source member identity')
    require(receipt['member_census_report']==report_binding and receipt['annotation_ledger']==ledger_binding, 'saved final receipt does not bind report/ledger')
    require(ledger_binding['complete_and_bound_to_member_census'] is True and report['complete_member_EOF'] is True
            and report['complete_member_CRC_verified'] is True and report['source_member_release_authenticated'] is True, 'saved completion proof absent')
    for key,summary_key in (('source_data_rows','source_data_rows'),('expanded_bytes_read','expanded_bytes_read'),
                            ('member_sha256','member_sha256'),('member_crc32','member_crc32'),('header_sha256','header_sha256'),
                            ('protected_annotation_rows','protected_annotation_rows')):
        require(report[key]==summary[summary_key] and type(report[key]) is type(summary[summary_key]), 'saved source report differs from bound cohort')
    require(receipt['source_data_rows']==summary['source_data_rows'] and type(receipt['source_data_rows']) is int, 'saved source row count differs')
    ledger=ctx.load_bytes(Path(ledger_binding['path']),sha(ledger_binding['sha256_of_actual_retained_bytes']),MAX_LEDGER)
    require(len(ledger)==exact_integer(ledger_binding['bytes_successfully_written'],0,MAX_LEDGER), 'saved ledger byte count')
    require(not ledger or ledger.endswith(b'\n'), 'saved ledger has incomplete final JSONL line')
    rows=[]
    for line in ledger.splitlines(keepends=True):
        require(len(line)<=MAX_EVENT_LINE and line.endswith(b'\n'), 'saved annotation line ceiling')
        rows.append(unique_json(line))
        require(len(rows)<=50000, 'saved annotation row ceiling')
    require(len(rows)==summary['protected_annotation_rows'], 'complete saved annotation rows required')
    expected={'expanded_bytes':summary['expanded_bytes_read'],'source_rows':summary['source_data_rows'],
              'member_sha256':summary['member_sha256'],'header_sha256':summary['header_sha256'],
              'crc32':summary['member_crc32'],'annotation_rows':summary['protected_annotation_rows'],
              'clock_issue_counts':report['timestamp_audit']['issue_counts']}
    return expected,rows


def verify_directory(archive, bounds, inventory):
    infos=archive.infolist()
    require(archive.start_dir==bounds['offset'] and len(infos)==bounds['declared_members']==len(inventory['members']), 'authenticated ZIP directory shape changed')
    require(len({x.filename for x in infos})==len(infos), 'duplicate ZIP member names')
    require({x.filename for x in infos}=={x['path'] for x in inventory['members']}, 'ZIP directory population changed')
    for expected in inventory['members']:
        info=archive.getinfo(expected['path'])
        require(info.is_dir()==expected['directory'] and info.file_size==expected['expanded_bytes']
                and info.compress_size==expected['compressed_bytes'] and info.header_offset==expected['header_offset']
                and info.compress_type==expected['compression_method'] and info.flag_bits==expected['flag_bits']
                and f'{info.CRC:08x}'==expected['crc32_from_directory_only'], 'ZIP member metadata changed')


def exception_summary(problem):
    return {'type':type(problem).__name__,'message':str(problem)[:1000]}


def close_writers(writers):
    errors=[]
    for name,writer in writers.items():
        try:writer.close()
        except BaseException as exc:errors.append({'writer':name,**exception_summary(exc)})
    return errors


def checked_binding(writer, expected, *, bytes_expected=None):
    binding=writer.binding()
    require(type(binding) is dict and type(binding.get('bytes')) is int and binding['bytes']>=0, 'closed output binding shape')
    sha(binding['sha256'])
    signature=binding.get('closed_file_signature')
    require(type(signature) is dict and set(signature)=={'st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'}
            and all(type(value) is int for value in signature.values()) and signature['st_size']==binding['bytes'],
            'closed output stat signature must bind its exact byte count')
    if bytes_expected is not None:require(binding['bytes']==bytes_expected, 'closed output size differs from source shape')
    if expected is not None:require(binding['bytes']==expected['bytes'] and binding['sha256']==expected['sha256'], 'closed output binding differs from complete stream digest')
    return binding


def produce_member(ctx, entry, cohort, archive, modules):
    p=ctx.protocol; rid=entry['recording_id']; stem='recording-'+rid
    writers={}; stream_report=None; event_tally=Counter(); event_digest=hashlib.sha256(); event_bytes=0
    cleanup_errors=[]; failure_written=None
    try:
        with ctx.member_deadline():
            ctx.check_boundary()
            expected,rows=read_member_saved(ctx,entry,cohort)
            ctx.json(stem+'.start.json',{'schema':'dosei_full_eeg_member_start_v1','status':'started','recording_id':rid,
                        'execution_binding':execution_binding(ctx),
                        'source_member':entry['directory_member']['path'],'source_member_sha256':expected['member_sha256'],
                        'source_rows':expected['source_rows'],'source_annotation_rows':len(rows),
                        'native_run_id':p['native_run_id'],'transaction_commit_marker':stem+'.success.json'},8192)
            for key,width in EXPECTED_STREAM_WIDTHS.items():
                writers[key]=ctx.writer(stem+'.'+STREAM_SUFFIXES[key],expected['source_rows']*width,binary=True)
            writers['events']=ctx.writer(stem+'.annotation-events.jsonl.provisional',MAX_EVENT_STREAM,binary=False)
            for event in modules['annotation_adapter'].adapt_recording(rid,rows):
                encoded=bounded_json(event,MAX_EVENT_LINE)
                require(event_bytes+len(encoded)<=MAX_EVENT_STREAM,'private event projection ceiling')
                written=writers['events'].write(encoded)
                require(type(written) is int and written==len(encoded),'short/unknown private event write')
                event_digest.update(encoded);event_bytes+=written;event_tally['rows']+=1
                if event['moaas_grouped_ordinal'] is not None:event_tally['source_supported_moaas_targets']+=1
                if event['soc_transition_state'] is not None:event_tally['source_supported_soc_transition_targets']+=1
                event_tally[event['marker_kind']]+=1
                require(event['canonical_scoring_admitted'] is False and event['biological_person_id'] is None,'adapter changed scientific scope')
            require(event_tally['rows']==expected['annotation_rows'],'adapter did not preserve complete saved annotation population')
            info=archive.getinfo(entry['directory_member']['path'])
            with archive.open(info,'r') as source:
                stream_report=modules['numeric_stream'].project_member(source,expected=expected,annotation_rows=iter(rows),
                    sinks={key:writers[key] for key in EXPECTED_STREAM_WIDTHS},block_rows=65536)
            require(stream_report['complete_EOF'] is True and stream_report['source_rows']==expected['source_rows']
                    and stream_report['expanded_bytes']==expected['expanded_bytes']
                    and stream_report['member_sha256']==expected['member_sha256']
                    and stream_report['member_crc32']==expected['crc32']
                    and stream_report['annotation_rows_joined']==expected['annotation_rows'], 'complete numeric core source proof differs')
            require(stream_report['source_rows_repaired_dropped_or_interpolated']==0 and stream_report['canonical_scoring_admitted'] is False,'numeric core changed scientific scope')
            require(len(stream_report['quality_combination_counts_by_channel'])==2,'exactly two channel quality counts required')
            for counts in stream_report['quality_combination_counts_by_channel']:
                require(all(type(state) is int and state in modules['numeric_policy'].ALLOWED_STATUSES
                            and type(n) is int and n>0 for state,n in counts.items())
                        and sum(counts.values())==expected['source_rows'],'quality states do not cover every source row')
            cleanup_errors=close_writers(writers)
            require(not cleanup_errors,'projection close/fsync/stat failure')
            bindings={key:checked_binding(writers[key],stream_report['outputs'][key],bytes_expected=expected['source_rows']*width)
                      for key,width in EXPECTED_STREAM_WIDTHS.items()}
            event_binding=checked_binding(writers['events'],{'bytes':event_bytes,'sha256':event_digest.hexdigest()})
            member={'schema':'dosei_full_eeg_member_success_v1','status':'succeeded','recording_id':rid,
                    'execution_binding':execution_binding(ctx),
                    'native_run_id':p['native_run_id'],'source_release':p.get('source_release','zenodo:22145442/v2'),
                    'archive_sha256':p['archive_sha256'],'source_member':entry['directory_member']['path'],
                    'source_member_sha256':expected['member_sha256'],'source_header_sha256':expected['header_sha256'],
                    'source_rows':expected['source_rows'],'source_expanded_bytes':expected['expanded_bytes'],
                    'source_crc32':expected['crc32'],'complete_source_EOF_CRC_SHA':True,
                    'saved_annotation_ledger':entry['summary']['annotation_ledger'],
                    'saved_member_report':entry['summary']['member_census_report'],
                    'saved_final_member_receipt':entry['summary']['final_member_receipt'],
                    'all_three_streams_closed_and_size_stat_checked':True,'outputs':bindings,
                    'event_projection':event_binding,'event_projection_counts':dict(event_tally),
                    'numeric_core_report':stream_report,
                    'output_hash_scope':'exact successful writes compared with core digests and closed-file size/stat; no independent post-exit rehash claimed',
                    'canonical_scoring_admitted':False,'biological_person_mapping_verified':False,
                    'native_marker_relative_packets_constructed':False}
            # The only successful transaction marker, written after all four files.
            receipt=ctx.json(stem+'.success.json',member,MAX_RECEIPT)
            return {'recording_id':rid,'receipt':receipt,'source_rows':expected['source_rows'],
                    'expanded_bytes':expected['expanded_bytes'],'annotation_rows':expected['annotation_rows'],
                    'event_projection_counts':dict(event_tally),'clock_issue_counts':stream_report['clock_issue_counts'],
                    'quality_counts':stream_report['quality_combination_counts_by_channel'],
                    'binary_bytes':sum(b['bytes'] for b in bindings.values()),'event_bytes':event_bytes}
    except BaseException as problem:
        more=close_writers(writers)
        try:
            failure_written=ctx.json(stem+'.failure.json',{'schema':'dosei_full_eeg_member_failure_v1','status':'incomplete',
                'execution_binding':execution_binding(ctx),
                'recording_id':rid,'native_run_id':p['native_run_id'],'error':exception_summary(problem),
                'close_errors':cleanup_errors+more,'files_left_in_place':True,'projection_files_are_not_success_markers':True,
                'event_bytes_confirmed_written_before_error':event_bytes,'event_rows_confirmed_written_before_error':event_tally.get('rows',0),
                'complete_numeric_core_report_observed':stream_report is not None,
                'resource_observation_before_this_receipt':ctx.resources(),'canonical_scoring_admitted':False},MAX_RECEIPT,critical=True)
        except BaseException:
            pass  # Native run/guard start, retained partials and launcher preserve failure evidence.
        raise


def produce(ctx):
    """Complete finite orchestration. Tests inject generated GuardContext doubles."""
    p=ctx.protocol; completed=[]; failing_recording=None; inputs=None
    modules={}; totals=Counter();clock=Counter();quality=[Counter(),Counter()];event_counts=Counter()
    try:
        ctx.check_boundary()
        for key,name in (('numeric_policy','numeric_policy'),('numeric_stream','numeric_stream'),
                         ('annotation_adapter','annotation_events'),('zip_guard','inventory_guard')):
            modules[key]=ctx.load_module(Path(p[key+'_path']),p[key+'_sha256'],name)
        inputs,order=read_inputs(ctx)
        ctx.json('COHORT_START.json',{'schema':'dosei_full_eeg_cohort_start_v1','status':'started',
                 'execution_binding':execution_binding(ctx),
                 'native_run_id':p['native_run_id'],'required_recordings':p['full_scope_recordings'],
                 'expected_source_rows':p['total_source_rows'],'expected_binary_bytes':26*p['total_source_rows'],
                 'archive_sha256':p['archive_sha256'],'saved_cohort_sha256':p['cohort_sha256'],
                 'source_manifest_sha256':p['manifest_sha256'],'one_archive_handle':True,'automatic_retries':0,
                 'final_transaction_marker':'COHORT_SUCCESS.json','canonical_scoring_admitted':False},16384)
        # Guard authenticates the whole original archive before yielding this one
        # metered source descriptor; neither ZipFile nor producer opens a path.
        with ctx.open_archive() as source:
            bounds=modules['zip_guard'].directory_bounds(source)
            with zipfile.ZipFile(source,'r') as archive:
                verify_directory(archive,bounds,inputs['inventory'])
                for entry in order:
                    failing_recording=entry['recording_id'];ctx.check_boundary()
                    member=produce_member(ctx,entry,inputs['cohort'],archive,modules)
                    completed.append({'recording_id':member['recording_id'],'receipt':member['receipt']})
                    for key in ('source_rows','expanded_bytes','annotation_rows','binary_bytes','event_bytes'):totals[key]+=member[key]
                    clock.update(member['clock_issue_counts']);event_counts.update(member['event_projection_counts'])
                    for index in range(2):quality[index].update(member['quality_counts'][index])
                    print(json.dumps({'status':'member_finalized','completed_recordings':len(completed),
                                      'required_recordings':p['full_scope_recordings'],'recording_id':failing_recording}),flush=True)
        # Source descriptor identity/closure checks have completed before success.
        failing_recording=None;ctx.check_boundary()
        require(len(completed)==p['full_scope_recordings'] and len({r['recording_id'] for r in completed})==len(completed),'complete cohort final receipts required')
        require(totals['source_rows']==p['total_source_rows'] and totals['binary_bytes']==26*p['total_source_rows'],'whole 26-byte row projection denominator differs')
        require(totals['expanded_bytes']==inputs['cohort']['totals']['expanded_bytes_read']
                and totals['annotation_rows']==inputs['cohort']['totals']['protected_annotation_rows'],'whole source/annotation census differs')
        require(dict(clock)==inputs['cohort']['timestamp_issue_counts'],'whole source clock anomaly census differs')
        require(event_counts['rows']==totals['annotation_rows'] and all(sum(q.values())==totals['source_rows'] for q in quality),'whole source event/quality accounting differs')
        receipt=ctx.json('COHORT_SUCCESS.json',{'schema':'dosei_complete_full_eeg_preparation_v1','status':'succeeded',
                'execution_binding':execution_binding(ctx),
                'saved_scientific_inputs':{key:{'path':p[key+'_path'],'sha256':p[key+'_sha256']}
                                          for key in ('cohort','census_supervisor','inventory','headers','manifest')},
                'native_run_id':p['native_run_id'],'source_release':p.get('source_release','zenodo:22145442/v2'),
                'archive_sha256':p['archive_sha256'],'census_cohort_sha256':p['cohort_sha256'],
                'source_manifest_sha256':p['manifest_sha256'],'complete_source_recordings':len(completed),
                'complete_member_receipts':completed,'totals':dict(totals),'quality_combination_counts_by_channel':[dict(q) for q in quality],
                'clock_issue_counts':dict(clock),'event_projection_counts':dict(event_counts),
                'one_source_handle_full_authentication_and_one_numeric_pass':True,'all_source_rows_retained':True,
                'private_complete_numeric_representation':True,'independent_saved_projection_rehash_completed':False,
                'resource_observation_before_this_receipt':ctx.resources(),
                'native_marker_relative_packets_constructed':False,'biological_person_mapping_verified':False,
                'canonical_scoring_admitted':False,'model_or_scoring_execution':False},MAX_RECEIPT,critical=True)
        print(json.dumps({'status':'succeeded','recordings':len(completed),'source_rows':totals['source_rows'],
                          'receipt':receipt,'resources_after_final_receipt':ctx.resources()}),flush=True)
        return receipt
    except BaseException as problem:
        failure=None
        try:
            failure=ctx.json('COHORT_FAILURE.json',{'schema':'dosei_full_eeg_cohort_failure_v1','status':'incomplete',
                    'execution_binding':execution_binding(ctx),
                    'native_run_id':p.get('native_run_id'),'error':exception_summary(problem),'failed_or_held_recording_id':failing_recording,
                    'completed_member_receipts':completed,'completed_source_totals':dict(totals),'required_recordings':p.get('full_scope_recordings'),
                    'all_retained_files_left_in_place':True,'automatic_retries':0,
                    'resource_observation_before_this_receipt':ctx.resources(),'canonical_scoring_admitted':False},MAX_RECEIPT,critical=True)
        except BaseException:pass
        print(json.dumps({'status':'incomplete','error_type':type(problem).__name__,'completed_recordings':len(completed),'failure_receipt':failure}),flush=True)
        raise


def bootstrap_guards(args):
    """The sole direct file read is pinned sibling operational source code."""
    require(re.fullmatch('[0-9a-f]{64}',GUARDS_SHA256),'producer guard pin is not frozen')
    path=HERE/'eeg_guards.py'
    require(path.parent.resolve()==path.parent,'guard source parent changed')
    fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK|getattr(os,'O_NOFOLLOW',0))
    with os.fdopen(fd,'rb') as source:
        before=os.fstat(source.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size<=MAX_MODULE,'guard source type/size')
        raw=source.read(MAX_MODULE+1)
        fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')
        signature=lambda s:tuple(getattr(s,k) for k in fields)
        require(len(raw)<=MAX_MODULE and signature(before)==signature(os.fstat(source.fileno()))==signature(path.lstat()),'guard source changed')
    require(hashlib.sha256(raw).hexdigest()==GUARDS_SHA256,'guard source pin differs')
    args.bootstrap_operational_read_bytes=len(raw)
    module=types.ModuleType('dosei_eeg_guards');module.__file__=str(path)
    sys.modules[module.__name__]=module
    exec(compile(raw,str(path),'exec'),module.__dict__)
    return module


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol',type=Path,required=True)
    parser.add_argument('--protocol-sha256',required=True)
    parser.add_argument('--approval-id',required=True)
    parser.add_argument('--native-run-id',required=True)
    args=parser.parse_args();args.protocol=args.protocol.absolute()
    ctx=None
    try:
        guards=bootstrap_guards(args)
        ctx=guards.GuardContext(args)
        produce(ctx)
        return 0
    except BaseException as problem:
        print(json.dumps({'status':'producer_failed','error_type':type(problem).__name__}),flush=True)
        return 1
    finally:
        if ctx is not None:ctx.close()


if __name__=='__main__':raise SystemExit(main())
