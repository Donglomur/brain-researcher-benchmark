"""The full eleven-family programme; slots never become benchmark counts."""
import hashlib
from collections import Counter
from .protocol import fields,need,identity,integer,digest

CANONICAL='PAPER-paper-method-023'
PROFILE='complete_eegpt_participant_v1'
MODES=('H','P','I');ACCESS=('A','B');REPETITIONS=(0,1,2)
CONTROLS=('EEGPT_linear_probe','EEGPT_full_finetune','EEGNet','fixed_spectral_ridge')
DATASETS=('BCIC-2A','BCIC-2B','Sleep-EDFx','KaggleERN','PhysioP300','TUAB','TUEV')
FOLDS={'BCIC-2A':9,'BCIC-2B':9,'Sleep-EDFx':10,'KaggleERN':4,'PhysioP300':9,'TUAB':1,'TUEV':1}
CLASSES={'BCIC-2A':4,'BCIC-2B':2,'Sleep-EDFx':5,'KaggleERN':2,'PhysioP300':2,'TUAB':2,'TUEV':6}
CALLS=('DESCRIBE','PREPARE','PRETRAIN','FIT','VALIDATE','PREDICT','QUERY_TRANSFORM','DIAGNOSE','ANALYZE','CLOSE','REFERENCE_BUILD','SCORE_AND_REPORT','INTERPRET')
CONTRACT_NAMES=('ADAPTIVE_INFORMATION_CONTRACT','API','ARCHITECTURE_AND_RECIPES','CLAIM_LEDGER','DATA_SPLITS','DECLARATIVE_TRACES','EXPOSURE','GATES_CONTROLS','LOGICAL_OUTPUT_SLOTS','METRICS','OBLIGATIONS','OPERATORS','PREDECESSOR_PANEL','REASONING_RUBRIC','REFERENCES','REFERENCE_SELECTION_CONTRACT','SCHEDULE_COSTS')


class Scope:
    def __init__(self,contracts):
        need(set(contracts)==set(CONTRACT_NAMES),'whole authenticated accepted contract set')
        self.contracts=contracts;slots=contracts['LOGICAL_OUTPUT_SLOTS'];legacy=slots['legacy'];additional=slots['additional_reproduction']
        need(len(legacy)==1203 and len(additional)==1206,'all original classification products')
        need(len({x['case_id'] for x in legacy+additional})==2409,'unique original logical product identities')
        original=[x for x in legacy if x['purpose']=='reproduction'];candidate=[x for x in legacy if x['purpose']=='improvement' and not x['trusted_reference']];fixed=[x for x in legacy if x['trusted_reference']]
        need((len(original),len(candidate),len(fixed))==(558,129,516),'original principal/candidate/fixed support')
        for row in legacy+additional:
            need(row['dataset'] in DATASETS and row['columns']==CLASSES[row['dataset']],'original dataset/class semantics')
            integer(row['fold_slot'],'original fold',0,FOLDS[row['dataset']]-1);need(row['seed_slot'] in REPETITIONS,'all3 original repetition slots')
        need(Counter(x['family'] for x in additional)=={'EG-04':264,'EG-05':264,'EG-06':456,'EG-07':216,'EG-08':6},'complete original nonprincipal reproduction families')
        need(len(contracts['OBLIGATIONS']['families'])==11 and len(contracts['OPERATORS']['operators'])==31,'whole scientific family/operator scope')
        need(tuple(x['name'] for x in contracts['API']['calls'])==CALLS and len(contracts['API']['products'])==14,'all13 calls and14 scientific products')
        need({x['id'] for x in contracts['DATA_SPLITS']['downstream']}==set(DATASETS),'all7 original datasets')
        need(sum(FOLDS.values())==43,'all43 original folds')
        self.original=original;self.additional=additional;self.candidate=candidate;self.fixed=fixed
        self.families=contracts['OBLIGATIONS']['families'];self.identity=identity(contracts)
    def classification(self):
        """Every H/P original row has a separate independent reference bank.

        This conservative initial schedule does not assume any A/B, variant,
        deterministic or cross-mode reuse. Legitimate future aliases must keep
        both logical identities and actual original eligible ancestry.
        """
        for mode in MODES:
            for access in ACCESS:
                if mode in ('H','P'):
                    for role in ('participant','reference'):
                        for row in self.original+self.additional:
                            method=row.get('method',row.get('variant'))
                            yield {'mode':mode,'access':access,'actor_role':role,'case':row,'method':method,'family':row.get('family','EG-03'),'bank':('REF_'+mode) if role=='reference' else 'CANDIDATE_'+mode}
                else:
                    for row in self.candidate+self.fixed:
                        role='reference' if row['trusted_reference'] else 'participant'
                        yield {'mode':mode,'access':access,'actor_role':role,'case':row,'method':row['method'],'family':'EG-03','bank':'REF_I' if role=='reference' else 'CANDIDATE_I'}
    def classification_key(self,row):
        return identity({'mode':row['mode'],'access':row['access'],'actor_role':row['actor_role'],'case_id':row['case']['case_id'],'bank':row['bank']})
    def episode(self,row,policy):
        return {'mode':row['mode'],'access':row['access'],'policy_id':policy,'actor_role':row['actor_role'],'dataset':row['case']['dataset'],'outer_fold':'f'+str(row['case']['fold_slot']),'method':row['method']}
    def summary(self):
        return {'canonical_id':CANONICAL,'canonical_assignments':1,'families':11,'figures':18,'tables':13,'claims':24,'operators':31,'calls':13,'products':14,'datasets':7,'folds':43,'downstream_repetitions':3,'principal_reproduction_per_mode_access_actor':558,'additional_reproduction_per_mode_access_actor':1206,'complete_reproduction_per_mode_access_actor':1764,'improvement_candidate_per_access':129,'independent_fixed_controls_per_access':516,'gates_open':24,'future_scientific_control_groups':54,'declarative_traces':14,'all_required_matrix_slots_before_any_alias':15402,'cases_conditions_or_versions_are_tasks':False,'scientifically_qualified':False}


