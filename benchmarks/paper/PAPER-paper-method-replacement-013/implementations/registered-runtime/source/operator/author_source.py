"""Verify the selected original text snapshot without importing author modules."""
import argparse,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'public'))
from io_contract import *

def source_root():
    return ROOT/'public/official_code'

def captured_source():
    index=ROOT/'operator/CODE_INDEX.json'
    require(index.is_file(),'official source snapshot unprovisioned')
    value=load(index);require(value['commit']==REVISION and type(value['files']) is list and value['files'],'exact selected author revision')
    names=[];bodies={}
    for r in value['files']:
        name=r['path'];parts=Path(name).parts
        require(type(name) is str and not Path(name).is_absolute() and '..' not in parts and str(Path(name))==name,'safe source path')
        source=source_root()
        for part in parts:source=source/part;require(not source.is_symlink(),'no original-source symlinks')
        b=capture(source,5_000_000);b.decode('utf8');distributed=b;sha256(r['sha256'])
        if 'public_distribution' in r:
            d=r['public_distribution'];prefix=d['notice_prefix'].encode('utf8')
            require(d['path']==name and d['notice_only'] is True and len(b)==d['bytes'] and hashlib.sha256(b).hexdigest()==d['sha256'],'exact public source distribution')
            require(prefix and all(not line.strip() or line.lstrip().startswith(b'#') for line in prefix.splitlines()),'comment-only notice prefix')
            require(b.startswith(prefix),'exact public notice prefix');b=b[len(prefix):]
        require(len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'],'exact source text pin')
        if 'git_blob_sha' in r:require(hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==r['git_blob_sha'],'original Git blob identity')
        names.append(name);bodies[name]=distributed
    require(len(names)==len(set(names)),'unique selected original files')
    return bodies

def captured_notices():
    """Capture all exact licenses/notices for every separated official-code view."""
    value=load(ROOT/'operator/NOTICE_INDEX.json')
    require(value['schema']=='neuroformer_public_notices_v1' and value['original_code_files']==26,'notice inventory')
    result={}
    for row in value['files']:
        name=row['path'];require(type(name) is str and '/' not in name and name not in ('','.','..') and name not in result,'notice basename')
        path=source_root()/name;require(not path.is_symlink(),'no notice symlink')
        b=capture(path,1_048_576);b.decode('utf8')
        require(len(b)==row['bytes'] and hashlib.sha256(b).hexdigest()==row['sha256'],'exact source notice')
        result[name]=b
    require(len(result)==7,'complete seven-file notice inventory')
    return result

def verify():
    bodies=captured_source();notices=captured_notices()
    return {'schema':'neuroformer_public_original_text_check_v1','commit':REVISION,'files':len(bodies),'bytes':sum(map(len,bodies.values())),'original_bytes':375148,'public_notice_files':len(notices),'scientific_body_change':False,'author_imports':0,'model_or_data_calls':0}

def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--check-source',action='store_true',required=True);a.parse_args();print(encode(verify()).decode(),end='')
if __name__=='__main__':main()
