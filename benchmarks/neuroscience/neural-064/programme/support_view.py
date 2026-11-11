"""Deterministic support-context projection from already-admitted source metadata.
This removes neural values and source file paths. Hash pseudonyms are stable case
joins, not anonymization or source authority. Actual disclosure must be issued by
the future role owner; no protected cohort is read or exposed by this build.
"""
import hashlib

def opaque(kind,value):return kind+'-'+hashlib.sha256((kind+':'+str(value)).encode()).hexdigest()[:24]

def support_context(membership,events,dispositions):
    allowed=('event','behavior_event','experiment','mouse','session','container','condition','image','native_image_novel',
      'lifetime_image_count','lifetime_count_status','session_order','within_session_history','pre_running_bin','pre_pupil_bin',
      'change','outcome_status','outcome_flags','neural_support')
    identities={'event','behavior_event','experiment','mouse','session','container'}
    def project(row,fields):
        out={k:row[k] for k in fields if k in row}
        for k in identities&set(out):out[k]=opaque(k,out[k])
        return out
    result={'population':membership['population'],'membership_status':membership['membership_status'],
       'source_membership_binding':membership['source_membership_binding'],
       'experiments':[project(r,('experiment','mouse','session','container','condition','status','source_event_observations','retained_event_observations','excluded_event_observations')) for r in membership['experiments']]}
    exclusions=[project(r,('event','behavior_event','experiment','mouse','session','container','condition','reason')) for r in dispositions]
    return result,[project(r,allowed) for r in events],exclusions


def assessed_support_context(membership,events,dispositions):
    """One actual metadata join feeds both the permitted view and protected table.
    The caller must supply source-owned event census/exclusions explicitly.
    """
    from .support import support_tables
    members,retained,excluded=support_context(membership,events,dispositions)
    context={'membership':members,'events':retained,'event_dispositions':excluded}
    return context,support_tables(members,retained,excluded)
