"""Primitive NPY transport only: no interpolation, arithmetic, fitted transform or pickle.

Spatial response selection copies exact binary64 cells into a C-order tensor.
Both source orders are explicit. Nonfinite support and signed zero survive bitwise.
"""
import ast
import itertools
import math
import struct
from common import need


def header(shape,fortran=False):
    need(type(shape)is tuple and 1<=len(shape)<=3 and all(type(x)is int and x>0 for x in shape),'positive bounded axes')
    literal=repr({'descr':'<f8','fortran_order':fortran,'shape':shape}).encode('ascii')
    padded=literal+b' '*((-(10+len(literal)+1))%64)+b'\n'
    return b'\x93NUMPY\x01\x00'+struct.pack('<H',len(padded))+padded


def inspect(raw,shape):
    need(type(raw)is bytes and len(raw)>=10 and raw[:8]==b'\x93NUMPY\x01\x00','exact primitive NPYv1')
    n=struct.unpack('<H',raw[8:10])[0]
    need(0<n<=4096 and 10+n<=len(raw),'bounded NPY header')
    h=raw[10:10+n];need(h.endswith(b'\n'),'terminated header')
    d=ast.literal_eval(h.decode('ascii').strip())
    need(type(d)is dict and set(d)=={'descr','fortran_order','shape'} and d['descr']=='<f8' and type(d['fortran_order'])is bool and d['shape']==tuple(shape),'exact float64 geometry and order')
    need(len(raw)==10+n+math.prod(shape)*8,'exact tensor extent with no trailing data')
    return d['fortran_order'],memoryview(raw)[10+n:]


def select_response(raw,shape,signal_index,time_indices):
    order,payload=inspect(raw,shape);n,signals,times=shape
    need(signals==4 and times==75 and type(signal_index)is int and 0<=signal_index<4,'original full response geometry')
    need(time_indices in (list(range(75)),list(range(38)),list(range(38,75))),'only full or original38/37 indices')
    out=bytearray(header((n,len(time_indices))))
    for row in range(n):
        for t in time_indices:
            i=row+n*(signal_index+signals*t) if order else (row*signals+signal_index)*times+t
            out.extend(payload[i*8:(i+1)*8])
    return bytes(out)
