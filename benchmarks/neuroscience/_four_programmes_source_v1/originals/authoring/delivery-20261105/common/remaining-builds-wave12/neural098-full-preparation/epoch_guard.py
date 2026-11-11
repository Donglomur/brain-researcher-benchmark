"""Retained identity custody across exact original eight-epoch window batches."""
import sys
from pathlib import Path
from custody import need, hash_staged
from native_capture import epoch_snapshot, verify_split_group, FIELDS
from source_plan import encode, digest


def batch_identity(np, epochs, indices=None):
    selection = epochs.selection if indices is None else epochs.selection[indices]
    events = epochs.events if indices is None else epochs.events[indices]
    table = epochs.metadata if indices is None else epochs.metadata.iloc[indices]
    need(0 < len(selection) <= 8, 'original at-most-eight epoch read')
    metadata = []
    for _, row in table.iterrows():
        item = {k: row[k] for k in FIELDS}
        trigger = item['Stim_trigger']
        need(np.isscalar(trigger) and not isinstance(trigger, (bool, np.bool_))
             and bool(np.isfinite(trigger)) and float(trigger) == int(trigger), 'integral batch metadata stimulus')
        item['Stim_trigger'] = int(trigger)
        if isinstance(item['Response'], np.bool_): item['Response'] = bool(item['Response'])
        metadata.append(item)
    return digest(encode({'selection': selection.tolist(), 'events': events.tolist(),
        'metadata': metadata, 'times': epochs.times.tolist(), 'channels': list(epochs.ch_names),
        'types': list(epochs.get_channel_types()), 'bads': list(epochs.info['bads']),
        'sfreq': float(epochs.info['sfreq'])}))


class Batch:
    def __init__(self, owner, value, expected_selection, expected_identity):
        self.owner, self.value = owner, value
        need(value.selection.tolist() == expected_selection, 'native subset preserves ordered saved selection')
        self.identity = batch_identity(owner.library.np, value)
        need(self.identity == expected_identity, 'subset retains exact original metadata/header identity')

    def get_data(self, *, picks):
        o = self.owner; o.budget.check()
        need(batch_identity(o.library.np, self.value) == self.identity, 'unchanged batch before read')
        result = o.library.call(self.value.get_data, picks=picks)
        need(batch_identity(o.library.np, self.value) == self.identity, 'no native epoch drops/reorder/metadata drift during read')
        o.budget.check()
        return result


class Epochs:
    def __init__(self, owner, value): self.owner, self.value = owner, value
    def __getattr__(self, name): return getattr(self.value, name)
    def __getitem__(self, indices):
        need(type(indices) is list and 0 < len(indices) <= 8 and all(type(i) is int for i in indices),
             'original explicit small integer batch')
        expected = self.value.selection[indices].tolist()
        identity = batch_identity(self.owner.library.np, self.value, indices)
        child = self.owner.library.call(self.value.__getitem__, indices)
        return Batch(self.owner, child, expected, identity)


class Guard:
    def __init__(self, *, library, people, plan, identities, stage, stage_fd, files, signatures, caps, budget):
        self.library, self.people, self.plan = library, people, plan
        self.identities, self.stage, self.stage_fd = identities, Path(stage), stage_fd
        self.files, self.signatures, self.caps, self.budget = files, signatures, caps, budget
        self.index = 0; self.pending = None; self.active = None
        self.closed_people = []

    def rehash(self, item):
        for row in item['epochs']['parts']:
            hash_staged(self.stage_fd, row, self.signatures[row['path']], self.budget)

    def source_pin(self, path, pin):
        self.budget.check()
        need(self.index < len(self.people), 'one complete source sequence')
        person = self.people[self.index]; item = self.plan['participants'][person]
        primary = item['epochs']['parts'][0]
        need(Path(path) == self.stage / primary['path'] and pin == {k: primary[k] for k in ('bytes', 'sha256')},
             'canonical selected epoch source')
        if self.pending is None:
            self.rehash(item); self.pending = person
        else:
            need(self.pending == person and self.active is not None, 'paired original source custody calls')
            original = None
            try:
                _, identity = epoch_snapshot(self.library.np, self.active, self.caps)
                need(identity == self.identities[person]['epoch_identity_sha256'], 'whole saved epoch identity after all reads')
            except BaseException as exc:
                original = exc
            try: self.close_active()
            except BaseException as cleanup:
                if original is not None and not isinstance(original, Exception): raise original
                raise cleanup from original
            if original is not None: raise original
            self.rehash(item)
            self.closed_people.append(person); self.index += 1; self.pending = None
        return tuple(self.signatures[primary['path']])

    def read_epochs(self, path, *, preload, verbose):
        need(self.pending is not None and self.active is None and preload is False and verbose == 'ERROR',
             'one guarded original native epoch open')
        item = self.plan['participants'][self.pending]
        expected = verify_split_group(self.library, self.stage, item['epochs'], self.budget)
        need(Path(path) == expected[0], 'same selected epoch entry')
        value = self.library.mne.read_epochs(path, preload=False, verbose=verbose)
        self.active = value
        _, identity = epoch_snapshot(self.library.np, value, self.caps)
        need(identity == self.identities[self.pending]['epoch_identity_sha256'], 'saved epoch identity before window computation')
        return Epochs(self, value)

    def close_active(self):
        value, self.active = self.active, None
        if value is not None: self.library.close_epochs(value)

    def complete(self):
        need(self.index == 33 and self.closed_people == list(self.people) and self.pending is None
             and self.active is None, 'all33 native source lifecycles closed')
        self.budget.check()
