"""Exact owner-side artifact closure; not a participant submission/scoring schema."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import zlib

HERE = Path(__file__).resolve().parent
PREDECESSOR = HERE.parent / 'nider-primary-producer-v2'
PREDECESSOR_COMMIT = '9701e99e181f1f8056a5c6f2849eb56977a37bcb'
PREDECESSOR_PINS = {
    'replay_primary_dl.py': 'd66ca0a2e177ad0843aaca7fbc7e1a766d158f6f40c7393ccbc4153b6a1f6d16',
    'collector.R': '8eb78f3eedfecb91dff89cedbea1d7db1df665b5065fa115787ae8d3d4599b58',
    'source_selection.R': '21de9624646177b1974957a4609a2b3ee606fa2159d4b5dbef244e26e449adac',
}
PHASES = {
    'libraries': [(n,n) for n in range(13,20)] + [(23,23)],
    'core_DL': [(28,28),(29,29),(73,73),(74,74),(75,75),(77,82),(86,129),(131,138),
                (140,140),(141,141),(149,149),(153,153),(216,216),(219,219),(262,262),(265,265)],
    'table1': [(31,67),(377,377),(379,379),(380,380),(381,381)],
    'forests': [(165,171),(173,176),(178,178),(229,235),(237,240),(242,242),
                (274,280),(282,285),(287,287)],
    'Bayesian': [(186,186),(187,187),(189,189),(190,190),(192,192),(194,194),(195,195),
                 (197,200),(201,201),(245,245),(247,247),(248,248),(250,253),(255,255),
                 (296,296),(298,298),(299,299),(301,304),(306,306)],
}
IDS = ('quest_self','amy_quest','amy_self')
MODEL_BINDINGS = {
    'quest_self': ('meta_questSelf','dfQuestSelf','dfQuestSelf_conv','sample size quest'),
    'amy_quest': ('meta_amyQuest','dfAmyQuest','dfAmyQuest_conv','sample size quest'),
    'amy_self': ('meta_amySelf','dfAmySelf','dfAmySelf_conv','sample size rating'),
}
FIGURES = {
    'quest_self': 'results/figures/forestplot_questSelf_nat.png',
    'amy_quest': 'results/figures/forestplot_amyQuest_nat.png',
    'amy_self': 'results/figures/forestplot_meta_amySelf_nat.png',
}
REQUIRED_ARTIFACTS = ('full120.json','row_lineage.json','table1/habit_associations.rds',
    'table1/habit_associations.csv','runtime.json') + tuple('dl/'+x+'.rds' for x in IDS) + tuple(
    FIGURES.values()) + tuple('bayes/'+x+suffix for x in IDS for suffix in ('.input.rds','.rds','.txt','.json')) + tuple(
    'dl/'+x+'.json' for x in IDS)


def need(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load_predecessor():
    verified = {}
    for name, expected in PREDECESSOR_PINS.items():
        raw = (PREDECESSOR/name).read_bytes()
        need(digest(raw) == expected, 'predecessor_identity:'+name)
        verified[name] = raw
    spec = importlib.util.spec_from_loader('_frozen_nider_reference',loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(PREDECESSOR/'replay_primary_dl.py')
    exec(compile(verified['replay_primary_dl.py'],module.__file__,'exec'),module.__dict__)
    return module


def source_manifest(script, base):
    need(digest(script) == base.PINS['script'][0], 'original_source_identity')
    lines = script.decode('utf-8').splitlines(keepends=True)
    records = [{'phase': phase, 'start': a, 'end': b,
                'sha256': digest(''.join(lines[a-1:b]).encode())}
               for phase, spans in PHASES.items() for a,b in spans]
    need(len(records) == 57 and len({(x['start'],x['end']) for x in records}) == 57,
         'complete_unique_source_expression_set')
    return records


def artifact_identity(path):
    need(path.is_file() and not path.is_symlink(), 'regular_artifact_required:'+str(path))
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024*1024):
            h.update(block)
    return {'bytes': path.stat().st_size, 'sha256': h.hexdigest()}


def png_dimensions(raw):
    """Validate a complete PNG container and scanline stream, not its scientific content."""
    need(raw[:8] == b'\x89PNG\r\n\x1a\n','native_png_signature')
    position = 8
    chunks = []
    payloads = []
    header = None
    palette = False
    idat_ended = False
    while position < len(raw):
        need(position+12 <= len(raw),'native_png_chunk_extent')
        length = struct.unpack('>I',raw[position:position+4])[0]
        kind = raw[position+4:position+8]
        end = position+12+length
        need(end <= len(raw),'native_png_chunk_extent')
        payload = raw[position+8:position+8+length]
        crc = struct.unpack('>I',raw[position+8+length:end])[0]
        need((zlib.crc32(kind+payload)&0xffffffff) == crc,'native_png_crc')
        need(chunks or kind == b'IHDR','native_png_header_first')
        if kind == b'IHDR':
            need(not chunks and length==13,'native_png_header')
            header = struct.unpack('>IIBBBBB',payload)
        elif kind == b'PLTE':
            need(not palette and not payloads and 0 < length <= 768 and length%3==0,'native_png_palette')
            palette = True
        elif kind == b'IDAT':
            need(not idat_ended,'native_png_IDAT_order')
            payloads.append(payload)
        elif kind == b'IEND':
            need(length==0 and end==len(raw) and payloads,'native_png_complete_end')
        else:
            need(kind and bool(kind[0]&32),'unknown_critical_png_chunk')
        if payloads and kind != b'IDAT':
            idat_ended = True
        chunks.append(kind)
        position = end
    need(header is not None and chunks[-1:]==[b'IEND'],'native_png_complete_container')
    width,height,bits,color,compression,filter_method,interlace = header
    channels = {0:1,2:3,3:1,4:2,6:4}
    bit_options = {0:(1,2,4,8,16),2:(8,16),3:(1,2,4,8),4:(8,16),6:(8,16)}
    need(width>0 and height>0 and color in channels and bits in bit_options[color] and
         compression==0 and filter_method==0 and interlace in (0,1),'native_png_header_fields')
    need(color != 3 or palette,'native_png_palette_required')
    passes = [(0,0,1,1)] if interlace==0 else [(0,0,8,8),(4,0,8,8),(0,4,4,8),
        (2,0,4,4),(0,2,2,4),(1,0,2,2),(0,1,1,2)]
    rows = []
    for x,y,dx,dy in passes:
        pw,ph = max(0,(width-x+dx-1)//dx),max(0,(height-y+dy-1)//dy)
        if pw and ph:
            rows.append((ph,1+(pw*channels[color]*bits+7)//8))
    extent = sum(count*size for count,size in rows)
    need(extent <= 128*1024*1024,'native_png_decoded_extent_limit')
    decoder = zlib.decompressobj()
    decoded = decoder.decompress(b''.join(payloads),extent+1)
    need(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail and len(decoded)==extent,
         'native_png_scanline_stream')
    offset = 0
    for count,size in rows:
        for _ in range(count):
            need(decoded[offset] <= 4,'native_png_scanline_filter')
            offset += size
    return [width,height]


def check_bundle(root, arm, byte_limit, base):
    files = {str(path.relative_to(root)) for path in root.rglob('*') if path.is_file() or path.is_symlink()}
    need(files == set(REQUIRED_ARTIFACTS), 'exact_original_artifact_closure')
    inventory = {name: artifact_identity(root/name) for name in REQUIRED_ARTIFACTS}
    need(all(record['bytes'] > 0 for record in inventory.values()), 'empty_native_artifact')
    need(sum(record['bytes'] for record in inventory.values()) <= byte_limit, 'artifact_byte_limit')
    full120 = base.validate_output((root/'full120.json').read_bytes(), arm, base.public_contract())
    decoder,_ = base.load_validator(base.public_contract())
    json_documents = {name:decoder.decode_numeric_json((root/name).read_bytes()) for name in REQUIRED_ARTIFACTS
                      if name.endswith('.json')}
    ledger = json_documents['row_lineage.json']
    need(ledger['schema']=='nider_primary_native_row_lineage_v1' and ledger['task']==full120['task'] and
         ledger['workbook_sha256']==full120['workbook_sha256'],'row_ledger_identity')
    need(len(ledger['contrasts'])==3,'row_ledger_universe')
    for row,reference in zip(ledger['contrasts'],full120['contrasts']):
        need(row['contrast']==reference['contrast'] and row['membership']==reference['membership'],
             'row_ledger_full120_alignment')
        model,subset,converted,n_column = MODEL_BINDINGS[reference['contrast']]
        need(row['native_model']==model and row['native_subset']==subset and
             row['bayes_input_object']==converted and row['dl_n_column']==n_column and
             row['bayes_n_column']=='sample size quest' and
             all(unit['n_column']==n_column for unit in reference['membership']), 'row_ledger_source_n_choices')
        contrast = reference['contrast']
        forest = json_documents['dl/'+contrast+'.json']
        need(forest['schema']=='nider_original_forest_native_vectors_v1' and forest['contrast']==contrast and
             forest['native_model']==model and forest['membership']==reference['membership'] and
             forest['studlab']==[unit['author_label'] for unit in reference['membership']],
             'native_forest_export_source_alignment')
        bayes = json_documents['bayes/'+contrast+'.json']
        need(bayes['schema']=='nider_original_bma_native_values_v1' and bayes['contrast']==contrast and
             bayes['native_model']=='B'+model, 'native_Bayesian_export_source_alignment')
    for name in FIGURES.values():
        raw = (root/name).read_bytes()
        inventory[name]['png_dimensions'] = png_dimensions(raw)
    runtime = json.loads((root/'runtime.json').read_text())
    need(runtime['evaluated_expression_count'] == 57 and runtime['R_version'] == '4.3.2',
         'runtime_completion_identity')
    need(runtime['full120_frozen_before_Bayesian_mutations'] is True, 'phase_freeze_missing')
    # Native RDS/print/PNG contents need independent native/paper comparison.
    # This check establishes file identity/extent, not scientific agreement.
    return inventory, full120, runtime
