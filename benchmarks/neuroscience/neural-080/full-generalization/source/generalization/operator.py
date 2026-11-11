"""Trusted full-input preparation and complete programme orchestration.

No method executes at import. Operators must supply genuine inputs and a
separately qualified native host; this module creates no admission or freshness
credential. All public historical cases remain developmental crossvalidation.
"""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
import hashlib
import time
from .source_map import need, load_source_map, descriptor
from .provenance import document, load_graph, join_media_graph, preprocessing
from .splits import (EvidenceDescriptor, DonorIdentity, VideoProvenance, DuplicateEdge,
                     ProvenanceGraph, build_family_plan, assignment_document, outer_cases)


def restore_plan(value):
    need(type(value) is dict and value.get('schema') == 'neural080_family_assignment_v1', 'complete captured family assignment')
    g = value['source_graph']
    ev = lambda rows: tuple(EvidenceDescriptor(**r) for r in rows)
    graph = ProvenanceGraph(g['provider_identity'],g['source_version'],ev(g['evidence']),
        tuple(VideoProvenance(v['video_id'],tuple(DonorIdentity(**d) for d in v['donor_identities']),ev(v['evidence'])) for v in g['videos']),
        tuple(DuplicateEdge(e['left_video_id'],e['right_video_id'],ev(e['evidence'])) for e in g['duplicate_edges']))
    plan = build_family_plan(graph)
    from .source_map import canonical
    need(canonical(assignment_document(plan)) == canonical(value), 'complete deterministic assignment recompiled from supplied source graph')
    return plan


def _prefix(row, prefix):
    return dict(row, path=prefix+'/'+row['path'])


def _existing_writer(path, owner):
    """Only for the empty output directory created by our subprocess owner.

    Individual accepted Writer.put operations remain no-replace and raw-first.
    This does not attach to an existing scientific run or reuse old artifacts.
    """
    from input_owner import Writer
    p=Path(path)
    need(p.is_dir() and not p.is_symlink() and not any(p.iterdir()), 'fresh empty isolated output directory')
    w=Writer.__new__(Writer);w.root=p;w.owner=owner;w.files=[]
    return w


def project_feature_metadata(source_root, rows, output, owner):
    """Create an exact four-body public metadata tree, preserving raw paths.

    The original preparation metadata root also contains private recording/join
    roles and is never mounted in a candidate. Captured raw map bytes keep their
    original relative references; this projection does not rewrite those bytes.
    """
    from input_owner import Writer, capture
    from pathlib import PurePosixPath
    record=owner.begin('project_exact_feature_metadata_tree');answer=None
    try:
        need(len(rows)==4 and len({r['path'] for r in rows})==4,'exact distinct map andthree evidence bodies')
        writers={'':Writer(output,owner)}
        for row in rows:
            descriptor(row,cap=16_777_216)
            parts=PurePosixPath(row['path']).parts
            for level in range(1,len(parts)):
                relative='/'.join(parts[:level])
                if relative not in writers:
                    writers[relative]=Writer(Path(output)/relative,owner)
            parent='/'.join(parts[:-1])
            body=capture(source_root,row,owner,max_bytes=16_777_216)
            observed=writers[parent].put(parts[-1],body)
            need(observed['bytes']==row['bytes'] and observed['sha256']==row['sha256'],'projection preserves exact raw metadata bodies')
        answer=str(Path(output))
    except BaseException as exc:
        owner.failure(record,exc)
    owner.complete(record);return answer


