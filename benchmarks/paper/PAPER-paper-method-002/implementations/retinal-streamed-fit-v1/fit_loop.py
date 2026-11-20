"""Portable orchestration for the fixed streamed full-fit production schedule.

The runtime owns parameter/optimizer carry, fixed neuronal initialization,
scientific arithmetic, prediction arrays, and detached parameter snapshots.
This module owns ordering, exact counts, epoch records, and best-epoch selection.
The private schedule seam exists for small analytical controls only.
"""

from collections import namedtuple
import math


Schedule = namedtuple(
    "Schedule", ("epochs", "training_batch_sizes", "validation_chunk_sizes", "test_rows")
)
PRODUCTION_SCHEDULE = Schedule(
    epochs=21,
    training_batch_sizes=(256,) * 47 + (153,),
    validation_chunk_sizes=(1024, 1024, 999),
    test_rows=128,
)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _validate_schedule(schedule):
    _require(type(schedule) is Schedule, "fit schedule must use the immutable Schedule type")
    _require(type(schedule.epochs) is int and schedule.epochs > 0, "fit epoch count must be positive")
    _require(type(schedule.test_rows) is int and schedule.test_rows > 0, "fit test row count must be positive")
    for sizes in (schedule.training_batch_sizes, schedule.validation_chunk_sizes):
        _require(type(sizes) is tuple and len(sizes) > 0, "fit chunk sizes must be nonempty tuples")
        _require(all(type(size) is int and size > 0 for size in sizes), "fit chunk sizes must be positive integers")


def _sized_payloads(items, expected_sizes, phase):
    """Reject an extra or wrongly sized item before its scientific operation."""
    count = 0
    for index, item in enumerate(items):
        _require(index < len(expected_sizes), phase + " yielded too many chunks")
        _require(type(item) is tuple and len(item) == 2, phase + " requires (row_count, payload) tuples")
        rows, payload = item
        _require(type(rows) is int and rows == expected_sizes[index], phase + " chunk row count mismatch")
        count += 1
        yield payload
    _require(count == len(expected_sizes), phase + " yielded too few chunks")


def _finite_float(value, message):
    _require(type(value) is float and math.isfinite(value), message)
    return value


def _run_loop(runtime, schedule):
    """Run an explicit schedule; this private seam is for analytical controls.

    Runtime protocol:
      start_epoch(epoch_zero_based)
      training_batches() -> iterable of (row_count, opaque_batch)
      step(opaque_batch) -> exactly {"loss": finite Python float}
      validation_chunks() -> iterable of (row_count, opaque_predictions)
      validation_metric(tuple_of_predictions) -> finite Python float global mean
      snapshot() -> non-None, detached selected parameters
      record_epoch(record, new_selected_snapshot_or_None, tuple_of_predictions)
      final_test(selected_snapshot) -> (row_count, opaque_predictions)

    The runtime computes the validation metric globally over all supplied
    chunks exactly once per epoch. It may retain its complete site-wise metric
    for record_epoch. The runtime must detach snapshot leaves from all later
    parameter updates and must preserve that snapshot through record_epoch.
    """
    _validate_schedule(schedule)
    updates_per_epoch = len(schedule.training_batch_sizes)
    expected_updates = schedule.epochs * updates_per_epoch
    updates = 0
    epochs_completed = 0
    best_mean = -1.0
    best_epoch = None
    best_snapshot = None

    for epoch in range(schedule.epochs):
        runtime.start_epoch(epoch)
        epoch_loss = 0.0
        batches = _sized_payloads(runtime.training_batches(), schedule.training_batch_sizes, "training")
        for batch in batches:
            step = runtime.step(batch)
            _require(type(step) is dict and set(step) == {"loss"}, "fit step must return exactly its batch mean loss")
            loss = _finite_float(step["loss"], "fit batch mean loss must be a finite Python float")
            # Preserve ordered summation of batch means, including the short tail.
            epoch_loss += loss
            _require(math.isfinite(epoch_loss), "fit epoch sum of batch means must remain finite")
            updates += 1
        _require(updates == (epoch + 1) * updates_per_epoch, "fit epoch update count mismatch")

        predictions = tuple(_sized_payloads(
            runtime.validation_chunks(), schedule.validation_chunk_sizes, "validation"
        ))
        validation_mean = _finite_float(
            runtime.validation_metric(predictions), "fit global validation mean must be a finite Python float"
        )
        selected = validation_mean > best_mean
        new_snapshot = None
        if selected:
            new_snapshot = runtime.snapshot()
            _require(new_snapshot is not None, "fit selected snapshot must not be None")
            best_snapshot = new_snapshot
            best_mean = validation_mean
            best_epoch = epoch

        record = {
            "epoch_zero_based": epoch,
            "updates": updates,
            "epoch_sum_of_batch_mean_L1": epoch_loss,
            "validation_mean": validation_mean,
            "selected": selected,
        }
        runtime.record_epoch(record, new_snapshot, predictions)
        epochs_completed += 1

    _require(epochs_completed == schedule.epochs and updates == expected_updates, "fit final epoch/update count mismatch")
    _require(best_snapshot is not None and best_epoch is not None, "fit has no validation mean strictly greater than -1.0")
    final_test = runtime.final_test(best_snapshot)
    _require(type(final_test) is tuple and len(final_test) == 2, "fit final test requires (row_count, predictions)")
    test_rows, test_predictions = final_test
    _require(type(test_rows) is int and test_rows == schedule.test_rows, "fit final test row count mismatch")
    return {
        "schema": "jaxley-streamed-full-fit-loop-v1",
        "epochs_completed": epochs_completed,
        "updates": updates,
        "training_rows_per_epoch": sum(schedule.training_batch_sizes),
        "validation_rows_per_epoch": sum(schedule.validation_chunk_sizes),
        "test_rows": test_rows,
        "best_epoch_zero_based": best_epoch,
        "best_validation_mean": best_mean,
        "best_snapshot": best_snapshot,
        "test_predictions": test_predictions,
    }


def run_production(runtime):
    """Run the fixed 21-epoch, 1,008-update fit without a schedule override."""
    result = _run_loop(runtime, PRODUCTION_SCHEDULE)
    _require(
        result["epochs_completed"] == 21
        and result["updates"] == 1008
        and result["training_rows_per_epoch"] == 12185
        and result["validation_rows_per_epoch"] == 3047
        and result["test_rows"] == 128,
        "fit production schedule count mismatch",
    )
    return result
