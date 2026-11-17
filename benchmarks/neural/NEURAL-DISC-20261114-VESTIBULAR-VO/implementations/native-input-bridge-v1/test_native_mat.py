"""Generated complete-tree/native-loader controls; no authentic MAT access."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import types
import unittest

import numpy as np
from scipy import io as sio

import native_mat as n


def fixture(path,compressed=True):
    neurons=np.empty((1,49),dtype=[('neuronid',object),('spikes',object)])
    for index in range(49):
        neurons[0,index]['neuronid']=np.array([[index+1]],dtype=np.int64)
        neurons[0,index]['spikes']=np.array([[index,index+2,index+4]],dtype=np.int32)
    pairs=np.arange(70,dtype=np.int16).reshape(35,2)
    cells=np.empty((2,2),dtype=object)
    cells[0,0]=neurons;cells[1,0]=np.empty((0,3));cells[0,1]=pairs
    cells[1,1]=np.array([['private generated label']],dtype='U23')
    sio.savemat(path,{'records':cells,'tail':np.array([[9876543210123457]],dtype=np.int64)},
                appendmat=False,do_compression=compressed,oned_as='row')
    body=path.read_bytes()
    return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'md5':hashlib.md5(body).hexdigest()}


class OriginalReaderControls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='vo-native-generated-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.path=self.root/'generated.mat'
        self.pin=fixture(self.path)

    def load(self,**kwargs):
        stream=io.BytesIO();state={}
        document=n.load_complete(self.path,self.pin,stream,diagnostics=state,**kwargs)
        return document,[json.loads(line) for line in stream.getvalue().splitlines()],state

    def test_complete49_cells_all_top_variables_and_Fortran_paths(self):
        doc,rows,state=self.load()
        self.assertEqual([r['name'] for r in doc.top_variables],['records','tail'])
        neuron_paths=[row['path'] for row in rows[1:] if row['path'][-1]=='neuronid']
        self.assertEqual(len(neuron_paths),49)
        self.assertEqual(neuron_paths[0],['records',{'index':[0,0]},{'index':[0,0]},'neuronid'])
        self.assertEqual(neuron_paths[-1],['records',{'index':[0,0]},{'index':[0,48]},'neuronid'])
        self.assertEqual(state['nodes'],len(rows)-1)
        self.assertTrue(state['complete_nested_traversal'])
        self.assertFalse(doc.census_summary['biological_membership_verified'])
        self.assertFalse(doc.census_summary['historical_Docker_inventory_qualification_claimed'])
        self.assertNotIn('9876543210123457',json.dumps(rows))

    def test_precise_field_resolution_preserves_orientation(self):
        doc,_,_=self.load()
        path=['records',{'index':[0,0]},{'index':[0,48]},'spikes']
        vector=n.resolve(doc,path)
        self.assertEqual(vector.shape,(1,3))
        np.testing.assert_array_equal(vector,[[48,50,52]])
        self.assertEqual(n.resolve(doc,['records',{'index':[1,0]}]).shape,(0,3))
        for bad in [['records',{'index':[0]}],['records',{'index':[0,0]},{'index':[48,0]}],
                    ['records',{'index':[0,0]},'spikes'],['missing']]:
            with self.subTest(path=bad),self.assertRaises(ValueError):
                n.resolve(doc,bad)

    def test_late_original_change_rejects_before_any_census_output(self):
        raw=self.path.read_bytes();self.path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
        output=io.BytesIO();state={}
        with self.assertRaisesRegex(ValueError,'checksum'):
            n.load_complete(self.path,self.pin,output,diagnostics=state)
        self.assertEqual(output.getvalue(),b'')
        self.assertFalse(state['original_hash_complete'])
        self.assertEqual(state['original_bytes_delivered'],self.pin['bytes'])

    def test_whole_reader_budget_is_preventive(self):
        output=io.BytesIO();state={}
        with self.assertRaisesRegex(ValueError,'reader_budget'):
            n.load_complete(self.path,self.pin,output,n.Limits(read_bytes=128),diagnostics=state)
        self.assertEqual(output.getvalue(),b'')
        self.assertEqual(state['original_bytes_delivered'],0)

    def test_decoded_node_and_output_caps_fail_without_complete_claim(self):
        for limits in [n.Limits(nodes=5),n.Limits(census_bytes=128),n.Limits(decoded_array_bytes=32)]:
            output=io.BytesIO();state={}
            with self.subTest(limits=limits),self.assertRaises(RuntimeError):
                n.load_complete(self.path,self.pin,output,limits,diagnostics=state)
            self.assertFalse(state['complete_nested_traversal'])
            self.assertTrue(state['original_hash_complete'])
            self.assertTrue(state['all_variables_loaded'])

    def test_uncompressed_same_complete_source_structure(self):
        self.pin=fixture(self.path,compressed=False)
        doc,rows,_=self.load()
        self.assertEqual(len(doc.values),2)
        self.assertEqual(len([row for row in rows[1:] if row['path'][-1]=='spikes']),49)

    def test_post_read_identity_change_is_detected(self):
        stream=n.OriginalStream(self.path,self.pin,3*self.pin['bytes']+1024)
        self.addCleanup(stream.close)
        stream.authenticate()
        self.path.write_bytes(self.path.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'identity_changed'):
            stream.verify_identity()

    def test_unselected_header_family_is_refused(self):
        body=bytearray(self.path.read_bytes());body[124:126]=b'\x00\x02'
        self.path.write_bytes(body)
        descriptor={'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'md5':hashlib.md5(body).hexdigest()}
        with self.assertRaisesRegex(ValueError,'only_selected'):
            n.load_complete(self.path,descriptor,io.BytesIO())


class PreservedTenControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=n.HERE/'reused/offline_controls.py'
        body=n.read_source(path,'e2406ce683c7adada953c75d37e979b3e65e0a1b695870feca3124ea63c0f09b')
        module=types.ModuleType('vestibular_original_generated_controls');module.__file__=str(path)
        exec(compile(body,str(path),'exec'),module.__dict__)
        np_,sio_,sparse=n.numerical_environment()
        cls.ledger=module.run_controls(n.parser_module(),np_,sio_,sparse)


def _preserved_case(index):
    def test(self):
        row=self.ledger['ledger'][index]
        self.assertEqual(row['id'],'VO-CENSUS-%02d'%(index+1))
        self.assertTrue(row['completed'])
        self.assertEqual(row['status'],'pass',row)
        self.assertFalse(self.ledger['authentic_data_accessed'])
    return test


for _index in range(10):
    setattr(PreservedTenControls,'test_preserved_%02d'%(_index+1),_preserved_case(_index))


if __name__=='__main__':
    unittest.main()
