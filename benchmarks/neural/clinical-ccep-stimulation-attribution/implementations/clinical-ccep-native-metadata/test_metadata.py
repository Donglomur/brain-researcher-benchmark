"""Invented metadata controls only. No patient observations or native MATLAB run."""
import copy
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import validate_metadata as v


def hx(x):
    return struct.pack('>d', x).hex()


def md(start='0', samples='5', blocks='2'):
    return dict(acquisition_channel_number='7', start_sample=start, number_of_samples=samples,
                number_of_blocks=blocks, number_of_discontinuities='1',
                sampling_frequency_hex=hx(2048), units_conversion_factor_hex=hx(-0.25),
                units_description='uV', **{k+'_hex': hx(-1) for k in v.REAL_FIELDS[2:]})


def fixture():
    binding = {'schema': 'clinical-ccep-native-metadata-binding-v1', 'reader_commit': v.COMMIT,
               'recordings': [{'recording_key': 'invented-'+str(i), 'native_source_manifest_sha256': str(i)*64} for i in range(1,6)]}
    packets=[]
    for row in binding['recordings']:
        # Segment-relative index 0 is distinct from the very large channel sample coordinate.
        segment={'metadata': md(str(2**53+1)), 'indices': [
            {'start_sample':'0','start_time':str(-(2**63)+1), 'number_of_samples':'2','RED_block_flags':'1'},
            {'start_sample':'2','start_time':str(2**63-1), 'number_of_samples':'3','RED_block_flags':'0'}]}
        channel={'native_name':'invented-channel', 'number_of_segments':'1',
                 'earliest_start_time':str(-(2**63)), 'latest_end_time':str(2**63-1),
                 'metadata':md(str(2**53+1)), 'segments':[segment]}
        packets.append({'schema':'clinical-ccep-native-metadata-v1','reader_commit':v.COMMIT,
                        'recording_key':row['recording_key'], 'source_manifest_sha256':row['native_source_manifest_sha256'],
                        'number_of_time_series_channels':'1','number_of_video_channels':'0','channels':[channel]})
    return binding, packets


