"""Frozen program composition. Counts are cases within one benchmark, never new tasks."""
TASK='PAPER-ROOT-ADD-014'
CONDITION='full_released_typed_inputs_portable_training_v1'
PEOPLE=('p01','p02','p05','p06','p07','p08','p09','p10','p11')
COUNTS=dict(zip(PEOPLE,(11,25,35,38,31,10,19,136,128)))
SIGNALS=('corrected_alpha','broadband','raw_alpha','low_broadband')
ROLES=('full','train_first','train_second')
PURPOSES=('spectral_reproduction','spatial_reproduction','spatial_improvement')
CONDITIONS=(('corrected_alpha','GS',False),('broadband','GS',False),('raw_alpha','GS',False),('low_broadband','GS',False),('corrected_alpha','OG',False),('broadband','OG',False),('corrected_alpha','GS',True),('raw_alpha','GS',True))
VERSIONS={'python':'3.11.6','numpy':'2.4.6','scipy':'1.17.1'}
COVERAGE={'people':9,'electrodes':433,'spectral_matrices':36,'spectral_rows':1732,'spectral_scalar_slots':129900,'spatial_conditions':72,'spatial_cases':3464,'parameters_per_panel':10392,'global_programs':6,'phases':85}

def indices(role):
    if role not in ROLES:raise ValueError('fixed fit role')
    return list(range(75)) if role=='full' else list(range(38)) if role=='train_first' else list(range(38,75))

def phases():
    out=[]
    for mode,purpose in [('spectral','spectral_reproduction'),('spatial','spatial_reproduction')]:
        for arm in ('A','B'):
            out.append(dict(phase_id=mode+'_'+arm,mode=mode,arm=arm,purpose=purpose,participant=None,fit_role=None))
    for arm in ('A','B',None):
        mode='reference' if arm is None else 'corrected'
        for person in PEOPLE:
            for role in ROLES:
                out.append(dict(phase_id=(arm or 'operator')+'_'+person+'_'+role,mode=mode,arm=arm,purpose=None if arm is None else 'spatial_improvement',participant=person,fit_role=role))
    assert len(out)==85
    return out
