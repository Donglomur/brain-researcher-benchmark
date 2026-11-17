"""Target-independent public projections; protected outcomes never select requests."""
from .common import require,exact_keys,identity,integer,token,keyed,finite

WAIT_FIELDS={'offered_physical_ul','offered_ordinal','wait_limit_seconds','relative_time','past_events'}
NEURAL_FIELDS={'target_unit','peer_units','peer_observations','past_events','bin_width_seconds'}
REWARD_FIELDS={'neural_units','neural_observations','relative_event_time','window_seconds'}
ASSOC_FIELDS={'neural_units','neural_observations','relative_time'}
SIM_FIELDS={'observation_asset_id','relative_time','trial_ordinal'}
EVENT_FIELDS={'kind','trial_ordinal','bin_ordinal','value'}
EVENT_KINDS={'offer','fixation_started','fixation_ended','reward_observed','optout_observed','timeout_observed','trial_started','waiting_started'}
def before(event,cutoff):return (event['trial_ordinal'],event['bin_ordinal'])<=(cutoff['trial_ordinal'],cutoff['bin_ordinal'])
def past(events,cutoff):
 require(isinstance(events,list),'past event list')
 for event in events:
  exact_keys(event,EVENT_FIELDS);require(event['kind']in EVENT_KINDS,'unknown public event');integer(event['trial_ordinal']);integer(event['bin_ordinal']);require(before(event,cutoff),'future event')
 return events
def validate_query(row):
 f=row['family_id'];p=row['public'];c=row['cutoff']
 allowed={'I_WAIT':WAIT_FIELDS,'I_NEURAL':NEURAL_FIELDS,'I_REWARD':REWARD_FIELDS,'I_ASSOCIATION':ASSOC_FIELDS,'I_SIM_ATI':SIM_FIELDS,'I_REAL_ATI':ASSOC_FIELDS}[f]
 exact_keys(p,allowed)
 if 'past_events'in p:past(p['past_events'],c)
 if f=='I_WAIT':
  require(p['wait_limit_seconds']==100 and p['relative_time']==0,'pre-wait timing/cap')
  require(type(p['offered_ordinal'])is int and p['offered_ordinal']in range(1,6),'reward ordinal')
  require(all(e['trial_ordinal']<c['trial_ordinal']or e['kind']in('offer','fixation_started','fixation_ended','trial_started','waiting_started')for e in p['past_events']),'current-trial future outcome')
 if f=='I_WAIT':canonical_offer_sequence(row)
 if f=='I_NEURAL':
  require(p['target_unit']not in p['peer_units']and len(set(p['peer_units']))==len(p['peer_units']),'target neuron in peer view')
  require(p['bin_width_seconds']==.05,'neural50ms unit')
  for obs in p['peer_observations']:
   exact_keys(obs,('unit','trial_ordinal','bin_ordinal','value'));require(obs['unit']in p['peer_units']and before(obs,c),'unallowed neural observation')
 if f=='I_REWARD':require(p['window_seconds']==.25,'decoder250ms window')
 if 'neural_observations'in p:
  for obs in p['neural_observations']:
   exact_keys(obs,('unit','trial_ordinal','bin_ordinal','value'));require(obs['unit']in p['neural_units']and before(obs,c),'future neural decoder/association observation')
 return row
def behavior_queries(admin,eligible_sessions,test_ordinals):
 """Consume administrative events only. Do not pass or inspect an outcome table."""
 rows=[];seen=set()
 for event in admin:
  exact_keys(event,('rat_token','session_token','trial_token','trial_ordinal','reached_waitstart','waitstart_prefix','offered_physical_ul','offered_ordinal'))
  s=event['session_token'];t=event['trial_ordinal']
  require(type(event['reached_waitstart'])is bool,'administrative waiting flag')
  if s not in eligible_sessions or t not in test_ordinals[s]or not event['reached_waitstart']:continue
  token(event['rat_token']);token(s);token(event['trial_token']);key=identity([s,event['trial_token']])
  require(key not in seen,'duplicate administrative trial');seen.add(key)
  row={'query_id':key,'family_id':'I_WAIT','stream_id':s,'public':{'offered_physical_ul':event['offered_physical_ul'],'offered_ordinal':event['offered_ordinal'],'wait_limit_seconds':100,'relative_time':0,'past_events':event['waitstart_prefix']},'public_input_ids':[],'cutoff':{'trial_ordinal':t,'bin_ordinal':0},'group_keys':{'rat':event['rat_token'],'session':s}}
  validate_query(row);rows.append(row)
 rows.sort(key=lambda r:(r['group_keys']['rat'],r['group_keys']['session'],r['cutoff']['trial_ordinal']))
 return rows
def neural_queries(admin_bins,units_by_session):
 """Create target-isolated all-bin projections from a fixed administrative roster."""
 output=[]
 for b in admin_bins:
  exact_keys(b,('rat','session','trial_ordinal','bin_ordinal','observations','past_events'))
  units=units_by_session[b['session']];require(set(b['observations'])==set(units),'complete source unit binding')
  for target in units:
   peers=[u for u in units if u!=target];cut={'trial_ordinal':b['trial_ordinal'],'bin_ordinal':b['bin_ordinal']}
   observations=[{'unit':u,**cut,'value':b['observations'][u]}for u in peers]
   r={'query_id':identity([b['session'],target,cut]),'family_id':'I_NEURAL','stream_id':identity([b['session'],target]),'public':{'target_unit':target,'peer_units':peers,'peer_observations':observations,'past_events':b['past_events'],'bin_width_seconds':.05},'public_input_ids':[],'cutoff':cut,'group_keys':{'rat':b['rat'],'session':b['session'],'unit':target}}
   output.append(validate_query(r))
 return output
def commitment(public_universes,native_requests,private_target_roster,policy_id):
 """Operator-only opaque commitment. Its private preimage never enters a worker view."""
 return identity({'public':public_universes,'native':native_requests,'protected':private_target_roster,'policy':policy_id})


def canonical_offer_sequence(query):
 """Exactly one ordered offer per prior trial plus exactly one current offer.

 A source prefix may contain or omit the current offer. Both encodings project
 to this same sequence. Duplicate, conflicting or reordered offers are refused;
 current observation is never treated as a previous-trial divisive history.
 """
 require(query['family_id']=='I_WAIT','offer sequence belongs to waiting view')
 p=query['public'];cut=query['cutoff'];current_offer={'physical_ul':p['offered_physical_ul'],'ordinal':p['offered_ordinal']}
 def value(v):
  exact_keys(v,('physical_ul','ordinal'));require(finite(v['physical_ul'])>0,'positive physical reward volume');require(type(v['ordinal'])is int and v['ordinal']in range(1,6),'five-level reward ordinal');return v
 value(current_offer);prior=[];seen=set();last=-1;current_seen=False
 for event in p['past_events']:
  if event['kind']!='offer':continue
  integer(event['trial_ordinal']);integer(event['bin_ordinal']);require(before(event,cut),'future offer event');trial=event['trial_ordinal'];require(trial not in seen and trial>last,'duplicate or unordered offer trial');seen.add(trial);last=trial;offer=value(event['value'])
  if trial==cut['trial_ordinal']:
   require(not current_seen and offer==current_offer,'conflicting current offer');current_seen=True
  else:require(trial<cut['trial_ordinal'],'future offer trial');prior.append(dict(offer))
 return prior+[current_offer]
