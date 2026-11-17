"""Exact authentic profile and complete support admission for trusted ownership.

These byte-level functions do not create authentic custody. Only custody.py's
operator-owned original-result capture may supply a reference to the scorer.
No candidate field can select a reference, context, source path or body hash.
"""
from dataclasses import dataclass
import struct
from kernel import D, P, MAX_WIDTH, Interval, Window, require
from certificate import decode, encode, pin, keys, hash_text, endpoint
from reader.contract import metadata, MASTER_PIN

PROFILE = 'tms_exact_real_authentic_source_position_248_v1'
IDENTITY_PIN = {'bytes':5214,'sha256':'4491f48145c8b9cddc7fcf7f7193a671117038583b234552cfa3bf85a23e262c'}
MAPS = ('NT.delay1','NT.delay2','T.delay1','T.delay2')
SUPPORT_SHAPE = (62,4,7,56)
SUPPORT_ENTRIES = 97216
SUPPORT_BYTES = 291648
CERTIFICATE_CAP = 262144
CONTEXT_KEYS = {'source_lock_sha256','runtime_sha256','identity_sha256','attempt_identity','input_sha256'}


def identity(body):
    require(type(body) is bytes and len(body)==IDENTITY_PIN['bytes'] and pin(body)==IDENTITY_PIN,'fixed original identity body')
    value=decode(body)
    metadata(value)
    return value


def context(value):
    keys(value,CONTEXT_KEYS)
    require(all(type(x) is str for x in value.values()),'strict owned context strings')
    for key in CONTEXT_KEYS-{'attempt_identity'}:hash_text(value[key])
    require(value['identity_sha256']==IDENTITY_PIN['sha256'] and value['input_sha256']==MASTER_PIN['sha256'],'authentic original source identity')
    require(value['attempt_identity']=='authentic-interval-reference-01','one fixed owned attempt')
    return dict(value)


def offset(channel,condition,frequency,time):
    require(all(type(x) is int for x in (channel,condition,frequency,time))
            and 0<=channel<62 and 0<=condition<4 and 0<=frequency<7 and 0<=time<56,'fixed support address')
    return (((channel*4+condition)*7+frequency)*56+time)*3


def support_rows(body):
    require(type(body) is bytes and len(body)==SUPPORT_BYTES,'complete fixed support ledger')
    rows=[]
    for count,mask in struct.iter_unpack('<BH',body):
        require(count<=15 and mask<(1<<15) and mask.bit_count()==count,'all15 position-mask/count agreement')
        rows.append((count,mask))
    require(len(rows)==SUPPORT_ENTRIES,'all97216 source-group supports')
    return rows


