"""Fixed prospective full-participant category-transfer task, not a paper replay."""
VERSION = 'neural075-v1'
PEOPLE = ['Subject' + str(i) for i in range(1, 6)]
ARMS = ['neural', 'no_neural', 'training_permuted']
PHASES = ['imagery', 'perception']
ROWS = {'imagery': 500, 'perception': 1750}
REPEATS = {'imagery': 10, 'perception': 35}
N_CATEGORY = 50
ROI = 'ROI_VC'
FEATURE = 'cnn7'
SCORE_CAP = 1_000_000.0


def case_ids():
    return [f'{person}/{arm}/{phase}' for person in PEOPLE for arm in ARMS for phase in PHASES]
