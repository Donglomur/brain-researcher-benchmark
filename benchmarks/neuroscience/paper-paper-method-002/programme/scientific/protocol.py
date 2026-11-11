"""Actual bounded producer input/output path used by the fixed native driver.

These objects are local scientific I/O owners, not native-authority issuers.
The outer controller still verifies sealed mounts, waits and complete outputs.
"""
import hashlib
import io
import os
import stat
import time
from runtime.strict import require, integer, relative, decode, canonical_bytes, digest

DTYPES={'float64-le':'<f8','float32-le':'<f4','int64-le':'<i8','uint8':'u1'}

class Failure:
    def __init__(self):self.errors=[];self.prefixes=[]
    def catch(self,e):self.errors.append(e)
    def close(self,fd):
        try:os.close(fd)
        except BaseException as e:self.catch(e)
    def raise_first(self):
        if self.errors:raise self.errors[0]

class JobContext:
    """Closed per-job scientific contract; no caller supplied function selectors."""
    def __init__(self,job,input_root,output_root):
        require(type(job)is dict and job['group']in tuple('J%02d'%i for i in range(1,37)),'group')
        require(type(job['action'])is str and type(job['config'])is dict,'scientific action/config')
        self.group=job['group'];self.action=job['action'];self.config=job['config'];self.job=job
        self.input_root=input_root;self.output_root=output_root
        require(input_root.path=='/inputs'and output_root.path=='/output','fixed source mounts')
        self.deadline=integer(job['native_deadline_ns'],'original native deadline',1)
        self.limits=job['producer_limits']
        for k in ('input_bytes','input_member_bytes','output_bytes','output_member_bytes','array_memory_bytes','log_bytes'):
            integer(self.limits[k],k,1)
        inputs=job['native_inputs'];require(type(inputs)is list,'original input roster')
        require(all(type(r)is dict and type(r['logical'])is str for r in inputs),'input descriptors')
        self.inputs={r['logical']:r for r in inputs};require(len(self.inputs)==len(inputs),'duplicate logical input')
        products=job['output_contract']['outputs'];self.products={p['artifact_id']:p for p in products}
        require(len(self.products)==len(products)and products,'closed complete output roster')
        self.used_read=0;self.used_write=0;self.log=[];self.rows={};self.failure=Failure();self.finished=False
        self.checkpoint()
    def checkpoint(self):
        self.failure.raise_first();require(not self.finished,'retired producer')
        require(time.monotonic_ns()<self.deadline,'original producer deadline exhausted')
    def _read(self,row,retain,root=None):
        self.checkpoint();n=integer(row['bytes'],'exact input extent')
        root=self.input_root if root is None else root
        member_limit=self.limits['input_member_bytes'if root is self.input_root else'output_member_bytes']
        require(n<=member_limit,'input member limit')
        require(self.used_read+n+1<=self.limits['input_bytes'],'complete read plus EOF not admitted')
        relative(row['path']);owner=Failure();fd=None;parent=None;prefix=[];total=0;h=hashlib.sha256()
        try:
            parent,leaf=root.parent(row['path'])
            fd=os.open(leaf,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
            before=os.fstat(fd)
            require(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_size==n,'pinned regular native input')
            while True:
                self.checkpoint();block=os.read(fd,min(65536,n-total+1));self.used_read+=len(block)
                owner.prefixes.append(block)
                if not block:break
                total+=len(block);require(total<=n,'input grew');h.update(block)
                if retain:prefix.append(block)
                owner.prefixes.clear()
            after=os.fstat(fd)
            require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'input changed')
            require(total==n and h.hexdigest()==row['sha256'],'original input byte identity')
        except BaseException as e:owner.catch(e)
        finally:
            if fd is not None:owner.close(fd)
            if parent is not None:owner.close(parent)
        if owner.errors:self.failure.prefixes.extend([owner,prefix]);self.failure.errors.extend(owner.errors);owner.raise_first()
        return b''.join(prefix)if retain else None
    def input_path(self,logical_name):
        require(logical_name in self.inputs,'undeclared native input')
        row=self.inputs[logical_name];self._read(row,False)
        # Static input mounts must remain sealed for the native library open.
        # Hashing alone is not immutability or native deployment qualification.
        return self.input_root.path+'/'+row['path']
    def read_source(self,logical_name):
        require(logical_name in self.inputs,'undeclared ordinary source input')
        row=self.inputs[logical_name];require(row['format']=='utf8-source','explicit source-only format')
        require(row['bytes']*4<=self.limits['array_memory_bytes'],'complete source decoder/AST allocation bound')
        raw=self._read(row,True);raw.decode('utf8');require(b'\0'not in raw,'ordinary source bytes')
        return raw
    def read_json(self,logical_name):
        require(logical_name in self.inputs,'undeclared JSON input')
        row=self.inputs[logical_name];require(row['format']=='json','JSON source format')
        require(row['bytes']*3<=self.limits['array_memory_bytes'],'bounded JSON body/decoder allocation estimate')
        return decode(self._read(row,True))
    def read_array(self,logical_name):
        require(logical_name in self.inputs,'undeclared array input');row=self.inputs[logical_name]
        require(row['format']in('npy','jaxley-flat-numeric-v1')and row['dtype']in DTYPES,'non-pickle native array format')
        require(row['bytes']*3<=self.limits['array_memory_bytes'],'complete raw/decoder/array memory reservation')
        import numpy as np
        raw=self._read(row,True)
        if row['format']=='npy':value=np.load(io.BytesIO(raw),allow_pickle=False)
        else:
            count=1
            for extent in row['shape']:count*=integer(extent,'exact source axis',1)
            require(count*np.dtype(DTYPES[row['dtype']]).itemsize==len(raw),'flat input byte/shape inverse')
            value=np.frombuffer(raw,dtype=DTYPES[row['dtype']]).reshape(row['shape'])
        require(type(value)is np.ndarray and value.dtype==np.dtype(DTYPES[row['dtype']]),'exact numeric dtype')
        require(list(value.shape)==row['shape']and np.isfinite(value).all(),'complete finite array support')
        return value
    def record(self,name,value):
        self.checkpoint();require(type(name)is str and name,'operation record name')
        row={'name':name,'value':value};prospective=canonical_bytes(self.log+[row])
        require(len(prospective)<=self.limits['log_bytes'],'operation log bound');self.log.append(row)
    def _emit(self,product_id,chunks,extent):
        self.checkpoint();require(product_id in self.products and product_id not in self.rows,'closed once-only product')
        require(extent<=self.limits['output_member_bytes']and self.used_write+extent<=self.limits['output_bytes'],'output admission')
        p=self.products[product_id]
        if self.job.get('route')=='prospective_full_scientific_source_v1':
            require(extent<=p['extent']['bytes'],'whole selected per-product extent exceeded')
            if p['extent']['kind']=='exact':require(extent==p['extent']['bytes'],'exact whole product extent changed')
        path='product-'+str(list(self.products).index(product_id)).zfill(3)+('.json'if p['format']=='json'else'.bin')
        owner=Failure();fd=None;parent=None;h=hashlib.sha256();total=0
        try:
            parent,leaf=self.output_root.parent(path)
            fd=os.open(leaf,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
            for block in chunks:
                require(type(block)is bytes,'output chunk bytes');owner.prefixes[:]=[block]
                require(total+len(block)<=extent,'producer extent changed')
                pos=0
                while pos<len(block):
                    self.checkpoint();n=os.write(fd,block[pos:]);require(n>0,'zero write')
                    self.used_write+=n;total+=n;h.update(block[pos:pos+n]);pos+=n
                owner.prefixes.clear()
            require(total==extent,'producer output incomplete');os.fsync(fd);os.fsync(parent)
        except BaseException as e:owner.catch(e)
        finally:
            if fd is not None:owner.close(fd)
            if parent is not None:owner.close(parent)
        if owner.errors:self.failure.prefixes.append(owner);self.failure.errors.extend(owner.errors);owner.raise_first()
        row={**p,'path':path,'bytes':total,'sha256':h.hexdigest()}
        # Complete readback is an additional read charge, not part of output bytes.
        require(self.used_read+total+1<=self.limits['input_bytes'],'output readback not admitted')
        self._read(row,False,root=self.output_root)
        self.rows[product_id]=row
    def emit_json(self,product_id,value):
        require(self.products[product_id]['format']=='json','JSON output contract')
        if self.job.get('route')=='prospective_full_scientific_source_v1':
            from .json_extent import require_json_product
            require_json_product(value,self.products[product_id])
        body=canonical_bytes(value);self._emit(product_id,[body],len(body))
    def emit_numeric(self,product_id,array):
        self.checkpoint();p=self.products[product_id]
        require(p['format']=='jaxley-flat-numeric-v1'and p['dtype']in DTYPES,'flat output contract')
        import numpy as np
        value=np.asarray(array);target=np.dtype(DTYPES[p['dtype']])
        require(value.dtype.kind in 'fiu'and list(value.shape)==p['shape'],'complete output shape/dtype')
        require(np.isfinite(value).all(),'nonfinite scientific product')
        if target.kind in 'iu':
            bounds=np.iinfo(target);require(np.logical_and(value>=bounds.min,value<=bounds.max).all()and np.equal(value,np.trunc(value)).all(),'integer narrowing changes values')
        elif value.dtype.kind=='f':require(target.itemsize>=value.dtype.itemsize,'floating storage narrowing is not a selected scientific method')
        require(value.nbytes+value.size*target.itemsize+65536<=self.limits['array_memory_bytes'],'array plus conversion/chunk reservation')
        converted=np.asarray(value,dtype=target,order='C')
        require(np.isfinite(converted).all(),'conversion overflow')
        if p['unit']=='boolean':require(target==np.dtype('u1')and np.logical_or(converted==0,converted==1).all(),'boolean product')
        flat=converted.reshape(-1);width=target.itemsize
        self._emit(product_id,(flat[i:i+65536//width].tobytes()for i in range(0,flat.size,65536//width)),flat.size*width)
    def finish(self):
        self.checkpoint();require(set(self.rows)==set(self.products),'missing required scientific output')
        job=self.job;receipt={'schema':'jaxley_complete_job_output_v1','job_id':job['job_id'],'condition':job['condition'],
            'contract_sha256':digest(canonical_bytes(job['output_contract'])),'source_profile_sha256':job['source_profile_sha256'],
            'producer_source_sha256':job['producer_source_sha256'],'artifacts':[self.rows[k]for k in self.products],
            'method_operations':self.log,'native_qualification':False,'local_read_bytes':self.used_read,'local_output_bytes_before_receipt':self.used_write}
        body=canonical_bytes(receipt);require(self.used_write+len(body)<=self.limits['output_bytes'],'receipt-inclusive output bound')
        if self.job.get('route')=='prospective_full_scientific_source_v1':require(len(body)<=self.job['metadata_limits']['receipt_bytes'],'full receipt extent not admitted')
        owner=Failure();parent=None;fd=None;offset=0
        try:
            parent,leaf=self.output_root.parent('result.json')
            fd=os.open(leaf,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
            owner.prefixes[:]=[body]
            while offset<len(body):
                self.checkpoint();n=os.write(fd,body[offset:offset+65536]);require(n>0,'zero receipt write')
                offset+=n;self.used_write+=n
            os.fsync(fd);os.fsync(parent);owner.prefixes.clear()
        except BaseException as e:owner.catch(e)
        finally:
            if fd is not None:owner.close(fd)
            if parent is not None:owner.close(parent)
        if owner.errors:self.failure.prefixes.append(owner);self.failure.errors.extend(owner.errors);owner.raise_first()
        pin={'path':'result.json','bytes':len(body),'sha256':digest(body)}
        require(self.used_read+len(body)+1<=self.limits['input_bytes'],'receipt readback bound')
        self._read(pin,False,root=self.output_root);self.finished=True
    def check(self,cleanup=False):
        # Root.write_new's Clock interface, always the same selected deadline.
        self.checkpoint();return time.monotonic_ns()
