"""Focused invented complete35 transport/header controls; no real connection."""
import copy
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import parse_qs,quote,urlsplit

HERE=Path(__file__).resolve().parent
def load(name):
    spec=importlib.util.spec_from_file_location('fixture_'+name,HERE/'runtime'/(name+'.py'))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
T=load('transport');P=load('header_protocol')
# Invented geometry and routing metadata; no external artifact is opened.
ANIMALS=load('route_contract').ANIMALS
ROWS=[dict(index=i,file_id=x[0],bytes=x[1],animal_id=ANIMALS[i//5],
      relative_path=ANIMALS[i//5]+'/'+x[2],canonical_download_url=x[3],published_computed_md5=x[4])
      for i,x in enumerate(T.PINNED)]
IDS={x[0]:{'scheme':'https','authority':'44c1cec316ec56bca76dfd65d2882b20.r2.cloudflarestorage.com',
      'path':'/figshare-com-storage/'+str(x[0])+'/'+x[2],
      'non_auth_query':['response-content-disposition=attachment','response-content-type=application%2Foctet-stream']}
      for x in T.PINNED}
ASSETS=[dict(zip(T.FIELDS,x)) for x in T.PINNED]
CLOCK=1794835858.0
DATE=datetime.datetime.fromtimestamp(CLOCK,datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
def header(meta,version=1):
    width=2 if version==1 else 4
    extent=128
    text=repr(meta).encode('ascii')
    size=extent-8-width
    assert len(text)<size
    b=b'\x93NUMPY'+bytes([version,0])+size.to_bytes(width,'little')+text+b' '*(size-len(text)-1)+b'\n'
    assert len(b)==128
    return b
def url(fid):
    x=IDS[fid]
    auth=[('X-Amz-Algorithm','AWS4-HMAC-SHA256'),('X-Amz-Credential','invented/20261116/auto/s3/aws4_request'),
          ('X-Amz-Date',DATE),('X-Amz-Expires','10'),('X-Amz-SignedHeaders','host'),('X-Amz-Signature','a'*64)]
    return 'https://'+x['authority']+x['path']+'?'+'&'.join(x['non_auth_query']+
        [k+'='+quote(v,safe='') for k,v in auth])

class Response:
    def __init__(self,status,headers,body=b''):
        self.status=status;self.headers=headers;self.body=body;self.closed=False;self.reads=[]
    def getheaders(self):return self.headers
    def read(self,n):
        self.reads.append(n);out=self.body[:n];self.body=self.body[n:];return out
    def close(self):self.closed=True

class Factory:
    def __init__(self,mode=None):
        self.calls=[];self.responses=[];self.connections=[];self.mode=mode
    def __call__(self,host,timeout):
        factory=self
        class Connection:
            def __init__(self):self.closed=False;self.observed_response=None;factory.connections.append(self)
            def request(self,method,path,headers):
                assert method=='GET'
                self.method,self.path,self.headers=method,path,headers
                factory.calls.append((host,method,path,dict(headers)))
            def getresponse(self):
                if host=='ndownloader.figshare.com':
                    fid=int(self.path.rsplit('/',1)[-1]);location=url(fid)
                    if factory.mode=='extra_query':location+='&extra=invented'
                    r=Response(302,[('Location',location),('Content-Length','0')])
                else:
                    fid=int(urlsplit(self.path).path.split('/')[2])
                    asset=next(x for x in T.PINNED if x[0]==fid)
                    bounds=self.headers['Range'][6:];lo,hi=map(int,bounds.split('-'));count=hi-lo+1
                    meta={'descr':'|u1','shape':(asset[1]-128,),'fortran_order':False}
                    data=header(meta,1 if T.PINNED.index(asset)%2==0 else 2)
                    assert hi<128,'generated source must never access even an invented numerical payload'
                    etag='"fixture-%d"'%fid
                    if factory.mode=='etag_change' and lo==8:etag='"changed"'
                    status=200 if factory.mode=='status200' else 206
                    hs=[('Content-Range','bytes %d-%d/%d'%(lo,hi,asset[1])),('Content-Length',str(count)),('ETag',etag)]
                    if factory.mode=='duplicate_etag':hs.append(('ETag',etag))
                    r=Response(status,hs,data[lo:hi+1])
                self.observed_response=r;factory.responses.append(r);return r
            def close(self):self.closed=True
        return Connection()

class Complete(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='consensus35-header-generated-')
        self.old_socket=socket.socket
        socket.socket=lambda *a,**k: (_ for _ in ()).throw(AssertionError('real socket forbidden'))
    def tearDown(self):
        socket.socket=self.old_socket;self.tmp.cleanup()
    def make(self,mode=None,now=CLOCK):
        f=Factory(mode)
        tr=T.RangeTransport(Path(self.tmp.name).resolve()/('case%d'%len(list(Path(self.tmp.name).iterdir()))),
            ASSETS,copy.deepcopy(IDS),connector=f,utc_clock=lambda:now)
        return tr,f
    def test_complete35_210_requests_fresh_signature_and_header_only(self):
        tr,f=self.make()
        with tr:result=P.collect(ROWS,tr)
        self.assertEqual((len(result['headers']),tr.range_attempts,tr.transactions,tr.redirects),(35,105,210,105))
        self.assertEqual(tr.body_returned,35*128)
        self.assertTrue(all(r.closed for r in f.responses))
        self.assertTrue(all(c.closed for c in f.connections))
        self.assertEqual(sum(len(r.reads) for r in f.responses),105)
        self.assertTrue(all(len(r.reads)<=1 for r in f.responses))
        self.assertTrue(all(c[0]=='ndownloader.figshare.com' for c in f.calls[::2]))
        self.assertTrue(all(c[0]==T.urlsplit(url(T.PINNED[0][0])).hostname for c in f.calls[1::2]))
        self.assertTrue(all('If-Match' not in c[3] for c in f.calls[:70]))
        self.assertTrue(all('If-Match' in c[3] for c in f.calls[70:]))
        self.assertFalse(result['geometry']['all_necessary_header_conditions_pass'])
        self.assertFalse(result['scientific_readiness'])
        self.assertEqual([h['NPY_version'] for h in result['headers'][:2]],[[1,0],[2,0]])
    def test_all35_prefix_barrier_and_no_repeat(self):
        tr,f=self.make()
        tr.fetch(ASSETS[0],0,8,'f00-magic')
        with self.assertRaises(T.RangeError):tr.fetch(ASSETS[0],8,2,'f00-length')
        self.assertEqual(len(f.calls),2)
        with self.assertRaises(T.RangeError):tr.fetch(ASSETS[1],0,8,'f01-magic')
        self.assertEqual(len(f.calls),2)
        tr.close()
    def test_status_duplicate_etag_and_expired_or_changed_route_read_no_body(self):
        for mode,now,transactions in [('status200',CLOCK,2),('duplicate_etag',CLOCK,2),
                                      ('extra_query',CLOCK,1),(None,CLOCK+20,1)]:
            tr,f=self.make(mode,now)
            with self.assertRaises(T.RangeError):tr.fetch(ASSETS[0],0,8,'f00-magic')
            self.assertEqual(len(f.calls),transactions)
            self.assertTrue(all(not r.reads and r.closed for r in f.responses))
            self.assertTrue(all(c.closed for c in f.connections))
            tr.close()
    def test_later_etag_change_refuses_before_length_body(self):
        tr,f=self.make('etag_change')
        for i,a in enumerate(ASSETS):tr.fetch(a,0,8,'f%02d-magic'%i)
        with self.assertRaises(T.RangeError):tr.fetch(ASSETS[0],8,2,'f00-length')
        self.assertEqual(len(f.calls),72)
        self.assertEqual(sum(sum(r.reads) for r in f.responses),35*8)
        self.assertTrue(all(r.closed for r in f.responses));tr.close()
    def test_standalone_parser_exact_extent_and_unsupported_values(self):
        for version in (1,2):
            data=header({'descr':'<f8','shape':(2,3,4),'fortran_order':True},version)
            r=dict(ROWS[0],bytes=128+192)
            calls=[]
            def fetch(label,start,count):
                calls.append((label,start,count));return data[start:start+count]
            h=P.remaining_header(0,r,data[:8],fetch)
            self.assertEqual((h['NPY_header_bytes'],h['numeric_payload_bytes_declared']),(128,192))
            self.assertEqual(calls[0],('f00-length',8,2 if version==1 else 4))
            self.assertEqual(max(s+n for _,s,n in calls),128)
            self.assertEqual(h['NPY_header_sha256'],hashlib.sha256(data).hexdigest())
            with self.assertRaises(ValueError):P.remaining_header(0,dict(r,bytes=r['bytes']+1),data[:8],fetch)
        data=header({'descr':'|O','shape':(2,),'fortran_order':False})
        with self.assertRaises(ValueError):
            P.remaining_header(0,dict(ROWS[0],bytes=144),data[:8],lambda l,s,n:data[s:s+n])
    def test_full_population_geometry_and_explicit_incompatibility(self):
        hs=[]
        for r in ROWS:
            leaf=r['relative_path'].split('/')[-1]
            shape=[2,2,105] if leaf in ('all_lm_cells.npy','all_v1_cells.npy') else[2,2] if leaf=='unique_ids.npy' else[2,1]
            hs.append(dict(index=r['index'],file_id=r['file_id'],animal_id=r['animal_id'],
                relative_path=r['relative_path'],shape=shape,dtype='<f8'))
        g=P.geometry(hs,ROWS)
        self.assertTrue(g['all_necessary_header_conditions_pass'])
        self.assertEqual(g['conditional_count_JSON_upper_bytes'],7*2*((17*4+2)*5+2))
        bad=copy.deepcopy(hs);bad[2]['shape']=[2]
        self.assertFalse(P.geometry(bad,ROWS)['all_necessary_header_conditions_pass'])
        with self.assertRaises(ValueError):P.geometry(hs[:-1],ROWS)
if __name__=='__main__':unittest.main(verbosity=2)

