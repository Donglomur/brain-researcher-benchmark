"""Real FIF/event/epoch consumers. All heavy imports and effects are call-local."""
from dataclasses import dataclass
import io
from .core import Custody, Refusal
from .admission import capture_recording, assert_scientific_metadata
from .decoding import EpochSet
from .support import SupportMap, reorder_plan


@dataclass
class Recording:
    raw: object
    events: object
    support: SupportMap
    input_capture: object
    closed: bool = False

    def close(self):
        if not self.closed:
            self.closed = True
            self.raw.close()


def load_recording(plan, participant, condition, root_fd, budget, custody, operation):
    import mne
    data, captured = capture_recording(plan, participant, condition, root_fd, budget, custody)
    local = Custody(custody)
    stream = io.BytesIO(data)
    raw = None
    with local.attempt('load FIF'):
        try:
            operation = operation.scoped(local)
            with operation('fif-read', {'participant': participant, 'condition': condition}):
                raw = mne.io.read_raw_fif(stream, preload=True, allow_maxshield=False,
                                          on_split_missing='raise', verbose='ERROR')
                assert_scientific_metadata(raw)
                events = mne.find_events(raw, shortest_event=1, verbose='ERROR')
            if len(events) == 0:
                raise Refusal('no actual events')
            # The prospective route uses the released 1–30 Hz data. It does not
            # pretend that a 0.1 Hz refilter can recover frequencies removed earlier.
            identity = captured.sha256 + ':' + str(raw.first_samp)
            result = Recording(raw, events, SupportMap.original(identity, raw.n_times), captured)
        except BaseException as error:
            if local.first is None:
                local.catch('FIF/event body', error)
        finally:
            local.close('captured FIF buffer close', stream.close)
            if local.first is not None and raw is not None:
                local.close('failed raw close', raw.close)
        local.raise_first()
    return result


def select_events(recording, stimulus):
    """Eligibility is fixed before fitting, with every removed index recorded."""
    events = recording.events
    codes = [int(x) for x in events[:, 2]]
    wanted = {1, 2, 3, 4} if stimulus == 'sound' else {10, 20, 30, 40}
    if stimulus not in ('sound', 'omission'):
        raise Refusal('unknown stimulus route')
    excluded = set()
    if stimulus == 'sound':
        for i, code in enumerate(codes):
            if code in {10, 16, 20, 30, 32, 40}:
                excluded.add(i)
                if i + 1 < len(codes):
                    excluded.add(i + 1)
    selected, dispositions = [], []
    for i, event in enumerate(events):
        sample = int(event[0]) - int(recording.raw.first_samp)
        if codes[i] not in wanted:
            reason = 'other_event'
        elif i in excluded:
            reason = 'omission_or_following_event'
        elif sample < 70 or sample + 70 >= recording.raw.n_times:
            reason = 'complete_141_sample_window_unavailable'
        else:
            selected.append(i)
            continue
        dispositions.append((i, reason))
    if not selected:
        raise Refusal('no complete eligible event windows')
    return tuple(selected), tuple(dispositions)


def epochs(recording, indices, stimulus, operation):
    import mne
    import numpy as np
    selected = recording.events[list(indices)].copy()
    with operation('epoch', {'stimulus': stimulus, 'events': len(indices)}):
        ep = mne.Epochs(recording.raw, selected, event_id=[1, 2, 3, 4] if stimulus == 'sound'
                        else [10, 20, 30, 40], tmin=-.7, tmax=.7, baseline=None,
                        picks='meg', preload=True, reject=None, flat=None, proj=True,
                        on_missing='raise', reject_by_annotation=True, event_repeated='error',
                        verbose='ERROR')
        if len(ep) != len(indices) or not np.array_equal(ep.events, selected):
            raise Refusal('MNE dropped or reordered preselected epoch support')
        data = ep.get_data()
        times = ep.times.copy()
        if len(times) != 141 or not np.allclose(times, np.arange(-70, 71) / 100, atol=1e-12, rtol=0):
            raise Refusal('observed epoch time axis differs from corrected profile')
    supports = tuple(recording.support.epoch(int(e[0]) - int(recording.raw.first_samp) - 70,
                                             int(e[0]) - int(recording.raw.first_samp) + 71)
                     for e in selected)
    labels = selected[:, 2].astype(int)
    if stimulus == 'omission':
        labels = labels // 10
    return EpochSet(data, labels, times, supports, tuple(indices))


def empirical_recording(random, target, *, stimulus, random_indices, target_indices,
                        operation, custody):
    import mne
    import numpy as np
    def rows(record, indices):
        return tuple((int(record.events[i, 0]) - int(record.raw.first_samp),
                      int(record.events[i, 2])) for i in indices)
    mapping, planned_events, originals = reorder_plan(
        rows(random, random_indices), rows(target, target_indices),
        recording=random.support.pieces[0].original.recording,
        sample_count=random.raw.n_times, segment_samples=33, padding_samples=200,
        stop_at_exhaustion=(stimulus == 'sound'))
    # The raw is owned here immediately on acquisition. The operation's exit
    # (including its final clock) and Recording construction precede transfer.
    local = Custody(custody)
    raw = None
    with local.attempt('empirical recording transfer'):
        try:
            operation = operation.scoped(local)
            with operation('empirical-reorder', {'stimulus': stimulus, 'pieces': len(mapping.pieces)}):
                blocks = [random.raw.get_data(start=p.original.start, stop=p.original.stop)
                          for p in mapping.pieces]
                data = np.concatenate(blocks, axis=1)
                raw = mne.io.RawArray(data, random.raw.info.copy(), first_samp=0, verbose='ERROR')
                events = np.array([(s, 0, c) for s, c in planned_events], dtype=int)
            result = Recording(raw, events, mapping, random.input_capture), originals
        except BaseException as error:
            # The scoped operation has already merged its original owner/index
            # into this local owner. Only an unowned body/transfer failure is new.
            if local.first is None:
                local.catch('empirical recording body/transfer', error)
        finally:
            if local.first is not None and raw is not None:
                local.close('failed empirical raw retirement', raw.close)
        local.raise_first()
    return result



def subset(epoch_set, count):
    if type(count) is not int or not 0 < count <= len(epoch_set.labels):
        raise Refusal('invalid matched denominator')
    return EpochSet(epoch_set.data[:count], epoch_set.labels[:count], epoch_set.times,
                    epoch_set.supports[:count], epoch_set.event_indices[:count])
