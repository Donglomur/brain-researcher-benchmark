"""Rebuild exact annotation join from held publisher metadata; no EEG access."""
import argparse
import hashlib
from pathlib import Path
import re
from urllib.parse import unquote
import io_contract as io


def compile_annotations(lock,metadata):
    def pinned(name,sha):
        body=io.read(metadata/name,1000000);io.need(hashlib.sha256(body).hexdigest()==sha,'publisher metadata pin');return body
    records=pinned('RECORDS',lock['records_manifest_sha256']).decode().splitlines()
    records=[r for r in records if r.strip()]
    positives=set(pinned('RECORDS-WITH-SEIZURES',lock['positive_manifest_sha256']).decode().split())
    io.need('chb07/chb07_18.edf' in positives and 'chb07/chb07_19.edf' not in positives,'only documented publisher conflict')
    positives.remove('chb07/chb07_18.edf');positives.add('chb07/chb07_19.edf')
    parsed={};companions=set()
    for asset in lock['summaries']:
        case=asset['path'].split('/')[0];body=pinned(case+'-summary.txt',asset['sha256']).decode('ascii')
        blocks=re.split(r'^File Name:\s*',body,flags=re.M)[1:]
        for block in blocks:
            name=block.splitlines()[0].strip();path=case+'/'+name
            counts=re.findall(r'^Number of Seizures in File:\s*(\d+)',block,re.M)
            start=re.findall(r'^Seizure(?: \d+)? Start Time:\s*(\d+) seconds',block,re.M)
            end=re.findall(r'^Seizure(?: \d+)? End Time:\s*(\d+) seconds',block,re.M)
            io.need(path not in parsed and len(counts)==1 and len(start)==len(end)==int(counts[0]),'one explicit exact summary join')
            events=[[float(a),float(b)] for a,b in zip(start,end)]
            io.need(all(a<b for a,b in events),'ordered annotation endpoints')
            parsed[path]={'events':events,'evidence':'summary_explicit_count','summary':asset['path']}
        html=io.read(metadata/(case+'-index.html'),1000000).decode()
        for href in re.findall(r'href="([^"]+)"',html):
            name=unquote(href)
            if name.endswith('.edf.seizures'):companions.add(case+'/'+name[:-9])
    io.need(positives==companions and len(positives)==141,'corrected exhaustive positive/companion identity')
    io.need(parsed['chb07/chb07_18.edf']['events']==[] and parsed['chb07/chb07_19.edf']['events']==[[13688.,13831.]],'explicit localized correction')
    # Preserve the independent publisher companion that corroborates the correction.
    pinned('chb07_19.edf.seizures','f70b7cf41c1384e181e22873cb01096be28b4ac6eb67b4bd73220e6535949b5e')
    result={}
    for row in lock['records']:
        path=row['path'];io.need(path in records,'exact release membership')
        if path in parsed:result[path]=parsed[path]
        else:
            io.need(row['case']=='chb24' and path not in positives,'no silent missing-label negative')
            result[path]={'events':[],'evidence':'publisher_positive_inventory_negative','summary':None}
        io.need(bool(result[path]['events'])==(path in positives),'summary/positive agreement')
    io.need(len(records)==len(set(records))==len(result)==686 and set(parsed)<=set(result)
            and sum(len(r['events']) for r in result.values())==198,'full exact source annotation support')
    return {'task_id':io.TASK,'records':result}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('lock','metadata','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();io.write(a.output,compile_annotations(io.strict(io.read(a.lock,1000000)),a.metadata))
