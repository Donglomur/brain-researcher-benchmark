"""N057 proposed measured-envelope definition, separate from N055 adoption."""
VERSION='n057-measured-envelopes-v1'
EXCLUDED=('native_cumulative_logical_read_bytes','native_cumulative_logical_write_bytes','native_cumulative_file_churn')
def unobserved(operation,policy):
    return [{'operation':operation,'quantity':k,'value':None,'status':'unobserved_by_selected_observer','resource_policy':policy} for k in EXCLUDED]
def states(policy,custody,admission,numerical,semantic,resource):
    return dict(resource_policy=policy,containment_custody=custody,remaining_envelope_admission=admission,numerical_availability=numerical,semantic_mode_qualification=semantic,measured_resource_comparison_qualification=resource)
