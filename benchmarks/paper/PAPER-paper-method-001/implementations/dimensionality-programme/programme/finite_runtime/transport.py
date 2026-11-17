"""Exact bounded control trees; scientific records are never truncated to fit frames."""
from __future__ import annotations
import json
from .common import encode,require,FRAME_LIMIT,RESULT_LIMIT,decode

class ParameterTransport:
    def __init__(self,store,prefix,producer,role):
        self.store,self.prefix,self.producer,self.role=store,prefix,producer,role
        self.tables={};self.counter=0

    def externalize(self,value):
        self.store.meter.checkpoint('next_parameter_transport_node')
        if isinstance(value,str) and len(value.encode('utf-8'))>8192:
            self.counter+=1;table=f'table-{self.counter:08d}'
            rows=[{'value':value[i:i+2048]} for i in range(0,len(value),2048)]
            parts=[self._part(table,i,encode(row,RESULT_LIMIT)+b'\n') for i,row in enumerate(rows)]
            self.tables[table]={'parts':parts,'kind':'string','rows':len(rows)}
            return {'$finite_table':table}
        if isinstance(value,dict):
            require('$finite_table' not in value,'RESERVED_TRANSPORT_KEY')
            transformed={k:self.externalize(v) for k,v in value.items()}
        elif isinstance(value,list):transformed=[self.externalize(v) for v in value]
        else:return value
        measured=0
        for piece in json.JSONEncoder(ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).iterencode(transformed):
            measured+=len(piece.encode('utf-8'))
            if measured>8192:break
        if measured<=8192:return transformed
        self.counter+=1;table=f'table-{self.counter:08d}'
        rows=([{'key':k,'value':v} for k,v in transformed.items()] if isinstance(transformed,dict)
              else [{'value':v} for v in transformed])
        parts=[];buffer=[];size=0
        for row in rows:
            self.store.meter.checkpoint('next_parameter_transport_row')
            b=encode(row,RESULT_LIMIT)+b'\n'
            if size+len(b)>FRAME_LIMIT:
                parts.append(self._part(table,len(parts),b''.join(buffer)));buffer=[];size=0
            buffer.append(b);size+=len(b)
        if buffer:parts.append(self._part(table,len(parts),b''.join(buffer)))
        self.tables[table]={'parts':parts,'kind':'dict' if isinstance(transformed,dict) else 'list',
                            'rows':len(rows)}
        return {'$finite_table':table}

    def _part(self,table,index,body):
        return self.store.write(f'{self.prefix}/{table}-{index:08d}.jsonl',body,
             role=self.role,producer=self.producer,media_type='application/x-ndjson')


def resolve_parameter_tree(value,tables,reader,*,max_rows,guard):
    cache={};active=set();total=0
    def resolve(node):
        nonlocal total
        guard('parameter_tree_node')
        if isinstance(node,dict) and '$finite_table' in node:
            require(set(node)=={'$finite_table'},'MIXED_TABLE_REFERENCE')
            key=node['$finite_table'];require(key in tables,'MISSING_PARAMETER_TABLE')
            if key in cache:return cache[key]
            require(key not in active,'PARAMETER_TABLE_CYCLE');active.add(key)
            spec=tables[key];rows=[]
            for part in spec['parts']:
                guard('before_parameter_table_read')
                body=reader(part)
                for line in body.splitlines():
                    guard('next_parameter_table_record');rows.append(decode(line,RESULT_LIMIT));total+=1
                    require(total<=max_rows,'PARAMETER_TABLE_ROW_CAP')
            require(len(rows)==spec['rows'],'PARAMETER_TABLE_CENSUS_MISMATCH')
            if spec['kind']=='dict':
                require(len({x['key'] for x in rows})==len(rows),'DUPLICATE_PARAMETER_KEY')
                out={x['key']:resolve(x['value']) for x in rows}
            elif spec['kind']=='string':
                require(all(type(x.get('value')) is str for x in rows),'INVALID_STRING_TRANSPORT')
                out=''.join(x['value'] for x in rows)
            else:
                require(spec['kind']=='list','UNKNOWN_PARAMETER_CONTAINER')
                out=[resolve(x['value']) for x in rows]
            cache[key]=out;active.remove(key);return out
        if isinstance(node,dict):return {k:resolve(v) for k,v in node.items()}
        if isinstance(node,list):return [resolve(x) for x in node]
        return node
    return resolve(value)
