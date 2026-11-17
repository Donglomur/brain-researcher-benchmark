#!/usr/bin/env python3
"""Full-size generated allocation control; no neural inputs or model execution."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import time


def rss_stage(name):
    current = int(subprocess.check_output(['ps','-p',str(os.getpid()),'-o','rss='],text=True).strip()) * 1024
    return dict(stage=name,current_rss_bytes=current,
                maxrss_native_units=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def run(source, report):
    import numpy as np
    text = source.read_text()
    node = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == 'eval_nlb')
    function_text = ast.get_source_segment(text,node)
    original = 'eval_predictions = np.array(eval_predictions).mean(axis=0)\n    training_predictions = np.array(training_predictions).mean(axis=0)'
    if function_text.count(original) != 1:
        raise ValueError('Original repeat aggregation differs')
    if report.exists():
        raise ValueError('Refuse to overwrite allocation evidence')
    wall = time.monotonic()
    eval_predictions = []
    training_predictions = []
    # The original chunk-local particle mean is (trial, neuron, time), then
    # transposed to (trial, time, neuron); concatenate preserves this layout.
    probe = np.concatenate([np.empty((2, 182, 45), dtype=np.float32).transpose(0, 2, 1),
                            np.empty((3, 182, 45), dtype=np.float32).transpose(0, 2, 1)])
    expected_strides = (182 * 45 * 4, 4, 45 * 4)
    if probe.strides != expected_strides:
        raise ValueError('Unexpected source NumPy concatenation layout')
    for i in range(32):
        Xs_t = np.empty((2295, 182, 45), dtype=np.float32).transpose(0, 2, 1)
        Xs_e = np.empty((574, 182, 45), dtype=np.float32).transpose(0, 2, 1)
        for array in (Xs_t, Xs_e):
            array.fill(i + 1)
            array[:, ::3, ::7] *= np.float32(-0.125)
            if array.strides != expected_strides:
                raise ValueError('Unexpected repeat layout')
        del array
        training_predictions_i = Xs_t
        training_predictions.append(training_predictions_i)
        eval_predictions_i = Xs_e
        eval_predictions.append(eval_predictions_i)
    before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    retained_bytes = sum(a.nbytes for a in training_predictions + eval_predictions)
    stages = [rss_stage('all_repeats_retained')]
    # These two lines and their order are exactly the authenticated author source.
    eval_predictions = np.array(eval_predictions).mean(axis=0)
    stages.append(rss_stage('eval_mean_complete'))
    training_predictions = np.array(training_predictions).mean(axis=0)
    stages.append(rss_stage('train_mean_complete'))
    assert training_predictions.shape == (2295, 45, 182)
    assert eval_predictions.shape == (574, 45, 182)
    assert training_predictions.dtype == eval_predictions.dtype == np.float32
    for array in (training_predictions, eval_predictions):
        assert array[0, 1, 1] == np.float32(16.5)
        assert array[-1, 0, 0] == np.float32(-2.0625)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result = dict(schema='smc_full_repeat_allocation_control_v1',
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        control_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        generated_only=True, model_executed=False, target_access=False,
        repeats=32, train_shape=[2295,45,182], eval_shape=[574,45,182],
        dtype='float32', repeat_strides=list(expected_strides),
        retained_repeat_bytes=retained_bytes,
        rss_stages=stages,
        alias_order='Xs_t/training_predictions_i and Xs_e/eval_predictions_i retain last repeat; eval list replaced by mean before train stack.',
        original_aggregation=original, arithmetic_checks_passed=True,
        peak_before_aggregation_native_units=before,
        maxrss_native_units=usage.ru_maxrss, cpu_seconds=usage.ru_utime+usage.ru_stime,
        wall_seconds=time.monotonic()-wall)
    report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    resource.setrlimit(resource.RLIMIT_CPU,(60,60))
    run(a.source,a.report)
