"""Production fit integration and the analytical seam for its actual streamed step."""
import hashlib
import math
import time


def require(ok, message):
    if not ok:
        raise ValueError(message)


def streamed_step(gradient, opt, optimizer_states, optimizers, currents, labels, mask, init_states,
                  *, np, jnp, tree_util, tree_map, l2_norm, optax, streamed_gradient,
                  source_transition, check, stats, validate):
    """The actual production mean-gradient and unchanged source update call path.

    Backend primitives are explicit for independently computed analytical controls.
    The public production entry binds them to the frozen scientific runtime only.
    validate(role, value) checks complete numerical trees; it does not alter them.
    """
    validate('parameters', opt)
    validate('optimizer_state', optimizer_states)
    validate('model_state', init_states)
    loss, gradients = streamed_gradient(gradient, opt, currents, labels, mask, init_states,
                                       np=np, jnp=jnp, tree_util=tree_util, check=check, stats=stats)
    validate('computed', loss)
    validate('computed', gradients)
    # The unchanged transition divides by these norms. Refuse undefined arithmetic;
    # no epsilon, clipping of norms, or zero-gradient special case is substituted.
    norms = [l2_norm(gradients[0][i]) for i in range(3)]
    norms += [l2_norm(gradients[1]), l2_norm(gradients[2])]
    require(all(math.isfinite(float(np.asarray(x))) and float(np.asarray(x)) > 0.0 for x in norms),
            'source normalization requires five finite positive group norms')
    result = source_transition(loss, gradients, opt, optimizer_states, optimizers, tree_map, l2_norm, optax)
    require(result['updates'] == 1, 'exactly one source transition')
    for name in ('normalized', 'proposed_updates'):
        validate('computed', result[name])
    validate('parameters', result['parameters'])
    validate('optimizer_state', result['optimizer_states'])
    result['loss'] = float(np.asarray(loss))
    return result


def streamed_test_prediction(predict, opt, currents, *, np, check, stats):
    """Explicit final 128-row feature-only path; no labels or metric argument."""
    require(tuple(currents.shape) == (128, 287), 'exact final feature-only TEST extent')
    result = None
    for row in range(128):
        check('test_before_singleton')
        prediction = np.asarray(predict(opt, currents[row:row + 1])).copy(order='C')
        require(prediction.shape == (1, 147) and prediction.dtype.kind == 'f' and
                bool(np.isfinite(prediction).all()), 'finite all-site test prediction')
        if result is None:
            result = np.empty((128, 147), dtype=prediction.dtype)
        require(prediction.dtype == result.dtype, 'unchanged test prediction dtype')
        result[row:row + 1] = prediction
        del prediction
        stats['test_singletons_completed'] += 1
        check('test_after_singleton')
    return result


