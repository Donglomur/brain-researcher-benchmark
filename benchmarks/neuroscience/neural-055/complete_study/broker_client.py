"""Participant-facing v3 client; host evidence, never this client, grants trust."""
import hashlib,json,os,time
from pathlib import Path

class Broker:
    def __init__(self):
        self.lease=json.loads(Path('/broker/LEASE.json').read_bytes());self.sequence=0;self.parent=None
    def request(self,provider,operation,payload):
        lease=self.lease
        if time.monotonic()>=lease['deadline']:raise TimeoutError('original phase deadline')
        value={'schema':'neural055-broker-request-v3','lease':lease['lease'],'cell':lease['cell'],'phase':lease['phase'],
               'sequence':self.sequence,'parent_response_sha256':self.parent,'source_sha256':lease['source_sha256'],
               'provider':provider,'operation':operation,'payload':payload}
        raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        if len(raw)>lease['request_bytes']:raise ValueError('bounded request')
        base=Path(lease['requests']);temp=base/(f'{self.sequence:08d}.partial');dest=base/(f'{self.sequence:08d}.json')
        fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o440)
        try:
            pos=0
            while pos<len(raw):
                n=os.write(fd,raw[pos:])
                if n<=0:raise IOError('request write progress')
                pos+=n
            os.fsync(fd)
        finally:os.close(fd)
        temp.rename(dest);reply=Path(lease['replies'])/(f'{self.sequence:08d}.json')
        while not reply.exists():
            if time.monotonic()>=lease['deadline']:raise TimeoutError('original reply deadline')
            time.sleep(.01)
        with reply.open('rb') as stream:body=stream.read(lease['response_bytes']+1)
        if len(body)>lease['response_bytes']:raise ValueError('bounded reply')
        response=json.loads(body)
        if any(response.get(k)!=value[k] for k in ('lease','cell','phase','sequence')) or response.get('request_sha256')!=hashlib.sha256(raw).hexdigest():raise ValueError('crossed original response')
        self.parent=hashlib.sha256(body).hexdigest();self.sequence+=1
        if response['status']!='ok':raise RuntimeError(response['error'])
        return response['result']
