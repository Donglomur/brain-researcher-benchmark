"""Prospective EEGMoments ocular/dynamics contract; no outcome-selected policy."""
SUBJECTS=tuple(f'sub-{i:02}' for i in range(1,7))
SESSIONS=tuple(f'ses-{i:02}' for i in range(1,9))
FIT=tuple(i for i in range(1,1001) if i%10)
VALIDATION=tuple(range(10,1001,10))
QUERY=tuple(range(1001,1103))
CHANNELS=127  # authenticated released metadata, not the128-channel apparatus
EEG_BINS=150
ARMS=('nuisance','nuisance_eye','nuisance_dynamic','full','full_shift500ms')
SHIFT_FEATURE_BINS=5  # 100ms dynamic-feature clock; query-only, frozen full model
FEATURE_BINS=30
BOOTSTRAP_DRAWS=10000
BOOTSTRAP_SEED=80057