class FitRuntime:
    """Bound production backend; neuronal states are fixed, opt/state carry evolves."""
    def __init__(self, arrays, meta, morphology_prefix, *, deadline, checkpoint_notice=None):
        import numpy as np
        import model_operation as model
        model.configure_model_runtime()
        import jax.numpy as jnp
        from jax import tree_map, tree_util
        from jaxley.optimize.utils import l2_norm
        import optax
        import context_codec as codec
        import fixed_coordinate_policy as policy
        import comparison_streamed_batch as streamed
        from source_bootstrap import initialize_fit
        from source_transition import source_transition
        self.np, self.jnp, self.tree_map, self.tree_util = np, jnp, tree_map, tree_util
        self.model, self.codec, self.policy = model, codec, policy
        self.streamed, self.transition, self.l2_norm, self.optax = streamed, source_transition, l2_norm, optax
        self.deadline, self.checkpoint_notice = deadline, checkpoint_notice
        self.check('before_frozen_initialization')
        bundle = initialize_fit(arrays, meta, morphology_prefix)
        self.__dict__.update(bundle)
        self.arrays, self.meta = arrays, meta
        self.history, self.updates = [], 0
        self.stats = {key: 0 for key in (
            'training_singletons_completed', 'last_training_batch_completed_rows',
            'completed_original_gradient_batches', 'last_global_mean_denominator',
            'validation_singletons_completed', 'last_validation_batch_completed_rows',
            'completed_original_validation_batches', 'test_singletons_completed')}
        self.initial_model_state = self.codec.encode_tree(self.states, np, tree_util, role='model_state')
        self.initial_context = self.codec.tree_witness((self.opt, self.states, self.optimizer_states), np, tree_util)
        self.validate('parameters', self.opt)
        self.validate('optimizer_state', self.optimizer_states)
        self.physical_parameters(self.opt)
        self.selected_snapshot_sha256 = None
        self.selected_predictions = None
        self.check('after_frozen_initialization')

    def check(self, stage):
        if time.monotonic() >= self.deadline:
            raise TimeoutError('full fit deadline at ' + stage)

    def validate(self, role, value):
        self.codec.encode_tree(value, self.np, self.tree_util, role=role)

    def model_state_unchanged(self):
        current = self.codec.encode_tree(self.states, self.np, self.tree_util, role='model_state')
        require(current == self.initial_model_state, 'fixed neuronal initial state mutated')

    def physical_parameters(self, parameters):
        self.validate('parameters', parameters)
        transforms = [self.static[name] for name in ('transform_params', 'transform_basal', 'transform_somatic')]
        physical = tuple(transform.forward(group) for transform, group in zip(transforms, parameters))
        self.validate('computed', physical)
        expected = self.np.asarray(transforms[2].forward([
            {'Na_gNa': self.jnp.asarray(float('-inf'), dtype=self.jnp.float64)}])[0]['Na_gNa'])
        actual = self.np.asarray(physical[2][0]['Na_gNa'])
        require(expected.shape == actual.shape == () and expected.dtype.str == actual.dtype.str == '<f8' and
                bool(self.np.isfinite(expected)) and 0.05 < float(expected) < 0.5 and
                expected.tobytes() == actual.tobytes(), 'unchanged finite physical boundary image')
        return physical

    def start_epoch(self, epoch):
        self.check('epoch_start')
        require(epoch == len(self.history), 'ordered production epoch')
        self.model_state_unchanged()

    def training_batches(self):
        for batch in self.dataloader:
            self.check('training_batch')
            yield int(batch[1].shape[0]), batch

    def step(self, batch):
        result = streamed_step(self.gradient, self.opt, self.optimizer_states, self.optimizers,
                              batch[1].numpy(), batch[2].numpy(), batch[3].numpy(), self.states,
                              np=self.np, jnp=self.jnp, tree_util=self.tree_util, tree_map=self.tree_map,
                              l2_norm=self.l2_norm, optax=self.optax, streamed_gradient=self.streamed.streamed_gradient,
                              source_transition=self.transition, check=self.check, stats=self.stats,
                              validate=self.validate)
        self.physical_parameters(result['parameters'])
        self.model_state_unchanged()
        self.opt, self.optimizer_states = result['parameters'], result['optimizer_states']
        self.updates += 1
        return {'loss': result['loss']}

    def validation_chunks(self):
        for batch in self.val_loader:
            currents = batch[1].numpy()
            prediction = self.streamed.streamed_prediction(self.predict, self.opt, currents,
                                                          np=self.np, check=self.check, stats=self.stats)
            require(bool(self.np.isfinite(prediction).all()), 'finite validation predictions')
            yield int(currents.shape[0]), prediction

    def validation_metric(self, chunks):
        self.check('global_validation_metric')
        predictions = self.np.concatenate(chunks, axis=0)
        require(predictions.shape == (3047, 147), 'complete validation before correlation')
        self.current_metric = self.model.masked_pearson(predictions, self.arrays['val_targets'],
                                                       self.arrays['mask'][self.val_ids])
        return self.current_metric['mean']

    def snapshot(self):
        # Exact source detachment expression; selected parameters never share buffers.
        snapshot = self.tree_map(lambda x: self.jnp.asarray(self.np.asarray(x).copy()), self.opt)
        self.validate('parameters', snapshot)
        self.selected_snapshot_sha256 = hashlib.sha256(self.codec.canonical(
            self.codec.encode_tree(snapshot, self.np, self.tree_util, role='parameters'))).hexdigest()
        return snapshot

    def record_epoch(self, record, snapshot, chunks):
        require(record['updates'] == self.updates and record['validation_mean'] == self.current_metric['mean'],
                'record matches complete scientific epoch')
        self.model_state_unchanged()
        if snapshot is not None:
            self.selected_predictions = self.np.concatenate(chunks, axis=0).copy(order='C')
        full_record = {**record, 'validation': self.current_metric}
        self.history.append(full_record)
        if self.checkpoint_notice is not None:
            self.checkpoint_notice(full_record)

    def final_test(self, selected_snapshot):
        self.model_state_unchanged()
        current_hash = hashlib.sha256(self.codec.canonical(self.codec.encode_tree(
            selected_snapshot, self.np, self.tree_util, role='parameters'))).hexdigest()
        require(current_hash == self.selected_snapshot_sha256, 'selected parameter snapshot stayed immutable')
        self.physical_parameters(selected_snapshot)
        test_ids = self.np.asarray(self.meta['splits']['test'], dtype=self.np.int64)
        predictions = streamed_test_prediction(self.predict, selected_snapshot, self.arrays['currents'][test_ids],
                                              np=self.np, check=self.check, stats=self.stats)
        self.model_state_unchanged()
        return 128, predictions
