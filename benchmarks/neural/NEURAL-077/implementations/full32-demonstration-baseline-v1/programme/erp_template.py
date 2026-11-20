"""Deterministic four-demonstration event-label reference programme.

Only the four visible demonstrations fit the normalization, centroids and
diagonal variance. Released waveforms are already baseline corrected. The
query and opaque identities never fit a parameter. Probabilities are an
uncalibrated, equal-prior mapping, not a physiological P3-presence estimate.
"""
from __future__ import annotations

import json
import math
import re
import struct
import sys

PROMPT_CAP = 196608
RESPONSE_CAP = 4096
PREFIX = struct.Struct('!I')
PROGRAMME_PERMISSION = ('Numerical tools and candidate code execution are allowed for this query. '
                        'Do not use external retrieval, other files, or memory from other query trials.')
DIRECT_PERMISSION = 'Do not use tools, code execution, external retrieval, files, or memory from other query trials.'
EXPECTED_CONFIG = {'schema': 'erp-four-demo-template-v1', 'noise_samples': 256,
                   'feature_start': 256, 'bin_samples': 32, 'noise_floor_ratio': 1e-6,
                   'variance_shrinkage': 0.5, 'variance_ridge': 0.03125,
                   'temperature': 1.0, 'logit_clip': 12.0}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    need(type(value) in (int, float), 'Nonboolean numeric waveform required')
    try:
        result = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError('Representable finite waveform required') from error
    need(math.isfinite(result), 'Finite waveform/arithmetic required')
    return result