def prepare(config_root, config_descriptor, roots, output, owner):
    """Actual full source-map, graph, clocks,96-recording and feature production.

    roots has exactly metadata, recordings, media, logs, checkpoint. They are
    provided explicitly by an operator; no discovery or network acquisition.
    The phase retains partial fresh outputs if any downstream gate refuses.
    """
    from input_owner import Writer, capture
    from .recordings import prepare_unscaled
    from .clocks import produce as clocks
    from .features import produce as features, FeatureLimits
    started_wall=time.monotonic_ns();started_cpu=time.process_time_ns();before=dict(owner.used)
    rec=owner.begin('complete_generalization_preparation');answer=None
    try:
        need(type(roots) is dict and set(roots)=={'metadata','recordings','media','logs','checkpoint'},'all explicit original input roots')
        c=document(config_root,config_descriptor,owner)
        need(type(c) is dict and set(c)=={'schema','backend','source_map','provenance_graph','joined_metadata','recordings','preprocessing','behavior_logs','checkpoint','feature_limits','stream'},'closed full preparation selection')
        need(c['schema']=='neural080_generalization_preparation_v1','full source preparation schema')
        need(c['backend'] in ('full_svd_materialized','streamed_dual_certified'),'explicit selected algebra/storage backend')
        writer=Writer(output,owner)
        plan, graph_evidence=load_graph(roots['metadata'],c['provenance_graph'],owner)
        source_map=load_source_map(roots['metadata'],c['source_map'],tuple(range(1,1103)),owner)
        media_document=document(roots['metadata'],c['source_map'],owner)
        need(media_document['evidence']['provenance_graph']==c['provenance_graph'],'source map and split graph exact original descriptor')
        join_media_graph(source_map,plan)
        joined=document(roots['metadata'],c['joined_metadata'],owner,12_000_000)
        roster=document(roots['metadata'],c['recordings'],owner,100_000)
        processing=preprocessing(roots['metadata'],c['preprocessing'],joined,roster,owner)
        logs=document(roots['metadata'],c['behavior_logs'],owner,4_000_000)
        assignment=writer.document('FAMILY_ASSIGNMENT.json',assignment_document(plan))
        clock_result=clocks(roots['logs'],logs,source_map,joined,owner,writer.root/'clocks')
        pool_result=prepare_unscaled(roots['metadata'],roots['recordings'],c['joined_metadata'],c['recordings'],writer.root/'pool',owner)
        # Final pool publication adds exact units/reference/provenance without
        # replacing the unchanged preparer's original manifest or source arrays.
        pool_writer=Writer.__new__(Writer);pool_writer.root=writer.root/'pool';pool_writer.owner=owner;pool_writer.files=[]
        original_processing=capture(roots['metadata'],c['preprocessing'],owner,max_bytes=16_777_216)
        processing_descriptor=pool_writer.put('PREPROCESSING.json',original_processing)
        target_contract={'schema':'neural080_target_basis_v1','channel_names':processing['channel_names'],
             'eeg_reference':processing['reference'],'eeg_units':processing['eeg_unit'],
             'source_clock':processing['clock'],'preprocessing_profile':processing['profile'],
             'preprocessing_evidence':[processing_descriptor]}
        contract=pool_writer.document('TARGET_CONTRACT.json',target_contract)
        pool=dict(pool_result['pool'],target_contract=contract)
        pool_descriptor=pool_writer.document('GENERALIZATION_POOL.json',pool)
        feature_descriptor=None;stream_descriptor=None
        if c['backend']=='full_svd_materialized':
            need(c['stream'] is None,'materialized backend has no implicit streamed operands')
            feature_result=features(roots['media'],source_map,roots['checkpoint'],c['checkpoint'],writer.root/'features',owner,FeatureLimits(**c['feature_limits']))
            feature_descriptor=feature_result['manifest']
        else:
            from .feature_stream import parse_stream_spec
            stream=c['stream']
            need(type(stream) is dict and stream['metadata_root']==str(roots['metadata']) and
                 stream['source_map_descriptor']==c['source_map'] and stream['media_root']==str(roots['media']) and
                 stream['checkpoint_root']==str(roots['checkpoint']) and stream['checkpoint']==c['checkpoint'] and
                 stream['limits']==c['feature_limits'],'streamed backend uses exact same full admitted source operands')
            parse_stream_spec(stream,owner)
            projected=project_feature_metadata(roots['metadata'],[c['source_map'],*media_document['evidence'].values()],writer.root/'feature-metadata',owner)
            stream=dict(stream,metadata_root=projected)
            parse_stream_spec(stream,owner)
            stream_descriptor=writer.document('STREAM_INPUT.json',stream)
        answer={'schema':'neural080_prepared_generalization_v1','selection':config_descriptor,
          'assignment':assignment,'assignment_sha256':plan.assignment_sha256,
          'source_map':c['source_map'],'graph':c['provenance_graph'],'captured_graph_evidence':graph_evidence,
          'clocks':_prefix(clock_result['manifest'],'clocks'),
          'pool':_prefix(pool_descriptor,'pool'),'features':_prefix(feature_descriptor,'features') if feature_descriptor else None,
          'backend':c['backend'],'stream':stream_descriptor,
          'pool_root':'pool','feature_root':'features','target_units':'original_eeg',
          'source_status':'complete prospective source operands only; actual preparation result is not qualification',
          'evaluation_exposure':'public historical1102/sixpeople; development only',
          'preprocessing_profile':processing['profile'],
          'native_and_rights_qualification':'separate real empirical gate, not issued by this document',
          'common_preparation_cost':{'process_cpu_ns':time.process_time_ns()-started_cpu,
            'monotonic_ns':time.monotonic_ns()-started_wall,
            'logical_delta':{k:owner.used[k]-before[k] for k in before},
            'scope':'All actual source-map,graph,clock,recordingpool and selectedfeature preparation through before PREPARED manifest serialization; shared across all30cases and allconditions; sameOwner also charges finalpublication',
            'native_aggregate_cost':'not measured by these logical/process observations; independenthost counter qualification required'}}
        result_descriptor=writer.document('PREPARED.json',answer)
        answer={'manifest':result_descriptor,'prepared':answer,'output':str(writer.root)}
    except BaseException as exc:
        owner.failure(rec,exc)
    owner.complete(rec);return answer


def bind_prepared(root, row, owner):
    p=document(root,row,owner)
    need(p.get('schema')=='neural080_prepared_generalization_v1','actual complete prepared source panel')
    plan=restore_plan(document(root,p['assignment'],owner))
    need(p['assignment_sha256']==plan.assignment_sha256 and p['target_units']=='original_eeg','exact assignment and original target units')
    # Top-level descriptors carry subdirectory prefixes. Child readers see the
    # same exact bodies using filenames relative to their own explicit roots.
    def child(r,prefix):
        descriptor(r,cap=2**63-1)
        need(r['path'].startswith(prefix+'/') and '/' not in r['path'][len(prefix)+1:],'single selected prepared manifest')
        return dict(r,path=r['path'][len(prefix)+1:])
    need(p['pool_root']=='pool' and p['feature_root']=='features','fixed complete operand roles')
    need(p.get('backend') in ('full_svd_materialized','streamed_dual_certified'),'explicit captured backend')
    if p['backend']=='streamed_dual_certified':
        need(p['features'] is None and p.get('stream') is not None,'streamed preparation has no hidden fullfeature materialization')
        feature=None
    else:
        need(p.get('stream') is None,'materialized preparation has no hidden stream')
        feature=child(p['features'],'features')
    return p,plan,child(p['pool'],'pool'),feature
