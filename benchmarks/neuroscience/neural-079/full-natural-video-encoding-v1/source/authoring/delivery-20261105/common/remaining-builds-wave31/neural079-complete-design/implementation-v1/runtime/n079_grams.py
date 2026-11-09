"""Actual full-column feature streaming, with no target-dependent transforms."""
import importlib
from n079_common import require, integer, identity
from n079_arrays import preflight
from n079_plan import DIMS, D
from n079_preparation import compensated_add


class GramBuilder:
    def __init__(self, context, reader, numeric, limits, column_block):
        context.require_effect('array_read', 'feature-grams')
        self.context, self.reader, self.numeric, self.limits = context, reader, numeric, limits
        self.width = integer(column_block, 1)
        require(reader.shape == (1102, D), 'all1102/all17 complete raw feature object')
        self.np = importlib.import_module('numpy')

    def partition(self, selected):
        train_rows = [v - 1 for v in selected['train']]; other_rows = [v - 1 for v in selected['other']]
        n, m = len(train_rows), len(other_rows)
        cells = n * n + m * n
        # Retained17 layer pairs + current pair/compensation/products and
        # feature inputs. Numerical-library workspace remains separate.
        total_slots = 23 * cells + 4 * (n + m) * self.width
        require(total_slots <= self.limits['max_live_float_slots'], 'all17 Gram storage plus active block bound')
        self.context.ledger.charge('feature-grams', {'logical_float_slots': total_slots}, 'full partition Gram allocation')
        train, cross, manifests = [], [], []; offset = 0
        for layer, columns in enumerate(DIMS):
            total = self.np.zeros((n, n), dtype='float64'); correction = self.np.zeros_like(total)
            other = self.np.zeros((m, n), dtype='float64'); other_correction = self.np.zeros_like(other)
            covered = 0
            for start in range(offset, offset + columns, self.width):
                stop = min(offset + columns, start + self.width); width = stop - start
                require(start == offset + covered, 'exact ordered feature-column coverage')
                preflight(self.limits, max(n, m), width, 4 * (n + m) * width + 4 * cells)
                values = self.reader.block(train_rows, start, stop); query = self.reader.block(other_rows, start, stop)
                transformed = self.numeric.standardize(values, query, limits=self.limits)
                pair = self.numeric.gram_pair(transformed['train'], transformed['other'], limits=self.limits)
                compensated_add(total, correction, pair['train'], self.np)
                compensated_add(other, other_correction, pair['cross'], self.np)
                state = self.context.state_store.pack('feature-grams', '%s-layer%d-col%d' %
                    (selected['id'], layer, start), transformed['moments'],
                    {'partition': selected, 'layer': layer, 'start': start, 'stop': stop,
                     'raw_feature_object': self.reader.selected})
                manifests.append({'layer': layer, 'start': start, 'stop': stop, 'moments': state})
                covered += width
            require(covered == columns, 'full admitted layer complete')
            value, value_other = total + correction, other + other_correction
            require(self.np.isfinite(value).all() and self.np.isfinite(value_other).all(), 'finite full layer Grams')
            train.append(value); cross.append(value_other); offset += columns
        require(offset == D and len(train) == len(cross) == 17, 'full concatenation support')
        ident = {'source_id': self.reader.selected['object']['sha256'],
                 'fit_id': identity(selected['train'], self.context.encoding_limits)['sha256'],
                 'query_id': identity(selected['other'], self.context.encoding_limits)['sha256'],
                 'columns_id': identity(list(DIMS), self.context.encoding_limits)['sha256']}
        return {'train': train, 'cross': cross, 'identity': ident, 'moments': manifests,
                'partition': selected, 'full_feature_columns': D}
