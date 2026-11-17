"""Full original presentation-log path, with software/physical limits explicit."""
from __future__ import annotations
from dataclasses import asdict
from .source_map import need


def produce(log_root, selection, source_map, joined, owner, output):
    """Use all768 actual MAT logs and all45,144 joined coordinates.

    Original experiment calls PlayMovie/GetSecs even for clips with no audio
    track. Therefore its positive onset_audio/offset_audio interval remains a
    playback-command observation for the confirmed34 silent clips; it never
    becomes a measured acoustic interval. The accepted MAT scalar/visual timing
    reader is reused unchanged and does not infer a hardware clock bridge.
    """
    from input_owner import Writer
    from presentation_clock import produce as observed_software_clocks
    record = owner.begin('complete_generalization_source_clocks')
    answer = None
    try:
        writer = Writer(output, owner)
        media_selection = {'videos': [dict(video_id=r.video_id, source_media=r.source_media) for r in source_map.roles]}
        software = observed_software_clocks(log_root, selection, media_selection, joined, owner, writer.root / 'software')
        need(software['all_presented_noncatch_trials'] == 50688 and software['joined_trials'] == 45144, 'complete source presentation and neural/eye join')
        roles = [{'video_id': r.video_id, 'experimental_name': r.experimental_name,
                  'source_media':r.source_media,'clip_origin_rational':list(r.timeline_origin),
                  'audio_status':r.audio_status,
                  'acoustic_feature_rule':'verified_no_playback_zeros_with_shared_status' if r.audio_status == 'presented_silent_no_track' else 'native_audio_resampled_from_actual_pts',
                  'log_audio_endpoints':'software_playback_commands_only'} for r in source_map.roles]
        role_descriptor = writer.document('MEDIA_CLOCK_ROLES.json', {'schema':'neural080_media_clock_roles_v1','videos':roles})
        answer = {'schema':'neural080_generalization_clocks_v1',
                  'canonical_source_map_sha256':source_map.canonical_source_map_sha256,
                  'software':software,'software_root':'software','media_clock_roles':role_descriptor,
                  'source_feature_clock':'native_media_pts_minus_explicit_rational_origin',
                  'target_clock':'released_source_declared_epoch; samples50:1550 into150 fixed20ms bins',
                  'timeline_warp':False,'physical_synchronization':'unavailable; independent hardware evidence required for physical latency claims',
                  'eeg_trigger_time':None,'eye_message_time':None,'physical_audio_onset':None,
                  'analysis_profile':'clip-time predictive association with disclosed source clock limitations',
                  'boundary_conventions':{'flow':'nearest observed transition-vector extension to clip edges','audio':'selected200-sample reflection around complete actual3s waveform'},
                  'conventions_are_measured_support':False}
        return_descriptor = writer.document('CLOCKS.json',answer)
        answer = {'manifest':return_descriptor,'clocks':answer,'output':str(writer.root)}
    except BaseException as exc:
        owner.failure(record,exc)
    owner.complete(record)
    return answer