class Controls(unittest.TestCase):
    def test_hand_derived_exact_extent_and_signed_factor(self):
        binding, packets=fixture(); result=v.validate(binding,packets)
        segment=result['recordings_in_operator_order'][0]['channels'][0]['segments'][0]
        self.assertEqual(segment['declared_native_sample_start'], '9007199254740993')
        self.assertEqual(segment['declared_native_sample_end_exclusive'], '9007199254740998')
        self.assertEqual(segment['RED_discontinuity_flag_count'],1)
        self.assertEqual(segment['native_time_order_breaks'],0)
        self.assertEqual(segment['issues'],[])
        self.assertFalse(result['scientifically_qualified'])

    def test_integer_domain(self):
        for value in [2**53+1, 1.0, True, '01', '-0', '+1', '1e3', str(2**63), str(-(2**63)-1)]:
            with self.subTest(value=value), self.assertRaises(ValueError):v.integer(value)
        self.assertEqual(v.integer(str(-(2**63))),-(2**63))
        self.assertEqual(v.integer(str(2**63-1)),2**63-1)

    def test_full_five_recordings(self):
        binding, packets=fixture()
        with self.assertRaises(ValueError):v.validate(binding,packets[:-1])
        packets[-1]=copy.deepcopy(packets[0])
        with self.assertRaises(ValueError):v.validate(binding,packets)

    def test_source_binding(self):
        binding, packets=fixture();packets[0]['source_manifest_sha256']='a'*64
        with self.assertRaises(ValueError):v.validate(binding,packets)

    def test_index_completeness(self):
        binding, packets=fixture();packets[0]['channels'][0]['segments'][0]['indices'].pop()
        with self.assertRaises(ValueError):v.validate(binding,packets)

    def test_channel_and_segment_completeness(self):
        for field in ('number_of_time_series_channels','number_of_segments'):
            binding, packets=fixture()
            target=packets[0] if field.startswith('number_of_time') else packets[0]['channels'][0]
            target[field]='2'
            with self.assertRaises(ValueError):v.validate(binding,packets)

    def test_privacy_closed_fields(self):
        for target in ('packet','channel','segment','index','metadata'):
            binding, packets=fixture();p=packets[0];ch=p['channels'][0];seg=ch['segments'][0]
            value={'packet':p,'channel':ch,'segment':seg,'index':seg['indices'][0],'metadata':seg['metadata']}[target]
            value['subject_ID']='invented-forbidden'
            with self.assertRaises(ValueError):v.validate(binding,packets)

    def test_noncontiguous_indices_not_hidden(self):
        binding, packets=fixture();packets[0]['channels'][0]['segments'][0]['indices'][1]['start_sample']='3'
        report=v.validate(binding,packets)['recordings_in_operator_order'][0]['channels'][0]['segments'][0]
        self.assertIn('noncontiguous_or_empty_stored_sample_block',report['issues'])
        self.assertIn('segment_sample_count_disagrees_with_indices',report['issues'])
        self.assertEqual(report['blocks'],2)

    def test_channel_collision_is_not_alias(self):
        binding, packets=fixture();p=packets[0];ch=copy.deepcopy(p['channels'][0]);ch['native_name']='INVENTED-CHANNEL'
        p['channels'].append(ch);p['number_of_time_series_channels']='2'
        report=v.validate(binding,packets)['recordings_in_operator_order'][0]
        self.assertEqual(report['casefold_name_collisions'],1)
        self.assertEqual(report['duplicate_acquisition_numbers'],1)
        self.assertTrue(report['acquisition_order_ambiguous'])
        self.assertEqual(report['native_channels'],2)

    def test_frequency_and_units_no_entry_retained(self):
        binding, packets=fixture();meta=packets[0]['channels'][0]['segments'][0]['metadata']
        meta.update(sampling_frequency_hex=hx(-1), units_conversion_factor_hex=hx(0), number_of_discontinuities='-1')
        issues=v.validate(binding,packets)['recordings_in_operator_order'][0]['channels'][0]['segments'][0]['issues']
        self.assertIn('missing_or_invalid_segment_frequency',issues)
        self.assertIn('missing_or_invalid_segment_conversion_factor',issues)
        self.assertIn('declared_discontinuity_count_unknown',issues)

    def test_native_time_not_repaired(self):
        binding, packets=fixture();indices=packets[0]['channels'][0]['segments'][0]['indices']
        indices[1]['start_time']=indices[0]['start_time']
        result=v.validate(binding,packets)
        self.assertEqual(result['recordings_in_operator_order'][0]['channels'][0]['segments'][0]['native_time_order_breaks'],1)
        self.assertFalse(result['clock_offset_interpretation_established'])

    def test_binary64_bits_and_native_flag_domain(self):
        self.assertEqual(v.real('8000000000000000'),-0.0)
        self.assertEqual(v.real(hx(-0.25)),-0.25)
        with self.assertRaises(ValueError):v.real('0.25')
        binding, packets=fixture();packets[0]['channels'][0]['segments'][0]['indices'][0]['RED_block_flags']='256'
        with self.assertRaises(ValueError):v.validate(binding,packets)

    def test_duplicate_json_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.json';path.write_text('{"x":1,"x":2}')
            with self.assertRaises(ValueError):v.read_json(path)

    def test_complete_zero_channel_inventory_is_explicit(self):
        binding, packets=fixture();packets[0]['channels']=[];packets[0]['number_of_time_series_channels']='0'
        result=v.validate(binding,packets)
        self.assertTrue(result['recordings_in_operator_order'][0]['empty_time_series_inventory'])
        self.assertFalse(result['scientifically_qualified'])

    def test_complete_zero_segment_and_index_inventory(self):
        for kind in ('segments','indices'):
            binding, packets=fixture();channel=packets[0]['channels'][0]
            if kind=='segments':
                channel['segments']=[];channel['number_of_segments']='0'
                channel['metadata'].update(number_of_samples='0',number_of_blocks='0')
            else:
                channel['segments'][0]['indices']=[]
                channel['segments'][0]['metadata'].update(number_of_samples='0',number_of_blocks='0')
                channel['metadata'].update(number_of_samples='0',number_of_blocks='0')
            report=v.validate(binding,packets)['recordings_in_operator_order'][0]['channels'][0]
            if kind=='segments':self.assertIn('empty_segment_inventory',report['issues'])
            else:self.assertIn('empty_index_inventory',report['segments'][0]['issues'])

    def test_native_no_entry_sentinels_do_not_make_known_support(self):
        binding, packets=fixture();segment=packets[0]['channels'][0]['segments'][0]
        segment['indices']=[{'start_sample':'0','start_time':str(-(2**63)),
                             'number_of_samples':str(2**32-1),'RED_block_flags':'0'}]
        segment['metadata'].update(number_of_samples=str(2**32-1),number_of_blocks='1')
        report=v.validate(binding,packets)['recordings_in_operator_order'][0]['channels'][0]['segments'][0]
        self.assertEqual(report['unknown_index_sample_counts'],1)
        self.assertEqual(report['unknown_index_start_times'],1)
        self.assertEqual(report['known_index_samples_subtotal'],'0')
        self.assertIsNone(report['complete_index_derived_sample_end'])
        self.assertIn('index_sample_count_unknown',report['issues'])
        self.assertIn('index_start_time_unknown',report['issues'])

    def test_fifo_directory_and_symlink_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);fifo=d/'fifo';os.mkfifo(fifo)
            script='import sys; import validate_metadata as v; v.read_json(sys.argv[1])'
            result=subprocess.run([sys.executable,'-c',script,str(fifo)],cwd=Path(v.__file__).parent,
                                  capture_output=True,text=True,timeout=2)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('input file extent/type refused',result.stderr)
            with self.assertRaises(ValueError):v.read_json(d)
            normal=d/'normal';normal.write_text('{}');link=d/'link';link.symlink_to(normal)
            with self.assertRaises(ValueError):v.read_json(link)

    def test_real_cli_generated_only(self):
        binding, packets=fixture()
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);b=d/'binding.json';b.write_text(json.dumps(binding));paths=[]
            for i,p in enumerate(packets):
                path=d/f'packet{i}.json';path.write_text(json.dumps(p));paths.append(str(path))
            report=d/'report.json'
            result=subprocess.run([sys.executable,str(Path(v.__file__).resolve()),'--binding',str(b),'--packets',*paths,'--report',str(report)],capture_output=True,text=True,check=True)
            self.assertFalse(json.loads(result.stdout)['scientifically_qualified'])
            data=json.loads(report.read_text());self.assertEqual(len(data['packet_sha256_in_argument_order']),5)
            result=subprocess.run([sys.executable,str(Path(v.__file__).resolve()),'--binding',str(b),'--packets',*paths,'--report',str(report)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)


if __name__=='__main__':unittest.main()
