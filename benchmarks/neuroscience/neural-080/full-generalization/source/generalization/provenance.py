"""Capture actual ordinary provenance operands; hashes never issue authority."""
from __future__ import annotations
from dataclasses import asdict
from .source_map import need, descriptor
from .splits import (DonorIdentity, EvidenceDescriptor, VideoProvenance,
                     DuplicateEdge, ProvenanceGraph, build_family_plan)


def document(root, row, owner, maximum=16_777_216):
    from input_owner import capture
    from io_contract import decode
    return decode(capture(root, descriptor(row, cap=maximum), owner, max_bytes=maximum))


def load_graph(root, row, owner):
    """Compile complete provider source-item/duplicate graph, opening evidence.

    Evidence is ordinary source/provenance material already selected by an
    operator. Its contents are retained by exact identity; this does not attest
    completeness, ownership, duplicate discovery or the provider's truthfulness.
    An independent source review must establish those empirical properties.
    """
    from input_owner import capture
    rec = owner.begin('capture_complete_provenance_graph')
    answer = None
    try:
        value = document(root, row, owner)
        need(type(value) is dict and set(value) == {'schema', 'provider_identity', 'source_version', 'evidence', 'videos', 'duplicate_edges'}, 'complete provenance graph schema')
        need(value['schema'] == 'neural080_provenance_graph_v1', 'source graph version')
        def evidence(rows):
            need(type(rows) is list and rows, 'nonempty observed provenance evidence')
            return tuple(EvidenceDescriptor(**descriptor(r, cap=16_777_216)) for r in rows)
        videos = []
        for v in value['videos']:
            need(type(v) is dict and set(v) == {'video_id', 'donor_identities', 'evidence'}, 'closed provenance video')
            donors = []
            for d in v['donor_identities']:
                need(type(d) is dict and set(d) == {'namespace', 'identity'}, 'actual donor namespace and identity')
                donors.append(DonorIdentity(**d))
            videos.append(VideoProvenance(v['video_id'], tuple(donors), evidence(v['evidence'])))
        edges = []
        for e in value['duplicate_edges']:
            need(type(e) is dict and set(e) == {'left_video_id', 'right_video_id', 'evidence'}, 'closed duplicate edge')
            edges.append(DuplicateEdge(e['left_video_id'], e['right_video_id'], evidence(e['evidence'])))
        graph = ProvenanceGraph(value['provider_identity'], value['source_version'], evidence(value['evidence']), tuple(videos), tuple(edges))
        plan = build_family_plan(graph)
        selected = set(graph.evidence)
        for v in graph.videos: selected.update(v.evidence)
        for e in graph.duplicate_edges: selected.update(e.evidence)
        observations = []
        for e in sorted(selected, key=lambda d: (d.path, d.sha256)):
            capture(root, asdict(e), owner, max_bytes=16_777_216)
            observations.append(asdict(e))
        answer = plan, observations
    except BaseException as exc:
        owner.failure(rec, exc)
    owner.complete(rec)
    return answer


def join_media_graph(source_map, plan):
    need(tuple(r.video_id for r in source_map.roles) == tuple(v.video_id for v in plan.source_graph.videos), 'complete graph-media order')
    components = {v:c.component_sha256 for c in plan.components for v in c.video_ids}
    duplicate_bytes = {}
    for media, video in zip(source_map.roles, plan.source_graph.videos, strict=True):
        need((media.provenance_namespace,media.provenance_identity) in {(d.namespace,d.identity) for d in video.donor_identities}, 'complete media donor key must occur in actual family graph')
        if media.source_sha256 in duplicate_bytes:
            need(components[video.video_id] == components[duplicate_bytes[media.source_sha256]], 'byte-identical media must belong to one provenance/duplicate component')
        duplicate_bytes[media.source_sha256] = video.video_id


def preprocessing(root, row, joined, recording_roster, owner):
    """Require explicit source units, common reference and known fit history.

    This permits the disclosed historical whole-record derivative profile. It
    never transforms that profile into strictly inductive raw preprocessing.
    Unknown producers/fit scopes remain an unavailable profile, not zero/default.
    """
    from input_owner import capture
    from .recordings import validate_joined, validate_recordings
    rec = owner.begin('capture_original_derivative_provenance')
    answer = None
    try:
        p = document(root, row, owner)
        expected = {'schema', 'profile', 'channel_names', 'eeg_unit', 'reference', 'clock', 'steps', 'source_recordings', 'evidence'}
        need(type(p) is dict and set(p) == expected and p['schema'] == 'neural080_original_derivative_provenance_v1', 'closed original derivative provenance')
        need(p['profile'] == 'released_whole_record_derivatives_disclosed_v1', 'only disclosed historical derivative profile selected; unknown/raw prospective preprocessing needs separate method review')
        _, channels = validate_joined(joined)
        need(p['channel_names'] == list(channels), 'actual127 names in fixed common source order')
        need(type(p['eeg_unit']) is str and p['eeg_unit'] and p['eeg_unit'] != 'unknown', 'actual original EEG numerical units required')
        need(type(p['reference']) is str and p['reference'] and p['reference'] != 'unknown', 'actual common released channel reference required')
        need(p['clock'] == {'samples':1800,'sampling_hz':500,'start_s':-0.1,'last_s':3.498,'analysis_slice':[50,1550]}, 'exact declared source/analysis clock')
        required = {'artifact_rejection', 'ica', 'channel_reference', 'normalization'}
        need(type(p['steps']) is list and len(p['steps']) == 4 and {s.get('name') for s in p['steps']} == required, 'all original fitted preprocessing stages explicitly disclosed')
        for step in p['steps']:
            need(type(step) is dict and set(step) == {'name','procedure','fit_scope','source'}, 'closed original preprocessing step')
            need(type(step['procedure']) is str and step['procedure'], 'actual source procedure, including explicit none')
            need(step['fit_scope'] in ('whole_record','per_trial','fixed','none'), 'unknown preprocessing scope is a source hold')
            capture(root, descriptor(step['source'],cap=16_777_216), owner, max_bytes=16_777_216)
        records = validate_recordings(recording_roster)
        expected_records = sorted((p,s,m,r['md5']) for (p,s,m),r in records.items())
        need(type(p['source_recordings']) is list and sorted(tuple(r) for r in p['source_recordings']) == expected_records, 'all96 actual original recording identities bind preprocessing profile')
        need(type(p['evidence']) is list and p['evidence'], 'actual unit/reference/preprocessing source evidence required')
        for e in p['evidence']:
            capture(root, descriptor(e,cap=16_777_216), owner, max_bytes=16_777_216)
        answer = p
    except BaseException as exc:
        owner.failure(rec, exc)
    owner.complete(rec)
    return answer
