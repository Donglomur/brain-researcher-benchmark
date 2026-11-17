"""Sole concrete credential writer. Metadata only until separately admitted read.

Secret bytes are never logged, serialized, hashed or returned. Source construction
and its controls use only expressly invented nonsecret bytes.
"""
import os
import selectors
import stat
from pathlib import PurePosixPath
from nb079_launch_contract import canonical,pin,fields,require
from nb079_authority_io import (integer,decode,open_directory,ident,close_all,cleanup,secondary,fifo_metadata)
from nb079_authority_policy import PolicyCapture
from nb079_authority_validation import require_time

PROTOCOL=('reader_ready_path','reader_ready_admission_path','writer_open_path','writer_open_admission_path',
          'authority_owner_uid','reader_owner_uid','feeder_owner_uid')


class CredentialFeeder:
    def __init__(self,policy_descriptor,request_descriptor,source_fd,*,execution_enabled=False,bootstrap=None):
        require(execution_enabled is True,'feeder disabled before any source FD/file/clock effect')
        integer(source_fd,3)
        self.source_fd=source_fd;self.writer_fd=None;self.selector=None;self.capture=None;self.closed=False
        self.record={'schema':'nb079_credential_feeder_prefix_v1','status':'attempted','source_bytes_read':0,'source_eof':False,
            'fifo_bytes_written':0,'writer_open':None,'writer_admission':None,'source_fd_closed':False,'writer_fd_closed':False,
            'secret_content_retained_or_hashed':False,'complete':False};self.buffer=bytearray()
        try:
            self.capture=PolicyCapture(policy_descriptor,request_descriptor,'feeder',execution_enabled=True,bootstrap=bootstrap)
            self.q,self.r,self.io,self.clock=self.capture.q,self.capture.r,self.capture.io,self.capture.clock
            route=self.r['credential_route'];fields(route,('fifo','feeder_selection','reader_ready_protocol','maximum_credential_bytes'))
            require(type(route['maximum_credential_bytes']) is int and 1<=route['maximum_credential_bytes']<=8192,'selected credential cap <=8192')
            self.maximum=route['maximum_credential_bytes'];self.protocol=route['reader_ready_protocol'];fields(self.protocol,PROTOCOL)
            require(self.protocol==self.q['reader_ready_protocol'] and self.q['reader_ready_request']==self.protocol['reader_ready_path'] and
                self.protocol['writer_open_path']==self.q['roots']['request']['path']+'/'+self.q['writer_ack_name'],'same earlier selected opaque protocol paths')
            require(self.protocol['feeder_owner_uid']==self.capture.actual_identity['uid'],'actual selected sole feeder owner')
            spend=decode(self.io.read(self.q['spend_admission']),self.io.encoding)
            fields(spend,('schema','deployment_pin','original_clock','source_fifo','destination_fifo','maximum_credential_bytes','key_access_authorized','provider_spend_selection_pin'))
            require(spend['schema']=='nb079_earlier_opaque_key_access_v1' and spend['deployment_pin']==self.q['deployment']['pin'] and
                spend['original_clock']==self.r['original_clock'] and spend['source_fifo']==self.q['source_fifo'] and
                spend['destination_fifo']==route['fifo'] and spend['maximum_credential_bytes']==self.maximum and
                spend['key_access_authorized'] is True and spend['provider_spend_selection_pin']==self.r['deployment_and_spend_selection']['spend']['pin'],
                'earlier independent source-FD/key-access/deployment/spend authority before first content read')
            self.record['source_fd_observation']=fifo_metadata(self.source_fd,self.q['source_fifo'],self.clock,os.O_RDONLY)
            require(self.q['source_fifo']['identity']!=route['fifo']['identity'],'opaque source is not destination/self-loop')
            self.clock.tick()
        except BaseException as error:
            self.close(error);error.feeder_prefix=self.prefix();raise

    def poll_file(self,path,owner):
        while True:
            self.clock.tick();self.capture.check_roots()
            try:return self.io.unpinned(path,self.io.limits['file_bytes'],owner=owner)
            except FileNotFoundError:
                import time
                now=self.clock.tick();time.sleep(min(self.q['limits']['poll_ns'],self.r['original_clock']['scientific']-now)/1e9)

    def open_writer(self):
        route=self.r['credential_route'];request,raw=self.poll_file(self.protocol['reader_ready_path'],self.protocol['reader_owner_uid'])
        reader=decode(raw,self.io.encoding)
        fields(reader,('schema','run_nonce','request_pin','central_source_pin','original_clock','fifo_identity','reader_fd_observation','feeder_selection_pin'))
        require(reader['schema']=='n079_opaque_reader_ready_request_v1' and reader['run_nonce']==self.r['run_nonce'] and
            reader['request_pin']==self.capture.request_descriptor['pin'] and reader['original_clock']==self.r['original_clock'] and
            reader['fifo_identity']==route['fifo']['identity'] and reader['feeder_selection_pin']==self.capture.policy_descriptor['pin'],
            'actual published same reader-ready request')
        require(type(reader['reader_fd_observation']['access_mode']) is int and reader['reader_fd_observation']['access_mode']==os.O_RDONLY,'exact source-produced integer read mode')
        require_time(reader['reader_fd_observation']['observed_ns'],self.r['original_clock'],'scientific')
        rd,admission_raw=self.poll_file(self.protocol['reader_ready_admission_path'],self.protocol['authority_owner_uid'])
        admission=decode(admission_raw,self.io.encoding)
        fields(admission,('schema','reader_ready_request_pin','request_pin','original_clock','actual','decision'))
        require(admission['schema']=='nb079_reader_ready_admission_v1' and admission['reader_ready_request_pin']==request['pin'] and
            admission['request_pin']==self.capture.request_descriptor['pin'] and admission['original_clock']==self.r['original_clock'] and
            admission['decision']=='verified_actual_read_only_fifo' and type(admission['actual']['access_mode']) is int and admission['actual']['access_mode']==os.O_RDONLY,'actual independent reader-open admission before writer')
        expected=route['fifo'];parent=open_directory(str(PurePosixPath(expected['path']).parent));first=None
        try:
            require(self.writer_fd is None and self.record['writer_open'] is None,'one sole writer open, no reopen/retry')
            self.clock.tick();self.writer_fd=os.open(PurePosixPath(expected['path']).name,os.O_WRONLY|os.O_NONBLOCK|os.O_NOFOLLOW,dir_fd=parent)
            observation=fifo_metadata(self.writer_fd,expected,self.clock,os.O_WRONLY)
            self.capture.identity.verify(self.capture.actual_identity)
            ack={'schema':'n079_opaque_writer_open_ack_v1','run_nonce':self.r['run_nonce'],'reader_ready_request_pin':request['pin'],
                'source_pin':pin(canonical(self.q['sources'])),'feeder_selection_pin':self.capture.policy_descriptor['pin'],
                'original_clock':self.r['original_clock'],'fifo_identity':expected['identity'],'actual_writer_identity':self.capture.actual_identity,
                'writer_open_observation':observation,'deployment_selection_pin':self.q['deployment']['pin'],
                'spend_selection_pin':self.q['spend_admission']['pin'],'decision':'sole_selected_writer_opened'}
            item=self.io.write(self.q['roots']['request'],self.q['writer_ack_name'],ack)
            require(item['path']==self.protocol['writer_open_path'],'actual selected writer-ack namespace')
            self.record['writer_open']={'descriptor':item,'body':ack}
        except BaseException as error:first=error;raise
        finally:close_all([('writer FIFO parent close',lambda:os.close(parent))],first)
        # Keep this actual writer FD live until independently observed admission.
        item,raw=self.poll_file(self.protocol['writer_open_admission_path'],self.protocol['authority_owner_uid'])
        body=decode(raw,self.io.encoding)
        fields(body,('schema','writer_open_ack','request_pin','original_clock','actual','decision'))
        require(body['schema']=='nb079_writer_open_admission_v1' and body['writer_open_ack']==self.record['writer_open']['descriptor'] and
            body['request_pin']==self.capture.request_descriptor['pin'] and body['original_clock']==self.r['original_clock'] and
            body['decision']=='verified_live_sole_writer' and body['actual']['identity']==self.capture.actual_identity and
            body['actual']['fd']==self.writer_fd and type(body['actual']['access_mode']) is int and body['actual']['access_mode']==os.O_WRONLY and body['actual']['fifo_identity']==expected['identity'],'actual exact protected writer-open admission')
        self.record['writer_admission']={'descriptor':item,'body':body};self.clock.tick()

    def transfer(self):
        require(self.record['writer_admission'] is not None and self.writer_fd is not None,'actual admitted writer before secret read')
        self.capture.counters.charge({'pending_bytes':self.maximum+1,'read_bytes':self.maximum+1},'complete prospective opaque buffer/read plus EOF probe')
        self.selector=selectors.DefaultSelector();self.selector.register(self.source_fd,selectors.EVENT_READ)
        while True:
            now=self.clock.tick();events=self.selector.select((self.r['original_clock']['scientific']-now)/1e9)
            require(events,'original opaque source EOF deadline')
            try:block=os.read(self.source_fd,min(self.io.limits['block_bytes'],self.maximum+1-len(self.buffer)))
            except BlockingIOError:continue
            self.record['source_bytes_read']+=len(block);self.capture.counters.observed('read_bytes',len(block))
            if not block:self.record['source_eof']=True;break
            require(all(32<=byte<=126 for byte in block),'printable ASCII opaque source only')
            self.buffer.extend(block);require(len(self.buffer)<=self.maximum,'whole opaque source capacity; no valid prefix delivered')
        require(0<len(self.buffer)<=self.maximum and self.record['source_eof'],'nonempty complete bounded source before delivery')
        self.selector.unregister(self.source_fd)
        # Detach ownership before close. Even a close error prevents delivery.
        fd,self.source_fd=self.source_fd,None
        os.close(fd);self.record['source_fd_closed']=True
        self.capture.counters.charge({'write_bytes':len(self.buffer)},'entire validated opaque FIFO write before first payload byte')
        self.selector.register(self.writer_fd,selectors.EVENT_WRITE)
        done=0
        while done<len(self.buffer):
            now=self.clock.tick();require(self.selector.select((self.r['original_clock']['scientific']-now)/1e9),'original FIFO write deadline')
            view=memoryview(self.buffer)[done:done+self.io.limits['block_bytes']]
            try:
                try:count=os.write(self.writer_fd,view)
                except BlockingIOError:continue
            finally:view.release()
            require(type(count) is int and 0<count<=min(self.io.limits['block_bytes'],len(self.buffer)-done),'actual positive bounded FIFO write')
            done+=count;self.record['fifo_bytes_written']=done;self.capture.counters.observed('write_bytes',count)
        self.selector.unregister(self.writer_fd)
        fd,self.writer_fd=self.writer_fd,None;os.close(fd);self.record['writer_fd_closed']=True
        self.clock.tick();self.record.update(status='transferred_and_closed',complete=True)

    def run(self):
        first=None;terminal=None
        try:self.open_writer();self.transfer()
        except BaseException as error:first=error
        first=cleanup([('all feeder owned cleanup',lambda:self.close(first))],first)
        if first is None:first=cleanup([('original feeder success cutoff',lambda:self.clock.tick())])
        if first is not None:
            self.record.update(status='failed_or_unknown',complete=False,failure_type=type(first).__name__)
            first.feeder_prefix=self.prefix()
            if self.capture is not None:
                try:self.io.write(self.q['roots']['journal'],'FEEDER_FAILURE.json',first.feeder_prefix,'outer',log=True)
                except BaseException as error:secondary(first,error,'nonsecret feeder failed-prefix publication')
            raise first
        terminal={'schema':'nb079_credential_feeder_terminal_v1','request_pin':self.capture.request_descriptor['pin'],
            'source_pin':pin(canonical(self.q['sources'])),'original_clock':self.r['original_clock'],'result':self.prefix(),
            'meaning':'source owned complete bounded transfer and all own writer copies closed; external original completion remains independent'}
        try:
            result=self.io.write(self.q['roots']['journal'],'FEEDER_TERMINAL.json',terminal,'scientific',log=True)
            self.clock.tick();return {'terminal':result,'record':terminal}
        except BaseException as error:
            self.record.update(status='failed_or_unknown',complete=False,failure_type=type(error).__name__);error.feeder_prefix=self.prefix();raise

    def close(self,primary=None):
        if self.closed:return
        self.closed=True;ops=[]
        if self.selector is not None:
            selector,self.selector=self.selector,None;ops.append(('feeder selector close',selector.close))
        for attr,record in (('source_fd','source_fd_closed'),('writer_fd','writer_fd_closed')):
            fd=getattr(self,attr);setattr(self,attr,None)
            if fd is not None:
                def close(fd=fd,record=record):os.close(fd);self.record[record]=True
                ops.append((attr+' one owned close',close))
        # Best-effort overwrite of our bounded bytearray, not a claim about all
        # Python/OS copies or cryptographic erasure. No contents enter records.
        def clear():
            for i in range(len(self.buffer)):self.buffer[i]=0
            self.buffer.clear()
        ops.append(('opaque owned buffer clear',clear));close_all(ops,primary)
    def prefix(self):return {'nonsecret':dict(self.record),'capture':None if self.capture is None else self.capture.prefix()}
