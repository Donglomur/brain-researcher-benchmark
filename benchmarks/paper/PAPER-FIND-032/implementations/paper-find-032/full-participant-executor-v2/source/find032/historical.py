"""Exact historical reconstruction boundary; never quietly substitute corrected source."""
from .core import Refusal

CURRENT_COMMIT = 'a454439aec8936ff9de2199ab255472c7d140b8c'
HISTORICAL_GAPS = (
    'current omission helpers absent from current base; older compatible helpers recovered but whole revision differs',
    'current sound KFold/train0-.32/test+-.666 disagrees with Methods stratified5/full+-.7',
    'newcv sound product naming differs from qmd cv and reord suffix convention',
    'complete OOF confusion producer for qmd expected rd_to_rd_confmats.npz not recovered',
    'literal fixed four-block135 theoretical route lacks compatible authenticated full-axis producer',
    'omission random-reordered expected qmd product is not emitted by selected script',
    'quick-run100 vs publication10000 permutation and false save default require exact version reconciliation',
)


def status():
    return {'profile': 'historical_reproduction', 'paper_parity_primary': True,
            'current_commit': CURRENT_COMMIT, 'complete_historical_runner': False,
            'gaps': HISTORICAL_GAPS, 'corrected_profile_is_substitute': False}


def run_historical(*args, **kwargs):
    raise Refusal('historical whole-paper reproduction unavailable: ' + '; '.join(HISTORICAL_GAPS))