def nested_support(rows,map_index,channel):
    condition=0 if map_index<2 else 2
    start=0 if map_index%2==0 else 28
    counts=[]
    for frequency in range(7):
        count=0
        for t in range(start,start+28):
            a=rows[offset(channel,condition,frequency,t)//3][0]
            b=rows[offset(channel,condition+1,frequency,t)//3][0]
            count+=int(a>0 and b>0)
        counts.append(count)
    return tuple(counts),sum(x>0 for x in counts)


@dataclass(frozen=True)
class AdmittedBody:
    slots: tuple
    certificate_pin: dict
    support_pin: dict
    source_context: dict


def admit_bytes(raw, support, *, expected_certificate, expected_support, identity_body, owned_context):
    # This is a bounded internal parser, never an authority or public grading entry.
    require(type(raw) is bytes and 0<len(raw)<=CERTIFICATE_CAP,'bounded authentic certificate before hashing')
    require(type(support) is bytes and len(support)==SUPPORT_BYTES,'bounded authentic support before hashing')
    document=decode(raw)
    keys(document,{'schema','authentic_source','fractional_bits','diameter_bits','domain_bound','identity_pin','source_context','map_order','labels','support','slots'})
    require(type(document['schema']) is str and document['schema']==PROFILE and document['authentic_source'] is True,'authentic profile; fixture cannot be promoted')
    meta=identity(identity_body);expected_context=context(owned_context)
    for value in (expected_certificate,expected_support):
        keys(value,{'bytes','sha256'});require(type(value['bytes']) is int and value['bytes']>0,'strict owned body length');hash_text(value['sha256'])
    require(pin(raw)==expected_certificate and pin(support)==expected_support,'trusted owner-selected body pins')
    require(type(document['fractional_bits']) is int and document['fractional_bits']==P
            and type(document['diameter_bits']) is int and document['diameter_bits']==96
            and type(document['domain_bound']) is int and document['domain_bound']==1000,'fixed exact-real numerical contract')
    require(document['identity_pin']==IDENTITY_PIN and type(document['identity_pin']['bytes']) is int,'fixed identity pin')
    require(context(document['source_context'])==expected_context,'exact owned source/runtime/attempt binding')
    require(type(document['map_order']) is list and document['map_order']==list(MAPS),'fixed four-map order')
    require(type(document['labels']) is list and all(type(x) is str for x in document['labels']) and document['labels']==meta['labels'],'complete original channel order')
    keys(document['support'],{'shape','encoding','pin'})
    require(type(document['support']['shape']) is list and all(type(x) is int for x in document['support']['shape']) and document['support']['shape']==list(SUPPORT_SHAPE),'strict full support geometry')
    require(document['support']['encoding']=='little-endian uint8 contributor count then uint16 source-position mask','support byte interpretation')
    require(document['support']['pin']==expected_support and type(document['support']['pin']['bytes']) is int,'support pin join')
    rows=support_rows(support)
    require(type(document['slots']) is list and len(document['slots'])==248,'all248 fixed map slots')
    slots=[]
    for i,row in enumerate(document['slots']):
        keys(row,{'index','map','channel','undefined','lo','hi','time_counts','frequency_count'})
        require(type(row['index']) is int and row['index']==i,'strict complete slot order')
        require(type(row['map']) is str and row['map']==MAPS[i//62]
                and type(row['channel']) is str and row['channel']==meta['labels'][i%62],'fixed map/channel identity')
        require(type(row['undefined']) is bool,'strict undefined Boolean')
        tc,fc=nested_support(rows,i//62,i%62)
        require(type(row['time_counts']) is list and all(type(x) is int for x in row['time_counts'])
                and row['time_counts']==list(tc) and type(row['frequency_count']) is int and row['frequency_count']==fc,'complete original-support to nested-support join')
        require(row['undefined']==(fc==0),'source support fixes undefined category')
        if fc==0:
            require(row['lo'] is None and row['hi'] is None,'undefined has no numeric endpoint');iv=None
        else:
            lo,hi=endpoint(row['lo']),endpoint(row['hi'])
            require(lo<=hi and hi-lo<=MAX_WIDTH,'fixed final certificate width');iv=Interval(lo,hi)
        slots.append(Window(iv,tc,fc))
    return AdmittedBody(tuple(slots),dict(expected_certificate),dict(expected_support),expected_context)


def publish_bytes(windows,support,*,identity_body,owned_context):
    meta=identity(identity_body);ctx=context(owned_context)
    require(type(windows) is list and len(windows)==248 and all(type(x) is Window for x in windows),'all248 constructed windows')
    rows=[]
    for i,value in enumerate(windows):
        iv=value.interval
        require(iv is None or type(iv) is Interval,'exact constructed interval')
        rows.append({'index':i,'map':MAPS[i//62],'channel':meta['labels'][i%62],'undefined':iv is None,
                     'lo':None if iv is None else str(iv.lo),'hi':None if iv is None else str(iv.hi),
                     'time_counts':list(value.time_counts),'frequency_count':value.frequency_count})
    raw=encode({'schema':PROFILE,'authentic_source':True,'fractional_bits':P,'diameter_bits':96,'domain_bound':1000,
                'identity_pin':IDENTITY_PIN,'source_context':ctx,'map_order':list(MAPS),'labels':meta['labels'],
                'support':{'shape':list(SUPPORT_SHAPE),'encoding':'little-endian uint8 contributor count then uint16 source-position mask','pin':pin(support)},'slots':rows})
    admit_bytes(raw,support,expected_certificate=pin(raw),expected_support=pin(support),identity_body=identity_body,owned_context=ctx)
    return raw
