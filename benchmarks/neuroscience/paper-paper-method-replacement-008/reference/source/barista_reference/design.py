"""Executable, declared choices where the reconstruction release is incomplete."""
from dataclasses import asdict, dataclass
import random

PEOPLE = (1, 2, 3, 4, 6, 7, 10)
COUNTS = {1: (2787, 348, 348, 91), 2: (3385, 422, 422, 100),
          3: (1825, 228, 228, 91), 4: (1795, 224, 224, 151),
          6: (1532, 191, 191, 134), 7: (1604, 200, 200, 205),
          10: (1506, 188, 188, 173)}
RECORDINGS = {1: 'sub_1_trial001', 2: 'sub_2_trial006', 3: 'sub_3_trial000',
              4: 'sub_4_trial000', 6: 'sub_6_trial004', 7: 'sub_7_trial000',
              10: 'sub_10_trial000'}
NATIVE_SESSIONS = {1: 'HOLDSUBJ_1_HS1_1', 2: 'HOLDSUBJ_2_HS2_6',
                   3: 'HOLDSUBJ_3_HS3_0', 4: 'HOLDSUBJ_4_HS4_0',
                   6: 'HOLDSUBJ_6_HS6_4', 7: 'HOLDSUBJ_7_HS7_0',
                   10: 'HOLDSUBJ_10_HS10_0'}
SCALES = ('channels', 'parcels', 'lobes')
MODELS = tuple('barista_' + e + '_' + m for e in SCALES for m in SCALES) + tuple(
    'random_' + e for e in SCALES)
ARMS = ('paper_and_data', 'paper_data_official_code')


@dataclass(frozen=True)
class ReferenceConfig:
    """All defaults are selected reference choices unless PAPER.md says otherwise.

    Five width entries mean FOUR affine maps, not five fully connected layers.
    Custom widths/bias/seed remain explicitly amended configurations.
    """
    h_widths: tuple = (64, 64, 64, 64, 64)
    h_bias: bool = True
    head_bias: bool = True
    dropout: float = 0.1
    seed: int = 0
    batch_size: int = 32
    epochs: int = 20
    pretrained_lr: float = 0.001
    head_lr: float = 0.01
    weight_decay: float = 0.01
    adam_betas: tuple = (0.9, 0.999)
    adam_eps: float = 1e-8
    warmup_epochs: int = 5
    decay: float = 0.99
    checkpoint_selection: str = 'last_epoch'
    masking: str = 'nearest_whole_groups_30pct'
    alpha_schedule: str = 'first10_one_then_0.9_to_0'
    temporal_tokenizer_trainable: bool = True
    reference_id: str = 'barista_reconstruction_amended_v2'

    def validate(self):
        if (type(self.h_widths) is not tuple or len(self.h_widths) != 5
                or self.h_widths[0] != 64 or self.h_widths[-1] != 64
                or any(type(n) is not int or n < 1 or n > 4096 for n in self.h_widths)):
            raise ValueError('Input64 + three explicit hidden widths + output64 required')
        if type(self.h_bias) is not bool or type(self.head_bias) is not bool:
            raise ValueError('Explicit bias choices required')
        if type(self.seed) is not int or not 0 <= self.seed < 2**32:
            raise ValueError('Explicit uint32 seed required')
        if type(self.batch_size) is not int or not 1 <= self.batch_size <= 128:
            raise ValueError('Explicit batch size in1..128 required')
        selected = ReferenceConfig(h_widths=self.h_widths, h_bias=self.h_bias,
                                   head_bias=self.head_bias, seed=self.seed,
                                   batch_size=self.batch_size)
        if self != selected:
            raise ValueError('This track fixes the documented loss/training schedule')
        return asdict(self)


def epoch_schedule(epoch, config):
    config.validate()
    if type(epoch) is not int or not 0 <= epoch < config.epochs:
        raise ValueError('Epoch must be0..19')
    alpha = 1.0 if epoch < 10 else (19 - epoch) / 10.0
    # Equivalent epoch rates to the released Torch2.4 LinearLR/SequentialLR
    # with step() after each epoch: .2,.36,.52,.68,.84,1,.99,... .
    multiplier = (0.2 + 0.8 * epoch / config.warmup_epochs
                  if epoch < config.warmup_epochs
                  else config.decay ** (epoch - config.warmup_epochs))
    return {'alpha': alpha, 'pretrained_lr': config.pretrained_lr * multiplier,
            'head_lr': config.head_lr * multiplier}


