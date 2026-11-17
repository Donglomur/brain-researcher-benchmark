"""Complete source-defined scientific contexts and immutable resource domains."""
from common import need
SESSIONS=('p1_1','p1_2','p2_1','p2_2','p3_1','p3_2','p4_1','p5_1','p5_2','p6_1','p7_1','p7_2','p8_1','p8_2')
EPISODES=tuple(s+'_f'+str(f) for s in SESSIONS for f in range(5))
WORK=3000000
PUBLICATION=WORK+120
OUTER=WORK+240
READ_CAP=1099511627776
WRITE_CAP=274877906944
OBSERVER_RETAINED=16777216
OBSERVER_MEMORY_CAP=2147483648
FULL_SOURCE_PAYLOAD=785073288
PREPARED_CAP=FULL_SOURCE_PAYLOAD+197*4096+1048576
SELECTED_CAP=788596416+14*1000000+1048576
EPISODE_PUBLIC_CAP=2*268435456+2000000
EPISODE_PRIVATE_CAP=33554432+2000000
EPISODE_CAP=EPISODE_PUBLIC_CAP+EPISODE_PRIVATE_CAP
PRIVATE_TARGET_TOTAL_CAP=192344344+70*65536
PRIVATE_BINDING_TOTAL_CAP=70*2000000
OUTPUT_CEILING=3*(14*33554432+500000)+2*(536870912+500000)+70*(33554432+100000)
# All mandatory retained output domains plus one live case, its candidate view,
# complete prepared pool, private targets, metadata/programs and block overhead.
PREPARE_PEAK=SELECTED_CAP+PREPARED_CAP
NATIVE_PEAK=3*(14*33554432+500000)+2*PREPARED_CAP+22000000
PREDICTION_PEAK=OUTPUT_CEILING+PREPARED_CAP+EPISODE_CAP+2*268435456+22000000+PRIVATE_TARGET_TOTAL_CAP+PRIVATE_BINDING_TOTAL_CAP
RETAINED_REQUIRED=max(PREPARE_PEAK,NATIVE_PEAK,PREDICTION_PEAK)+3221225472+268435456+OBSERVER_RETAINED
COVERAGE={'people':8,'sessions':14,'session_local_units':567,'layers':33,'native_fields_per_session':16,'prospective_episodes':70,'candidate_native_panels':2,'operator_native_panels':1,'candidate_prediction_files':140,'operator_baseline_episodes':70,'operator_baselines_per_episode':4,'phases':213}

def contexts():
    rows=[{'role':role,'mode':'native','purpose':'reproduction'if arm else'reference','arm':arm,'episode':None}for role,arm in [('native','A'),('native','B'),('reference_native',None)]]
    for episode in EPISODES:
        rows.extend({'role':role,'mode':'strict','purpose':'prediction'if arm else'reference','arm':arm,'episode':episode}for role,arm in [('strict','A'),('strict','B'),('reference_strict',None)])
    for i,r in enumerate(rows):r.update(index=i,phase_id=f'{i:03d}-{r["role"]}-{r["arm"] or "fixed"}-{r["episode"] or "full"}')
    need(len(rows)==213,'complete full protocol');return rows
