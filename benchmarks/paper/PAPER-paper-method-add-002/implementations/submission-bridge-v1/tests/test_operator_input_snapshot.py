"""Generated immutable operator-input controls; no original data or fits."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import numpy as np

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('slicetca_snapshot_bridge',HERE.parent/'bridge.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
WRITTEN=0


def save_bytes(path,payload):
 global WRITTEN
 WRITTEN+=len(payload)
 if WRITTEN>65536:raise AssertionError('generated fixture cumulative write bound exceeded')
 path.write_bytes(payload)
 return {'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}


def npy(value,version=(1,0)):
 stream=io.BytesIO();np.lib.format.write_array(stream,np.asarray(value),version=version,allow_pickle=False);return stream.getvalue()


class OperatorInputSnapshot(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=HERE);self.root=Path(self.tmp.name)
  self.addCleanup(self.tmp.cleanup)

 def capture(self,value,version=(1,0)):
  path=self.root/'input.npy';record=save_bytes(path,npy(value,version))
  return path,record

 def load(self,path,record,shape):
  return b._captured_numeric_npy(path,shape,expected_bytes=record['bytes'],expected_sha256=record['sha256'])

 def test_c_and_fortran_v1_v2_and_endian_preserve_values(self):
  for version,value in [((1,0),np.arange(6,dtype='<f4').reshape(2,3)),((2,0),np.asfortranarray(np.arange(6,dtype='>f8').reshape(2,3)))]:
   with self.subTest(version=version):
    path,record=self.capture(value,version);result=self.load(path,record,(2,3))
    np.testing.assert_array_equal(result,value)
    self.assertEqual(result.dtype.str,value.dtype.str)
    self.assertFalse(result.flags.writeable)

 def test_hash_is_checked_before_header_parser(self):
  path,record=self.capture(np.arange(3,dtype=float));record['sha256']='f'*64
  with mock.patch.object(b.np.lib.format,'read_magic',side_effect=AssertionError('must not parse')) as parser:
   with self.assertRaisesRegex(ValueError,'identity'):self.load(path,record,(3,))
   parser.assert_not_called()

 def test_replacement_after_hash_does_not_change_decoded_bytes(self):
  original=np.arange(3,dtype=float);path,record=self.capture(original)
  actual_magic=b.np.lib.format.read_magic
  def replace_then_parse(stream):
   save_bytes(path,npy(original+100))
   return actual_magic(stream)
  with mock.patch.object(b.np.lib.format,'read_magic',side_effect=replace_then_parse):result=self.load(path,record,(3,))
  np.testing.assert_array_equal(result,original)
  self.assertEqual(path.read_bytes(),npy(original+100))

 def test_returned_value_cannot_follow_mutation_or_be_made_writeable(self):
  original=np.arange(3,dtype=float);path,record=self.capture(original);result=self.load(path,record,(3,))
  save_bytes(path,npy(original+20));np.testing.assert_array_equal(result,original)
  with self.assertRaises(ValueError):result.setflags(write=True)
  with self.assertRaises(ValueError):result[0]=4

 def test_unexpected_shape_and_primitive_types_rejected(self):
  for value,shape in [(np.arange(4).reshape(2,2),(4,)),(np.ones(3,dtype=[('field','f8')]),(3,)),(np.ones(3,dtype=complex),(3,))]:
   path,record=self.capture(value)
   with self.assertRaisesRegex(ValueError,'shape/primitive'):self.load(path,record,shape)
  # Object header with inert fake bytes: it must fail before any pickle or array loading.
  stream=io.BytesIO();np.lib.format.write_array_header_1_0(stream,{'shape':(3,),'fortran_order':False,'descr':'|O'})
  payload=stream.getvalue()+b'not-pickle';path=self.root/'object.npy';record=save_bytes(path,payload)
  with mock.patch.object(b.np,'load',side_effect=AssertionError('no np.load')):
   with self.assertRaisesRegex(ValueError,'shape/primitive'):self.load(path,record,(3,))

 def test_nonfinite_rejected(self):
  path,record=self.capture(np.array([0.,np.inf]))
  with self.assertRaisesRegex(ValueError,'nonfinite'):self.load(path,record,(2,))

 def test_trailing_and_short_payloads_rejected(self):
  value=np.arange(3,dtype=float)
  for payload in (npy(value)+b'junk',npy(value)[:-1]):
   path=self.root/'extent.npy';record=save_bytes(path,payload)
   with self.assertRaisesRegex(ValueError,'decoded extent'):self.load(path,record,(3,))

 def test_symlink_and_oversized_record_rejected_before_read(self):
  path,record=self.capture(np.arange(3,dtype=float));link=self.root/'link.npy';link.symlink_to(path)
  with self.assertRaises(OSError):self.load(link,record,(3,))
  with mock.patch.object(b.os,'open',side_effect=AssertionError('must not open')) as opening:
   with self.assertRaisesRegex(ValueError,'extent/hash'):b._captured_numeric_npy(path,(3,),expected_bytes=10**12,expected_sha256=record['sha256'])
   opening.assert_not_called()

 def test_fifo_is_refused_without_waiting_for_a_writer(self):
  path=self.root/'input.fifo';b.os.mkfifo(path)
  with self.assertRaisesRegex(ValueError,'file extent/type'):b._captured_numeric_npy(path,(3,))

 def tiny_bank(self,indices=None):
  # The production entrypoint is exercised with a generated reduced support,
  # not an authentic bank or an alternative admitted task shape.
  shapes={'neural.npy':(3,2,4),'movement.npy':(4,3,2),'target_angle.npy':(3,),
          'target_pos.npy':(3,2),'condition.npy':(3,),'source_trial_indices.npy':(3,)}
  files={};values={}
  for name,shape in shapes.items():
   value=np.arange(int(np.prod(shape)),dtype=float).reshape(shape)
   if name=='source_trial_indices.npy':value=np.arange(3,dtype=np.int64) if indices is None else indices
   files[name]=save_bytes(self.root/name,npy(value));values[name[:-4]]=value
  manifest={'task_id':b.TASK,'producer_sha256':b.PRODUCER_SHA,'status':'complete_original_array_preparation_only','files':files}
  record=save_bytes(self.root/'COMPLETE.json',b.canonical(manifest))
  return shapes,values,record['sha256']

 def test_complete_bank_uses_only_captured_values_and_preserves_manifest(self):
  shapes,expected,sha=self.tiny_bank()
  with mock.patch.object(b,'PREPARED_SHAPES',shapes),mock.patch.object(b,'SHAPE',(3,2,4)),mock.patch.object(b.np,'load',side_effect=AssertionError('no reopen/np.load')):
   bank=b.load_prepared_bank(self.root,sha)
  self.assertEqual(bank['manifest_sha256'],sha)
  self.assertEqual(set(bank),set(expected)|{'manifest_sha256'})
  for name,value in expected.items():
   np.testing.assert_array_equal(bank[name],value);self.assertFalse(bank[name].flags.writeable)
  save_bytes(self.root/'movement.npy',npy(expected['movement']+50))
  np.testing.assert_array_equal(bank['movement'],expected['movement'])

 def test_bank_preserves_exact_source_row_order_and_identity(self):
  shapes,_,sha=self.tiny_bank(np.array([0,2,1],dtype=np.int64))
  with mock.patch.object(b,'PREPARED_SHAPES',shapes),mock.patch.object(b,'SHAPE',(3,2,4)):
   with self.assertRaisesRegex(ValueError,'source index order'):b.load_prepared_bank(self.root,sha)
   with self.assertRaisesRegex(ValueError,'manifest identity'):b.load_prepared_bank(self.root,'0'*64)

 def test_mask_semantics_and_immutable_returned_storage(self):
  mask=np.array([[[1,0],[0,1]]],dtype=np.uint8);path=self.root/'cell.npy';save_bytes(path,npy(mask))
  plan={'reconstruction_cells':[{'id':'cell','training_mask_sha256':b.mask_digest(mask)}]}
  with mock.patch.object(b,'SHAPE',mask.shape),mock.patch.object(b.np,'load',side_effect=AssertionError('no mmap')):
   result=b.load_operator_masks(self.root,plan)['cell']
   save_bytes(path,npy(1-mask))
   np.testing.assert_array_equal(result,mask);self.assertFalse(result.flags.writeable)
   with self.assertRaisesRegex(ValueError,'mask content'):b.load_operator_masks(self.root,plan)

 def test_updated_decoder_audit_dependency_loads_actual_bridge(self):
  path=HERE.parent.parent/'decoder-audit-v1/audit_packet.py'
  spec=importlib.util.spec_from_file_location('slicetca_snapshot_audit',path)
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  self.assertEqual(module.BRIDGE_SHA256,hashlib.sha256((HERE.parent/'bridge.py').read_bytes()).hexdigest())
  self.assertTrue(callable(module.b._captured_numeric_npy))

 @classmethod
 def tearDownClass(cls):
  print(json.dumps({'generated_fixture_cumulative_written_bytes':WRITTEN,'authentic_data_read':False,'fits':0}))


if __name__=='__main__':unittest.main(verbosity=2)
