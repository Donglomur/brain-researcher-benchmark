"""Original prepared packet reader; no NWB discovery, inferred axes or pickle."""
import ast,io,math,struct,sys,zipfile
from array import array
from .storage import decode,digest
from gain.features import inspect_metadata
ROSTER_SHA256='9afc2888bf5200c0362d5adbc951fc90cce2c5e120d58fe00bb83aa5926949fb'
FILE_CAP=134217728

def count_plane(raw,rows,units,ledger):
    # Original prepare.py writes exactly counts.npy, signed int64, row-major
    # trial x original selected-unit order. Read header only inside this future
    # invoked function; no authentic header is opened during construction.
    with zipfile.ZipFile(io.BytesIO(raw))as z:
        infos=z.infolist()
        if len(infos)!=1:raise ValueError('one original count member')
        inf=infos[0]
        if inf.filename!='counts.npy'or inf.flag_bits&1 or inf.is_dir()or inf.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):raise ValueError('original primitive NPZ member')
        if inf.file_size>FILE_CAP or inf.file_size<8*rows*units or inf.file_size>8*rows*units+65548:raise ValueError('decoded extent')
        ledger.take('decoded_bytes',inf.file_size)
        with z.open(inf)as f:
            if f.read(6)!=b'\x93NUMPY':raise ValueError('NPY magic')
            ver=tuple(f.read(2))
            if ver not in ((1,0),(2,0)):raise ValueError('original NPY version')
            n=struct.unpack('<H'if ver==(1,0)else'<I',f.read(2 if ver==(1,0)else 4))[0]
            if n>65536:raise ValueError('bounded NPY header')
            h=ast.literal_eval(f.read(n).decode('latin1'))
            if type(h)is not dict or set(h)!={'descr','fortran_order','shape'}or h['shape']!=(rows,units)or h['fortran_order']is not False or h['descr']not in ('<i8','>i8'):raise ValueError('exact original int64 trial/unit axes')
            b=f.read(8*rows*units+1)
            if len(b)!=8*rows*units:raise ValueError('exact payload and EOF')
    out=array('q');out.frombytes(b)
    if out.itemsize!=8:raise RuntimeError('signed int64 platform')
    if (h['descr'][0]=='<')!=(sys.byteorder=='little'):out.byteswap()
    if any(v<0 for v in out):raise ValueError('negative original count')
    return out

def prediction_plane(raw,rows,units):
    if len(raw)!=8*rows*units:raise ValueError('full prediction extent')
    a=array('d');a.frombytes(raw)
    if a.itemsize!=8:raise RuntimeError('float64 platform')
    if sys.byteorder!='little':a.byteswap()
    if any(not math.isfinite(x)or x<=0 for x in a):raise ValueError('positive finite full predictions')
    return a

def array_bytes(a):
    out=array(a.typecode,a)
    if out.itemsize!=8:raise RuntimeError('eight-byte array')
    if sys.byteorder!='little':out.byteswap()
    return out.tobytes()

class Packet:
    def __init__(self,source,selected,ledger):
        self.source=source;self.ledger=ledger;self.selected=selected
        roster=source.json(selected['roster']['path'],selected['roster']['pin'],25000000)
        if selected['roster']['pin']['sha256']!=ROSTER_SHA256:raise ValueError('original cohort pin')
        self.index=source.json(selected['index']['path'],selected['index']['pin'],30000000)
        if set(self.index)!={'schema','task_id','roster_sha256','sessions','limitations'}or self.index['schema']!='neuropixels_task_packet_v1'or self.index['task_id']!='NEURAL-092'or self.index['roster_sha256']!=ROSTER_SHA256:raise ValueError('original packet index')
        cohort={r['session_id']:r['donor_id']for r in roster['sessions']}
        self.entries={r['session_id']:r for r in self.index['sessions']}
        if len(cohort)!=32 or len(roster['sessions'])!=32 or len(set(cohort.values()))!=32 or len(self.entries)!=32 or len(self.index['sessions'])!=32 or set(self.entries)!=set(cohort):raise ValueError('full32 original cohort; optical cohort not admitted')
        self.metadata={};self.infos={}
        from prospective.phase_projection import project_prediction_index
        project_prediction_index(self.index,list(cohort))
        for sid,e in self.entries.items():
            if e['mouse_id']!=cohort[sid]:raise ValueError('original animal join')
            d=e['metadata'];m=source.json(d['path'],{k:d[k]for k in ('bytes','sha256')},30000000)
            if set(m)!={'schema','task_id','session_id','mouse_id','unit_ids','areas','unit_metadata','rows','baseline_rates','support','exposure_seconds','state_policy'}:raise ValueError('closed original metadata; no undeclared payload')
            for row in m['rows']:
                if set(row)!={'id','family','onset','stop','block','split','features','window','condition_key','running_cm_per_s','pupil_area','run_bin','pupil_bin'}:raise ValueError('closed original trial metadata')
            if m['session_id']!=sid or m['mouse_id']!=cohort[sid]:raise ValueError('metadata cohort axes')
            info=inspect_metadata(m);self.metadata[sid]=m;self.infos[sid]=info
            # Independent root selection provides expected counts for pre-allocation
            # admission, but never substitutes for the actual original metadata.
            dims=selected['dimensions'][sid]
            actual={p:len(info['rows'][p])for p in ('FIT','VALIDATION','QUERY')}
            actual.update(units=len(info['unit_ids']),categories=len(info['vocabulary']))
            if dims!=actual:raise ValueError('selected complete dimension inverse')
        if set(selected['dimensions'])!=set(cohort):raise ValueError('dimension cohort')
    def counts(self,sid,phase):
        d=self.entries[sid]['counts'][phase];b=self.source.read(d['path'],{k:d[k]for k in ('bytes','sha256')},FILE_CAP)
        i=self.infos[sid];return count_plane(b,len(i['rows'][phase]),len(i['unit_ids']),self.ledger)
    def view(self,store,observed=False):
        rows=[]
        for sid,e in self.entries.items():
            phases=('FIT','VALIDATION','QUERY')if observed else('FIT','VALIDATION')
            entry={'session_id':sid,'mouse_id':e['mouse_id'],'metadata':dict(e['metadata']),'counts':{p:dict(e['counts'][p])for p in phases}}
            for d in [entry['metadata'],*entry['counts'].values()]:
                b=self.source.read(d['path'],{k:d[k]for k in ('bytes','sha256')},FILE_CAP)
                store.put(d['path'],b)
            rows.append(entry)
        from .storage import encode
        # The original index is private; publish a new closed derived view.
        idx={**self.index,'sessions':rows};store.put('public/INDEX.json',encode(idx))
        return idx
