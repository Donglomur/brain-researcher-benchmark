"""Convert one pinned original subject ZIP and pinned image metadata to safe NPY.

No fitting or assessment. Original source dictionaries are never candidate files.
One participant at a time; all80 test repeats and all4 training repeats retained
in mean formation. Internal row order still needs the declared source join audit.
"""
import argparse
import json
from pathlib import Path
import zipfile
import numpy as np
from source_io import verify_file, read_source_dictionary, descriptor, save_json
from metadata_core import PARTICIPANTS, validate_metadata, validate_archive_identity


def repeat_mean(block):
    if type(block) is not np.ndarray or block.ndim != 4 or block.dtype.kind != 'f' or not np.isfinite(block).all():
        raise ValueError('finite image/repeat/channel/time floating array required')
    with np.errstate(over='raise', invalid='raise'):
        result = np.mean(block, axis=1, dtype=np.float64)
    if not np.isfinite(result).all():raise ValueError('nonfinite mean')
    return result


def summarize_dictionary(value, output, partition):
    if set(value) != {'preprocessed_eeg_data', 'ch_names', 'times'}:
        raise ValueError('exact source EEG dictionary fields required')
    expected = (16540, 4, 17, 100) if partition == 'train' else (200, 80, 17, 100)
    data = value['preprocessed_eeg_data']
    if type(data) is not np.ndarray or data.shape != expected or data.dtype.str != '<f8':
        raise ValueError('exact original17-channel little-endianfloat64 EEG schema required')
    channels = value['ch_names']
    if isinstance(channels, np.ndarray):channels = channels.tolist()
    if type(channels) is not list or len(channels) != 17 or not all(type(x) is str and x for x in channels) or len(set(channels)) != 17:
        raise ValueError('17 unique source channel labels required')
    times = np.asarray(value['times'])
    if times.shape != (100,) or times.dtype.kind != 'f' or not np.isfinite(times).all() or not (np.diff(times) > 0).all():
        raise ValueError('100 finite strictly increasing source times required')
    means = np.lib.format.open_memmap(output, mode='w+', dtype='<f8', shape=(expected[0], 17, 100))
    for first in range(0, expected[0], 32):
        block = data[first:first + 32]
        averaged = repeat_mean(block)
        means[first:first + len(block)] = averaged
    means.flush();del means
    return {'channel_names': channels, 'times_seconds': times.tolist(), 'shape': [expected[0], 17, 100],
            'source_repeats': expected[1], 'units': 'released_noise_normalized_EEG_not_microvolts'}


def stage(archive, archive_pin, metadata_file, metadata_pin, participant, output):
    if participant not in PARTICIPANTS:raise ValueError('source participant01..10 required')
    validate_archive_identity(participant,archive_pin)
    verify_file(archive, archive_pin);verify_file(metadata_file, metadata_pin)
    with Path(metadata_file).open('rb') as stream:
        meta = validate_metadata(read_source_dictionary(stream, maximum_bytes=2 * 1024 * 1024))
    out = Path(output);out.mkdir(parents=False, exist_ok=False)
    save_json(out/'image_metadata.json', meta)
    coordinate = None
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        if len(names) != len(set(names)):raise ValueError('duplicate ZIP members')
        for partition, basename, bound in [('train', 'preprocessed_eeg_training.npy', 1_000_000_000), ('test', 'preprocessed_eeg_test.npy', 250_000_000)]:
            matches = [x for x in names if Path(x).name == basename and not x.endswith('/')]
            if len(matches) != 1:raise ValueError('exactly one source member per partition required')
            info = zf.getinfo(matches[0])
            if info.file_size <= 0 or info.file_size > bound or info.flag_bits & 1:raise ValueError('bounded unencrypted source member required')
            with zf.open(info) as stream:
                value = read_source_dictionary(stream, maximum_bytes=bound)
            c = summarize_dictionary(value, out/(partition+'_mean.npy'), partition)
            del value
            common = {k:c[k] for k in ['channel_names','times_seconds','units']}
            if coordinate is not None and common != coordinate:raise ValueError('train/test coordinate mismatch')
            coordinate = common
    save_json(out/'coordinates.json', coordinate)
    save_json(out/'STAGED.json', {'schema':'neural055-safe-staged-person-v1','participant':participant,
        'source_archive':archive_pin,'source_metadata':metadata_pin,
        'files':{name:descriptor(out/name,out) for name in ['train_mean.npy','test_mean.npy','image_metadata.json','coordinates.json']},
        'limitations':['Safe numeric staging does not independently validate event-to-image ordering. Operator join attestation is required for final packaging.','No source recording or preparation execution occurred merely by distributing this script.']})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['archive','archive-pin','metadata','metadata-pin','participant','output']:p.add_argument('--'+name,required=True)
    a=p.parse_args();stage(a.archive,json.loads(Path(a.archive_pin).read_text()),a.metadata,json.loads(Path(a.metadata_pin).read_text()),a.participant,a.output)


if __name__=='__main__':main()