def unique(items):
    result = {}
    for key, value in items:
        need(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def nonfinite(_value):
    raise ValueError('Nonfinite JSON constant')


def waveform(value):
    need(type(value) is list and len(value) == 2 and
         all(type(channel) is list and len(channel) == 1024 for channel in value),
         'Complete two-channel 1024-sample waveform required')
    return [[finite(sample) for sample in channel] for channel in value]


def validate_records(demonstrations, query):
    need(type(demonstrations) is list and len(demonstrations) == 4, 'Exactly four demonstrations required')
    seen = set(); labels = []; waves = []
    for row in demonstrations:
        need(type(row) is dict and set(row) == {'trial_id', 'target', 'channels'}, 'Exact demonstration fields')
        identifier = row['trial_id']
        need(type(identifier) is str and 0 < len(identifier) <= 48 and identifier not in seen,
             'Unique bounded demonstration identities')
        seen.add(identifier)
        need(type(row['target']) is int and row['target'] in (0, 1), 'Binary nonboolean demonstration label')
        labels.append(row['target']); waves.append(waveform(row['channels']))
    need(set(labels) == {0, 1}, 'Both classes must be present among four demonstrations')
    need(type(query) is dict and set(query) == {'trial_id', 'channels'}, 'Exact unlabeled query fields')
    need(type(query['trial_id']) is str and re.fullmatch(r'q-[0-9a-f]{32}', query['trial_id']) and
         query['trial_id'] not in seen, 'Distinct opaque full32 query identity')
    return waves, labels, waveform(query['channels'])


def parse_prompt(text):
    """Recognize proven JSON shapes, without guessing human prose delimiters.

    Successful JSON values are consumed whole, so their nested channel arrays
    cannot become extra inputs. Malformed scientific values cannot supply the
    required pair. Nonfinite constants and duplicate keys always refuse.
    """
    need(type(text) is str and 0 < len(text.encode('utf-8')) <= PROMPT_CAP, 'One complete bounded UTF-8 prompt')
    need(text.count(PROGRAMME_PERMISSION) == 1 and DIRECT_PERMISSION not in text,
         'Exact programme condition permission required')
    decoder = json.JSONDecoder(object_pairs_hook=unique, parse_constant=nonfinite)
    demonstrations = query = None
    demo_position = query_position = None
    position = attempts = values = 0
    while position < len(text):
        starts = [index for index in (text.find('[', position), text.find('{', position)) if index >= 0]
        if not starts:
            break
        start = min(starts); attempts += 1
        need(attempts <= 128, 'Bounded JSON candidate scan')
        try:
            value, finish = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            position = start + 1
            continue
        except RecursionError as error:
            raise ValueError('Bounded JSON nesting required') from error
        values += 1; need(values <= 64, 'Bounded complete JSON values')
        position = finish
        if type(value) is list and any(type(row) is dict and 'channels' in row for row in value):
            need(demonstrations is None, 'Ambiguous or duplicate demonstration lists')
            need(len(value) == 4 and all(type(row) is dict and
                 set(row) == {'trial_id', 'target', 'channels'} for row in value), 'Exact four-demo list')
            demonstrations, demo_position = value, start
        elif type(value) is dict and 'channels' in value:
            need(query is None and set(value) == {'trial_id', 'channels'}, 'Ambiguous, labeled or malformed query')
            query, query_position = value, start
    need(demonstrations is not None and query is not None and demo_position < query_position,
         'One complete demonstration list followed by one complete query required')
    validate_records(demonstrations, query)
    return demonstrations, query


def stable_mean(values):
    """Scale before summation; this does not fit an additional parameter."""
    values = tuple(values)
    need(bool(values), 'Nonempty arithmetic mean')
    peak = max(abs(value) for value in values)
    if peak == 0:
        return 0.0
    return finite(peak * math.fsum(value / peak / len(values) for value in values))


def stable_rms(values):
    values = tuple(values)
    need(bool(values), 'Nonempty RMS')
    peak = max(abs(value) for value in values)
    if peak == 0:
        return 0.0
    return finite(peak * math.sqrt(math.fsum((value / peak) ** 2 / len(values) for value in values)))


def validate_config(config):
    # The one selected reference method is not a hidden hyperparameter search.
    try:
        received = dict(config)
    except (ValueError, TypeError) as error:
        raise ValueError('Frozen method configuration required') from error
    need(received == EXPECTED_CONFIG and all(type(received[key]) is type(expected)
         for key, expected in EXPECTED_CONFIG.items()), 'Configuration differs from the frozen reference method')
    return received


def predict(demonstrations, query, config):
    """Return an uncalibrated probability; no files, state, fitting on query, or random numbers."""
    settings = validate_config(config)
    waves, labels, query_wave = validate_records(demonstrations, query)
    # Working in units of the demonstration maximum prevents a subnormal RMS
    # floor from underflowing. It is algebraically the declared RMS scaling;
    # the query never contributes to this unit or any fitted statistic.
    unit = max(abs(value) for wave in waves for channel in wave for value in channel)
    unit = unit if unit > 0 else 1.0
    normalized = [[[value / unit for value in channel] for channel in wave] for wave in waves]
    global_rms = stable_rms(value for wave in normalized for channel in wave for value in channel)
    scales = []
    for channel in range(2):
        noise = stable_rms(value for wave in normalized for value in wave[channel][:settings['noise_samples']])
        scale = max(noise, settings['noise_floor_ratio'] * global_rms)
        scales.append(scale if scale > 0 else 1.0)

    def features(wave, normalized_input=False):
        result = []
        for channel in range(2):
            for start in range(settings['feature_start'], 1024, settings['bin_samples']):
                mean = stable_mean(wave[channel][start:start + settings['bin_samples']])
                mean = mean if normalized_input else finite(mean / unit)
                result.append(finite(mean / scales[channel]))
        need(len(result) == 48, 'Fixed 48-feature geometry')
        return result

    training = [features(wave, True) for wave in normalized]
    centroids = [[stable_mean(row[column] for row, label in zip(training, labels) if label == target)
                  for column in range(48)] for target in (0, 1)]
    pooled = [finite(math.fsum((row[column] - centroids[label][column]) ** 2
                              for row, label in zip(training, labels)) / 2.0) for column in range(48)]
    global_variance = stable_mean(pooled)
    variances = [finite((1 - settings['variance_shrinkage']) * value +
                        settings['variance_shrinkage'] * global_variance + settings['variance_ridge']) for value in pooled]
    observed = features(query_wave)
    terms = []
    for value, mean0, mean1, variance in zip(observed, centroids[0], centroids[1], variances):
        # Equivalent D0-D1 without two enormous, nearly equal squared distances.
        delta = mean1 - mean0
        terms.append(0.0 if delta == 0 else finite((delta / variance) * ((value - mean0) + (value - mean1))))
    logit = finite(stable_mean(terms) / (2 * settings['temperature']))
    logit = max(-settings['logit_clip'], min(settings['logit_clip'], logit))
    probability = 1.0 / (1.0 + math.exp(-logit))
    need(math.isfinite(probability) and 0 < probability < 1, 'Finite bounded reference probability')
    return probability


def answer(text, config):
    demonstrations, query = parse_prompt(text)
    return {'trial_id': query['trial_id'], 'target_probability': predict(demonstrations, query, config)}


def read_exact(stream, size):
    parts = []; received = 0
    while received < size:
        part = stream.read(size - received)
        need(part, 'Truncated input frame')
        parts.append(part); received += len(part)
    return b''.join(parts)


def main():
    from neural077_config import CONFIG
    header = read_exact(sys.stdin.buffer, PREFIX.size)
    size = PREFIX.unpack(header)[0]
    need(0 < size <= PROMPT_CAP, 'Complete bounded frame length')
    text = read_exact(sys.stdin.buffer, size).decode('utf-8')
    need(sys.stdin.buffer.read(1) == b'', 'Exactly one input frame followed by EOF')
    result = answer(text, CONFIG)
    body = json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    need(0 < len(body) <= RESPONSE_CAP, 'Bounded original response')
    sys.stdout.buffer.write(PREFIX.pack(len(body)) + body); sys.stdout.buffer.flush()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
