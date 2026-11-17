"""Narrow MNE1.13.2 calls, metadata guards and warning policy.

Imported only after the driver authenticates the selected native qualification.
No model, fitting, classification, resampling or preprocessing function is used.
"""
import importlib
from pathlib import Path
from types import SimpleNamespace
import warnings

from custody import need, relative


class Library:
    def __init__(self, budget):
        self.budget = budget
        self.np = importlib.import_module('numpy')
        mne = importlib.import_module('mne')
        need(mne.__version__ == '1.13.2', 'reviewed MNE source API version')
        self.fiff_module = importlib.import_module('mne._fiff.open')
        self.raw_module = importlib.import_module('mne.io.fiff.raw')
        self.annotations = importlib.import_module('mne.annotations')
        self.logging_module = importlib.import_module('mne.utils._logging')
        self.log_context = self.logging_module.use_log_level
        self.warnings = []
        self.mne = SimpleNamespace(
            io=SimpleNamespace(read_raw_fif=self.wrap(mne.io.read_raw_fif)),
            find_events=self.wrap(mne.find_events), read_events=self.wrap(mne.read_events),
            concatenate_events=self.wrap(mne.concatenate_events), read_epochs=self.wrap(mne.read_epochs))
        self.fiff_open = self.wrap(self.fiff_module.fiff_open)
        self.next_fname = self.wrap(self.fiff_module._get_next_fname)

    def call(self, fn, *args, **kwargs):
        self.budget.check()
        # MNE.warn suppresses Python warnings at ERROR. Hold WARNING and
        # translate the canonical ERROR seam so corruption cannot be hidden.
        with self.log_context('WARNING'):
            with warnings.catch_warnings():
                # Original author suffixes _annot/_filt may produce naming warnings.
                # All other warnings (including data corruption/zero fill and event
                # coordinate correction) become failures before any success return.
                warnings.simplefilter('error')
                warnings.filterwarnings('ignore', message=r'This filename .* does not conform to MNE naming conventions.*',
                                        category=RuntimeWarning)
                if 'verbose' in kwargs:
                    need(kwargs['verbose'] in ('ERROR', 'WARNING'), 'reviewed explicit native verbosity seam')
                    kwargs = dict(kwargs, verbose='WARNING')
                value = fn(*args, **kwargs)
        self.budget.check()
        return value

    def wrap(self, fn):
        return lambda *a, **k: self.call(fn, *a, **k)

    def split_metadata(self, fid, tree):
        """Reject ambiguous/unsafe native next references before helper follow."""
        f = self.fiff_module
        refs = f.dir_tree_find(tree, f.FIFF.FIFFB_REF)
        need(len(refs) <= 2, 'bounded previous/next split references')
        next_count = 0
        for node in refs:
            entries = node['directory']
            roles = [e for e in entries if e.kind == f.FIFF.FIFF_REF_ROLE]
            need(len(roles) == 1, 'one native split role')
            role = int(self.call(f.read_tag, fid, roles[0].pos).data.item())
            need(role in (1, 2), 'known native split role')
            if role != 2: continue
            next_count += 1
            names = [e for e in entries if e.kind == f.FIFF.FIFF_REF_FILE_NAME]
            nums = [e for e in entries if e.kind == f.FIFF.FIFF_REF_FILE_NUM]
            need(len(names) <= 1 and len(nums) <= 1 and bool(names or nums), 'unambiguous next split reference')
            need(all(entries.index(roles[0]) < entries.index(e) for e in names + nums),
                 'split role before filename or ordinal as native helper requires')
            if names:
                name = self.call(f.read_tag, fid, names[0].pos).data
                # Ordinary author split files are siblings; no absolute path,
                # parent traversal or hidden subdirectory can be auto-followed.
                need(len(relative(name)) == 1 and name.endswith('.fif'), 'safe native next split basename')
            if nums:
                num = self.call(f.read_tag, fid, nums[0].pos).data.item()
                need(type(num) is int and 1 <= num < 64, 'bounded native next split ordinal')
        need(next_count <= 1, 'one native next split reference')

    def acquisition_gaps(self, raw, cap):
        need(len(raw.annotations) <= cap, 'bounded acquisition annotations')
        starts, stops = self.call(self.annotations._annotations_starts_stops, raw, ['BAD_ACQ_SKIP'])
        need(len(starts) == len(stops) and len(starts) <= cap, 'complete acquisition gap intervals')
        result = []
        for a, b in zip(starts, stops):
            a, b = int(a), int(b)
            need(0 <= a <= b <= raw.n_times, 'acquisition gap inside selected raw extent')
            if a != b: result.append([int(raw.first_samp) + a, int(raw.first_samp) + b])
        return result

    def close_epochs(self, epochs):
        errors = []
        seen = set()
        for raw in epochs._raw:
            fid = raw.fid
            if id(fid) in seen: continue
            seen.add(id(fid))
            try: fid.close()
            except BaseException as exc: errors.append(exc)
        if errors: raise errors[0]