def derived_seed(commitment,repetition,stream):
    digest(commitment);need(repetition in REPETITIONS and type(stream) is str and stream,'complete prospective seed stream identity')
    return int.from_bytes(hashlib.sha256(('eegpt-prospective-v1:'+commitment+':'+str(repetition)+':'+stream).encode()).digest()[:4],'big')


def prospective_person_split(dataset,people,fold,*,kaggle=None,temple=None,block_commitment=None):
    """Metadata-only complete prospective split; never invent original H IDs."""
    need(dataset in DATASETS and len(people)==len(set(people)) and people,'complete qualified biological person ledger')
    integer(fold,'original fold slot',0,FOLDS[dataset]-1);ordered=list(people)
    if dataset in ('BCIC-2A','BCIC-2B','PhysioP300'):
        need(len(ordered)==9,'all9 original downstream people');query=[ordered[fold]];remaining=[x for x in ordered if x not in query]
        validation=[remaining[fold%8]];train=[x for x in remaining if x not in validation]
    elif dataset=='KaggleERN':
        fields(kaggle,('test','train','P_I_validation'),'exact source-selected Kaggle person folds')
        query=list(kaggle['test']);train=list(kaggle['train'][fold]);validation=[p for p in ordered if p not in set(query)|set(train)]
        need(type(kaggle['P_I_validation']) is str and kaggle['P_I_validation'].startswith('Complement'),'authenticated complement policy')
        need(len(query)==10 and len(train)==12 and len(validation)==4,'complete ten-query/twelve-train/four-validation support')
    elif dataset=='Sleep-EDFx':
        digest(block_commitment);need(len(ordered)>=10,'full authenticated sleep cohort can populate10 blocks')
        order=sorted(ordered,key=lambda p:hashlib.sha256(('sleep-block-v1:'+block_commitment+':'+p).encode()).digest());blocks=[[] for _ in range(10)]
        # Round-robin allocation fixes the integer remainder, difference<=1.
        for i,p in enumerate(order):blocks[i%10].append(p)
        qblocks={fold,(fold+1)%10};vblocks={(fold+2)%10,(fold+3)%10}
        query=[p for b in sorted(qblocks) for p in blocks[b]];validation=[p for b in sorted(vblocks) for p in blocks[b]];train=[p for b in range(10) if b not in qblocks|vblocks for p in blocks[b]]
    else:
        fields(temple,('train','validation','query','source_policy','qualification'),'complete qualified Temple split')
        digest(temple['qualification']);need(temple['source_policy'] in ('original_person_disjoint','corrected_person_disjoint'),'declared complete prospective Temple policy')
        train=list(temple['train']);validation=list(temple['validation']);query=list(temple['query'])
    sets=[set(x) for x in (train,validation,query)]
    need(all(sets) and all(not sets[a]&sets[b] for a,b in ((0,1),(0,2),(1,2))),'complete disjoint prospective person support')
    need(set.union(*sets)==set(people) and sum(map(len,(train,validation,query)))==len(people),'every eligible original person accounted exactly once within fold')
    return {'train':train,'validation':validation,'query':query,'source':'prespecified prospective policy, not asserted historical split'}


