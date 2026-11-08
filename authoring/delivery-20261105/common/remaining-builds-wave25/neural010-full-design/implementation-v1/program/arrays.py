"""Independent bounded full1D prediction admission; never NumPy pickle."""
import ast,math,struct
import common as c

def vector(desc,length,kind,budget,roots):
    c.integer(length,1,86400);c.need(kind in('probabilities','scores'),'prediction vector role')
    itemsize=8 if kind=='probabilities'else 1
    c.need(desc['bytes']<=65548+length*itemsize,'bounded complete vector extent')
    raw=c.capture(desc,budget,roots);c.need(raw[:6]==b'\x93NUMPY','NPY magic')
    version=raw[6:8]
    if version==b'\x01\x00':n=struct.unpack('<H',raw[8:10])[0];offset=10
    elif version==b'\x02\x00':n=struct.unpack('<I',raw[8:12])[0];offset=12
    else:raise ValueError('only explicit NPY versions1/2')
    c.need(0<n<=65536 and offset+n<=len(raw),'bounded exact array header')
    header=ast.literal_eval(raw[offset:offset+n].decode('latin1'));c.exact(header,('descr','fortran_order','shape'))
    c.need(type(header['fortran_order'])is bool and header['fortran_order']is False and type(header['shape'])is tuple and len(header['shape'])==1 and type(header['shape'][0])is int and header['shape']==(length,),'exact one-dimensional prediction support')
    dtype=header['descr'];c.need(dtype in(('<f8','>f8')if kind=='probabilities'else('|u1','<u1','>u1')),'exact binary64 probability oruint8 decision dtype')
    data=raw[offset+n:];c.need(len(data)==length*itemsize,'all vector rows, no trailing bytes')
    values=[x[0]for x in struct.iter_unpack(('<d'if dtype=='<f8'else'>d')if kind=='probabilities'else'B',data)]
    if kind=='probabilities':c.need(all(math.isfinite(x)and 0<=x<=1 for x in values),'complete finite probabilities')
    else:c.need(all(x in(0,1)for x in values),'binary canonical decisions')
    budget.check_clock();return values
