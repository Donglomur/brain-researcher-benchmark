"""Complete source-group census joined to independently supplied annotations.

Reads actual group names and ordinary identity datasets only when authorized to
operate on authentic HDF5. It does not inspect labels or infer animal/session,
curation, blockade or expert truth from file names. No HDF5 call ran at build.
"""
from .cohort import Cohort,Member,SOURCE_ROLES,SupportError

def _scalar_text(value):
    value=value.reshape(-1)[0]
    if hasattr(value,'item'):value=value.item()
    return value.decode('utf8') if isinstance(value,bytes) else str(value)

def build_census(source_paths,annotations,*,source_census_identity):
    if set(source_paths)!=set(SOURCE_ROLES):raise SupportError('all five original sources required')
    import h5py
    observed={};seen=set()
    for role in SOURCE_ROLES:
        with h5py.File(source_paths[role],'r') as source:
            for name in source:
                if 'neuron' not in name:continue  # exact published group selection
                group=source[name]
                if not isinstance(group,h5py.Group):raise SupportError('neuron member is not a source group')
                dataset=_scalar_text(group['dataset_id'][()])
                field='neuron_id' if role=='lisberger' else 'neuron_relative_id'
                unit=_scalar_text(group[field][()])
                observed[(role,name)]=(dataset,unit)
    if not observed:raise SupportError('source census is empty')
    for member in annotations:
        if not isinstance(member,Member):raise SupportError('typed complete annotations required')
        member.validate();key=(member.source_role,member.h5_group)
        if key not in observed or observed[key]!=(member.key.recording,member.key.unit):
            raise SupportError('annotation/source identity mismatch')
        seen.add(key)
    if seen!=set(observed):raise SupportError('every original source group needs a retained disposition')
    return Cohort(tuple(annotations),SOURCE_ROLES,True,source_census_identity).validate()