def validate_census(census,scope,population,*,require_target_roster=True):
    fields(census,('schema','datasets','corpus','overlap','diagnostic_plans','historical_policy','source_qualification','target_rosters','development_label_rosters'),'complete scientific input census')
    need(census['schema']=='eegpt_complete_input_census_v1' and set(census['datasets'])==set(DATASETS),'all7 complete original datasets')
    digest(census['source_qualification']);need(set(census['corpus'])=={'PhysioMI','HGD','TSU','SEED','M3CV'},'all five complete pretraining source families')
    fields(population,('schema','datasets','qualification','source_inventory_identity'),'independently qualified complete original population')
    need(population['schema']=='eegpt_qualified_population_v1' and set(population['datasets'])==set(DATASETS),'all seven qualified original populations');digest(population['qualification']);digest(population['source_inventory_identity'])
    seen=[]
    for dataset,document in census['datasets'].items():
        fields(document,('people','records','exclusions','provider_version','source_identity','person_alias_evidence','folds','source_policy'),'complete dataset cohort')
        need(document['people'] and len(document['people'])==len(set(document['people'])),'all original person identities')
        original=population['datasets'][dataset]
        fields(original,('people','person_dispositions','records','recordings','provider_version','source_identity','person_alias_evidence','historical_folds','prospective_policy'),'full independently selected original dataset roster')
        for key in ('people','provider_version','source_identity','person_alias_evidence'):need(document[key]==original[key],'exact qualified original population '+key)
        need(set(original['person_dispositions'])==set(original['people']),'all original people explicitly disposed')
        for person,disposition in original['person_dispositions'].items():
            fields(disposition,('included','reason'),'complete person inclusion/exclusion');need(type(disposition['included']) is bool and disposition['included']==(disposition['reason'] is None),'typed original person disposition')
        eligible=[person for person in original['people'] if original['person_dispositions'][person]['included']]
        if dataset in ('BCIC-2A','BCIC-2B','PhysioP300'):need(len(eligible)==9,'known complete nine-person downstream cohort')
        if dataset=='KaggleERN':need(len(eligible)==26,'complete26-person Kaggle cohort')
        need(len(original['historical_folds'])==FOLDS[dataset],'all independently selected historical folds, never overwritten with prospective policy')
        digest(document['source_identity']);digest(document['person_alias_evidence']);need(len(document['folds'])==FOLDS[dataset],'every original fold present')
        rows=[]
        for row in document['records']:
            fields(row,('id','person','session','recording','event','interval','channels','sampling_hz','units','signal','label_provenance','transform_ancestry','source_identity','included','exclusion_reason'),'complete raw-to-derived event')
            need(row['person'] in document['people'] and type(row['included']) is bool,'actual person and eligibility');need(row['included']==(row['exclusion_reason'] is None),'explicit exclusion status')
            need(type(row['channels']) is list and row['channels'] and len(row['channels'])==len(set(row['channels'])),'exact original channel axis')
            need(type(row['interval']) is list and len(row['interval'])==2 and row['interval'][1]>row['interval'][0],'original half-open physical interval')
            digest(row['source_identity']);digest(row['label_provenance']);rows.append(row['id'])
        need(len(rows)==len(set(rows)) and set(rows)==set(original['records']),'complete original event population, no dropped excluded or included record')
        for row in document['records']:
            selected=original['records'][row['id']];fields(selected,('person','session','recording','event','source_identity','included','exclusion_reason'),'independent complete original row identity/disposition')
            need(all(row[k]==v for k,v in selected.items()),'exact independently qualified event and exclusion status')
            if row['included']:need(row['person'] in eligible,'excluded person cannot contribute eligible rows')
        rows_by_recording={}
        for row in document['records']:rows_by_recording.setdefault(row['recording'],[]).append(row)
        recording_map={r['recording']:r for r in original['recordings']};need(len(recording_map)==len(original['recordings']),'unique original recording roster')
        for recording,item in recording_map.items():
            fields(item,('recording','person','source_identity','included','exclusion_reason'),'complete original recording identity/disposition');digest(item['source_identity']);need(item['person'] in original['people'] and type(item['included']) is bool and item['included']==(item['exclusion_reason'] is None),'original recording disposition')
            relevant=rows_by_recording.get(recording,[])
            need(all(r['person']==item['person'] for r in relevant),'no cross-person recording alias')
            if item['included']:need(relevant,'included original recording cannot disappear from event census')
            else:need(not any(r['included'] for r in relevant),'excluded recording contributes no included event')
        need(all(r['recording'] in recording_map for r in document['records']),'no row from unqualified recording')
        need(all(any(r['included'] and r['person']==p for r in document['records']) for p in eligible),'every included original person represented')
        exclusions={'records':{k:r['exclusion_reason'] for k,r in original['records'].items() if not r['included']},'recordings':{k:r['exclusion_reason'] for k,r in recording_map.items() if not r['included']},'people':{k:r['reason'] for k,r in original['person_dispositions'].items() if not r['included']}}
        need(document['exclusions']==exclusions,'full exact original exclusion dispositions and denominators')
        policy=original['prospective_policy'];fields(policy,('name','settings'),'exact qualified prospective policy')
        kaggle=temple=block=None
        if dataset in ('BCIC-2A','BCIC-2B','PhysioP300'):need(policy=={'name':'rotating_loso_v1','settings':{}},'fixed nine-person rotating inner-validation policy')
        elif dataset=='KaggleERN':
            need(policy['name']=='source_kaggle_12_4_10_v1','fixed exact Kaggle policy');aliases=policy['settings'];need(set(aliases)=={str(i) for i in range(1,27)} and set(aliases.values())==set(eligible) and len(set(aliases.values()))==26,'qualified exact provider1..26 person alias bijection')
            source=scope.contracts['DATA_SPLITS']['kaggle_exact_source_folds'];kaggle={'test':[aliases[str(i)] for i in source['test']],'train':[[aliases[str(i)] for i in group] for group in source['train']],'P_I_validation':source['P_I_validation']}
        elif dataset=='Sleep-EDFx':
            need(policy['name']=='sleep_person_blocks_v1' and set(policy['settings'])=={'block_commitment'},'fixed entire-person cyclic Sleep blocks');block=policy['settings']['block_commitment']
        else:
            need(policy['name']=='qualified_temple_person_partition_v1','exact selected original/corrected Temple person partition');temple=policy['settings']
        seen.extend((dataset,x) for x in rows)
        for fold_index,fold in enumerate(document['folds']):
            fields(fold,('fold_slot','H','P_I','whole_person_qualified','complete_support_identity'),'whole original fold policy')
            need(fold['fold_slot']==fold_index,'complete ordered fold slots');digest(fold['complete_support_identity'])
            need(fold['H']==original['historical_folds'][fold_index],'exact original H source policy preserved separately')
            prospective=prospective_person_split(dataset,eligible,fold_index,kaggle=kaggle,temple=temple,block_commitment=block)
            for mode in ('H','P_I'):
                split=fold[mode];fields(split,('train','validation','query','policy','exposure'),'complete mode support')
                need(all(type(split[k]) is list and split[k] for k in ('train','validation','query')),'complete mode support sets')
                need(all(len(split[k])==len(set(split[k])) and set(split[k])<=set(rows) for k in ('train','validation','query')),'exact original nonduplicated event support')
                if mode=='P_I':
                    need(fold['whole_person_qualified'] is True,'prospective grouping independently qualified')
                    byid={r['id']:r for r in document['records']};person_sets=[{byid[k]['person'] for k in split[role]} for role in ('train','validation','query')]
                    need(all(not person_sets[a]&person_sets[b] for a,b in ((0,1),(0,2),(1,2))),'no prospective person aliases across fit/development/query')
                    expected={r['id'] for r in document['records'] if r['included']};need(set(split['train'])|set(split['validation'])|set(split['query'])==expected,'all eligible original rows retained')
                    for role in ('train','validation','query'):
                        required=[r['id'] for r in document['records'] if r['included'] and r['person'] in set(prospective[role])]
                        need(split[role]==required,'exact source-owned prospective fold assignment and full original row order: '+dataset+':'+str(fold_index)+':'+role)
    need(census['overlap']['complete'] is True,'complete cross-corpus/downstream identity and exposure audit')
    digest(census['overlap']['evidence'])
    if require_target_roster:need(set(census['target_rosters'])==set(DATASETS),'all protected target joins separately selected')
    else:need(set(census['target_rosters']) in (set(),set(DATASETS)),'preparation may precede derived target-file publication, never partial dataset scope')
    need(set(census['diagnostic_plans'])=={r['id'] for r in scope.families},'all eleven complete numerical family plans')
    return {'census_identity':identity(census),'source_event_count':len(seen),'dataset_count':7,'fold_count':43,'no_authentic_data_read_by_metadata_admission':True}