def choose_group_mask(group_ids, seed):
    """Seeded subset-sum; nearest feasible masked CHANNEL count to30%.

    Whole groups and nonempty context/targets are mandatory. Because each channel
    has12 tokens, channel fraction equals token fraction. Integer distances avoid
    rounding ambiguity. Equal distances prefer the smaller masked count; group
    identities at the same count depend on the seeded order. This is NOT the
    unreleased historical masking sampler.
    """
    if (type(group_ids) is not tuple or len(group_ids) < 2
            or any(type(g) is not str or not g for g in group_ids)
            or type(seed) is not int):
        raise ValueError('Ordered explicit spatial groups and integer seed required')
    groups = list(dict.fromkeys(group_ids))
    random.Random(seed).shuffle(groups)
    counts = {g: group_ids.count(g) for g in groups}
    attainable = {0: ()}
    for group in groups:
        for count, subset in list(attainable.items()):
            new_count = count + counts[group]
            if new_count not in attainable:
                attainable[new_count] = subset + (group,)
    candidates = [n for n in attainable if 0 < n < len(group_ids)]
    if not candidates:
        raise ValueError('Whole-group mask cannot retain observed context')
    n = min(candidates, key=lambda k: (abs(10*k - 3*len(group_ids)), k))
    selected = frozenset(attainable[n])
    return tuple(g in selected for g in group_ids)


def validate_session(row):
    """Authenticate structural scope, not authenticity of operator-held identities."""
    fields = {'person', 'recording', 'channels', 'groups', 'splits'}
    if type(row) is not dict or set(row) != fields or type(row['person']) is not int:
        raise ValueError('Exact session fields required')
    p = row['person']
    if p not in PEOPLE or row['recording'] != RECORDINGS[p]:
        raise ValueError('Original held-session roster required')
    channels = row['channels']
    if (type(channels) is not tuple or len(channels) != COUNTS[p][3]
            or any(type(c) is not str or not c for c in channels)
            or len(set(channels)) != len(channels)):
        raise ValueError('Complete ordered native channels required')
    if type(row['groups']) is not dict or set(row['groups']) != set(SCALES):
        raise ValueError('All three channel/parcel/lobe group maps required')
    for scale, groups in row['groups'].items():
        if (type(groups) is not tuple or len(groups) != len(channels)
                or any(type(g) is not str or not g for g in groups)):
            raise ValueError('One explicit atlas/group identity per channel required')
        if scale == 'channels' and len(set(groups)) != len(channels):
            raise ValueError('Channel-scale groups must be one per channel')
    splits = row['splits']
    if type(splits) is not dict or set(splits) != {'train', 'validation', 'test'}:
        raise ValueError('All original split roles required')
    all_ids = []
    for role, count in zip(('train', 'validation', 'test'), COUNTS[p][:3]):
        ids = splits[role]
        if (type(ids) is not tuple or len(ids) != count
                or any(type(i) is not str or not i for i in ids)):
            raise ValueError('Full ordered Table6 split support required')
        all_ids.extend(ids)
    if len(set(all_ids)) != len(all_ids):
        raise ValueError('Training/validation/test identities must be disjoint')
    return row


def programme_cells(sessions):
    if type(sessions) is not tuple or tuple(s['person'] for s in sessions) != PEOPLE:
        raise ValueError('All seven people in original order required')
    for session in sessions:
        validate_session(session)
    return tuple({'arm': arm, 'model': model, 'person': s['person'],
                  'recording': s['recording']} for arm in ARMS for model in MODELS
                 for s in sessions)


def model_scales(model_name):
    if model_name not in MODELS:
        raise ValueError('One of all12 retained reconstruction models required')
    parts = model_name.split('_')
    # The random controls have encoding scale but no pretraining mask history.
    # Their reconstruction finetuning masking is explicitly selected as channels.
    return (parts[1], parts[2] if len(parts) == 3 else 'channels')
