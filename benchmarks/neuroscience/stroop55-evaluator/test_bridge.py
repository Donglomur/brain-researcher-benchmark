"""Generated checks of source-schema joins and the existing evaluator seam."""
import copy,hashlib,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import bridge
import stroop

def names():
    return [f"StroopDecData/NirsData/test{s}/{kind}/S{i:05d}{suffix}"
            for i in range(55) for s in (1,2,3)
            for kind,suffix in (("prep",".mat"),("raw",".csv"),("raw",".TXT"))]

def recording(onsets=(257,857,1457), length=2000):
    vector=[0]*length
    columns={11:[],12:[],13:[]}
    for code,onset in zip((11,12,13),onsets):
        vector[onset-1]=code;columns[code].append([float(onset),99.0])
    return vector,columns

class Controls(unittest.TestCase):
    def test_complete_inventory_and_third_session_typo(self):
        inventory=bridge.source_inventory(names())
        self.assertEqual(len(inventory['recordings']),165)
        changed=names();changed[6]=changed[6].replace('S00000','S99999')
        with self.assertRaises(bridge.InvalidBridge):bridge.source_inventory(changed)
    def test_marker_alignment_and_duplicate_refusal(self):
        vector,columns=recording();plans=bridge.native_block_plan(vector,columns)
        self.assertEqual(plans[0],{'block':0,'onset_sample1':257,'start_sample0':128,'stop_sample0_exclusive':768,'target':0})
        wrong=copy.deepcopy(columns);wrong[11][0][0]+=1
        with self.assertRaises(bridge.InvalidBridge):bridge.native_block_plan(vector,wrong)
        wrong=copy.deepcopy(columns);wrong[11].append(wrong[11][0])
        with self.assertRaises(bridge.InvalidBridge):bridge.native_block_plan(vector,wrong)
    def test_no_padding_and_no_following_block_crossing(self):
        vector,columns=recording((100,857,1457))
        with self.assertRaises(bridge.InvalidBridge):bridge.native_block_plan(vector,columns)
        vector,columns=recording((257,700,1457))
        with self.assertRaises(bridge.InvalidBridge):bridge.native_block_plan(vector,columns)
    def test_all_blocks_retained_beyond_author30(self):
        vector=[0]*(257+600*32+512);columns={11:[],12:[],13:[]}
        for i in range(33):
            onset=257+600*i;code=11+i%3;vector[onset-1]=code;columns[code].append([onset])
        self.assertEqual(len(bridge.native_block_plan(vector,columns)),33)
    def test_exact_grid_signal_order_and_no_scaling(self):
        vector,columns=recording()
        oxy=[[i+j/100 for j in range(35)]for i in range(len(vector))]
        dxy=[[-i-j/100 for j in range(35)]for i in range(len(vector))]
        result=next(bridge.native_windows({'oxyData':oxy,'dxyData':dxy,'vector_onset':vector},columns))
        self.assertEqual(len(result['native_values']),640)
        self.assertEqual(result['native_values'][0],oxy[128]+dxy[128])
        self.assertEqual(result['relative_time_seconds'][0],-5)
        self.assertEqual(result['relative_time_seconds'][128],0)
        self.assertEqual(result['relative_time_seconds'][-1],511/25.6)
        self.assertIn('unverified',result['unit_status'])
        oxy[128][0]=float('nan')
        with self.assertRaises(bridge.InvalidBridge):next(bridge.native_windows({'oxyData':oxy,'dxyData':dxy,'vector_onset':vector},columns))
    def test_channel_and_sample_shape(self):
        vector,columns=recording();bad=[[0.0]*34 for _ in vector];good=[[0.0]*35 for _ in vector]
        with self.assertRaises(bridge.InvalidBridge):next(bridge.native_windows({'oxyData':bad,'dxyData':good,'vector_onset':vector},columns))
        with self.assertRaises(bridge.InvalidBridge):next(bridge.native_windows({'oxyData':good[:-1],'dxyData':good,'vector_onset':vector},columns))
    def test_full55_manifest_matches_existing_evaluator(self):
        inventory=bridge.source_inventory(names());vector,columns=recording()
        blocks=bridge.native_block_plan(vector,columns)
        plans=[{**r,'n_samples':len(vector),'blocks':copy.deepcopy(blocks)}for r in inventory['recordings']]
        aliases={stem:hashlib.sha256(('generated-person-'+stem).encode()).hexdigest()for stem in inventory['source_stems']}
        key=b'generated-private-case-key-00001';self.assertEqual(len(key),32)
        manifest=bridge.private_manifest(inventory,aliases,'a5'*32,key,plans)
        self.assertEqual(len(manifest['cases']),165)
        predictions={'schema':'stroop55-predictions-v1','task':stroop.TASK,
                     'predictions':[{'case_id':c['case_id'],'probabilities':[1/3]*3,'label':'neutral'}for c in manifest['cases']]}
        self.assertAlmostEqual(stroop.evaluate(manifest,predictions)['primary']['value'],1/3)
        alternate=bridge.private_manifest(inventory,aliases,'a5'*32,b'x'*32,plans)
        self.assertTrue({c['case_id']for c in manifest['cases']}.isdisjoint(c['case_id']for c in alternate['cases']))
        with self.assertRaises(bridge.InvalidBridge):bridge.private_manifest(inventory,aliases,'a5'*32,key,plans[:-1])
        forged=copy.deepcopy(inventory);forged['recordings'][0]['session']=4
        with self.assertRaises(bridge.InvalidBridge):bridge.private_manifest(forged,aliases,'a5'*32,key,plans)
        short=copy.deepcopy(plans);short[0]['n_samples']=1500
        with self.assertRaises(bridge.InvalidBridge):bridge.private_manifest(inventory,aliases,'a5'*32,key,short)
        negative=copy.deepcopy(plans);negative[0]['blocks'][0].update(onset_sample1=1,start_sample0=-128,stop_sample0_exclusive=512)
        with self.assertRaises(bridge.InvalidBridge):bridge.private_manifest(inventory,aliases,'a5'*32,key,negative)
        overlap=copy.deepcopy(plans);overlap[0]['blocks'][1].update(onset_sample1=700,start_sample0=571,stop_sample0_exclusive=1211)
        with self.assertRaises(bridge.InvalidBridge):bridge.private_manifest(inventory,aliases,'a5'*32,key,overlap)
    def test_no_retroactive_identity_from_row_order(self):
        inventory=bridge.source_inventory(names())
        with self.assertRaises(bridge.InvalidBridge):bridge.private_manifest(inventory,{},'a5'*32,b'x'*32,[])

if __name__=='__main__':unittest.main()

