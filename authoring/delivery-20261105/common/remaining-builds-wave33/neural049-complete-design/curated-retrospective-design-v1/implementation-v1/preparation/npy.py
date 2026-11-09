"""Concrete primitive NPY stream writer and strict bounded header parser."""
import ast
import struct
from contextlib import contextmanager
from . import contracts as c

def header(shape,dtype):
    c.shape_bytes(shape,dtype)
    value={'descr':dtype,'fortran_order':False,'shape':tuple(shape)}
    body=repr(value).encode('ascii')
    pad=(- (10+len(body)+1))%64
    body+=b' '*pad+b'\n'
    c.need(len(body)<=65535,'NPY v1 header bound')
    return b'\x93NUMPY\x01\x00'+struct.pack('<H',len(body))+body

def inspect(f,extent,shape,dtype,budget):
    c.need(c.integer(extent),'NPY extent')
    n,payload=c.shape_bytes(shape,dtype);budget.elements(n)
    pre=f.read(10);c.need(len(pre)==10 and pre[:8]==b'\x93NUMPY\x01\x00','primitive NPY1 header')
    size=struct.unpack('<H',pre[8:])[0];c.need(0<size<=65535 and 10+size+payload==extent,'NPY exact bounded payload extent')
    with budget.hold(8*size+4096,'NPY header parser'):
        body=f.read(size);c.need(len(body)==size and body.endswith(b'\n'),'complete NPY header')
        expression=ast.parse(body.decode('ascii').strip(),mode='eval')
        c.need(isinstance(expression.body,ast.Dict) and len(expression.body.keys)==3
               and all(isinstance(k,ast.Constant) and type(k.value) is str for k in expression.body.keys),'primitive literal header')
        value=ast.literal_eval(expression)
        c.need(type(value) is dict and set(value)=={'descr','fortran_order','shape'}
               and value['descr']==dtype and value['fortran_order'] is False and type(value['shape']) is tuple
               and list(value['shape'])==list(shape) and all(c.integer(v) for v in value['shape']), 'NPY schema')
    budget.tick();return 10+size

class Stream:
    def __init__(self,f,shape,dtype,budget):
        self.f,self.shape,self.dtype,self.budget=f,list(shape),dtype,budget
        _,self.expected=c.shape_bytes(shape,dtype);self.written=0
        f.write(header(shape,dtype))
    def write(self,array):
        # numpy arrays are created only in the separately selected concrete preparation.
        c.need(type(array).__name__=='ndarray' and array.dtype.str==self.dtype
               and array.flags.c_contiguous,'exact primitive contiguous output array')
        n=array.nbytes;c.need(self.written+n<=self.expected,'NPY payload bound')
        self.budget.tick();self.f.write(memoryview(array).cast('B'));self.written+=n
    def finish(self):
        c.need(self.written==self.expected,'full NPY payload required');self.budget.tick()

@contextmanager
def writer(store,root,rel,shape,dtype,private=False):
    n,_=c.shape_bytes(shape,dtype);store.meter.elements(n)
    with store.writer(root,rel,private=private) as f:
        stream=Stream(f,shape,dtype,store.meter)
        yield stream
        stream.finish()

def describe(store,root,rel,shape,dtype):
    d=store.describe(root,rel)
    return {'path':rel,**d['pin'],'dtype':dtype,'shape':list(shape)}

def descriptor(d):
    c.array_descriptor(d)
    return {'path':d['path'],'pin':{'bytes':d['bytes'],'sha256':d['sha256']}}
