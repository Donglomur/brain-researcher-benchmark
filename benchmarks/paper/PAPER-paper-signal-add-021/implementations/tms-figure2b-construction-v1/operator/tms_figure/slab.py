"""One bounded HDF5 channel slab; scalar arithmetic and source order stay separate.

This is a data-access optimization only. A complete sequential pass loads 248
slabs rather than 2,628,800 cell slices. Cached access still charges each returned
15-value vector; repeated/nonsequential reads are not free logical transfers.
"""
from .contract import require

SLAB_SHAPE = (15, 200, 53)
SLAB_BYTES = 15 * 200 * 53 * 8


class ChannelSlab:
    def __init__(self, budget):
        self.budget = budget
        self.key = None
        self.data = None
        self.loads = 0
        self.returned_vectors = 0

    def values(self, dataset, condition, channel, frequency, time):
        key = (condition, channel)
        if key != self.key:
            # Drop the previous operand before allocating its successor.
            self.key = None
            self.data = None
            self.budget.charge(read=SLAB_BYTES)
            data = dataset[:, :, :, channel]
            require(data.shape == SLAB_SHAPE and data.dtype.kind == 'f'
                    and data.dtype.itemsize == 8 and data.nbytes == SLAB_BYTES,
                    'exact bounded binary64 channel slab')
            self.data = data
            self.key = key
            self.loads += 1
        self.budget.charge(read=15 * 8)
        # Original HDF5 dimension zero is preserved verbatim. No reduction,
        # sorting, dtype promotion, missing-value filtering or permutation.
        result = self.data[:, time, frequency].tolist()
        self.returned_vectors += 1
        return result

    def close(self):
        self.data = None
        self.key = None
