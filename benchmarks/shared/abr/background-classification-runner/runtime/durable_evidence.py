"""Pre-reserved, private, fixed-slot lifecycle evidence; no candidate access.

Each consumed slot is written once. A torn slot cannot hide a later slot:
readers scan all 64 fixed boundaries and validate index, length and SHA256.
The original owner alarm remains active throughout writes, fsync and close.
"""
import hashlib
import os
import stat
import struct
import time
from common import encode, need, pin, plain, write

SLOTS=64
SLOT_BYTES=32768
CAPACITY=SLOTS*SLOT_BYTES
HEADER=struct.Struct('<8sII32s')
MAGIC=b'TMSJNL02'

class Evidence:
    def __init__(self,path,budget):
        self.path=plain(path)
        self.budget=budget
        self.fd=None
        self.used=0
        self.errors=[]
        self.closed=False
        self.body=bytearray(CAPACITY)
        # Initialization and at most one entire replacement per fixed slot.
        # All later writes are charged prospectively, including failed writes.
        write(self.path,bytes(self.body),budget,mode=0o600)
        budget.reserve_write(CAPACITY)
        try:
            self.fd=os.open(self.path,os.O_WRONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            st=os.fstat(self.fd)
            need(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_size==CAPACITY,
                 'owned_journal_extent')
            os.fchmod(self.fd,0o400)
        except BaseException:
            if self.fd is not None:
                try:os.close(self.fd)
                except BaseException as error:self.error('initial_close',error)
                self.fd=None
            raise

    def error(self,phase,error):
        # Finite call/slot count bounds the list; messages never leave private custody.
        self.errors.append({'phase':phase,'class':type(error).__name__})

    def emit(self,phase,value):
        slot=self.used
        self.used+=1                 # a failed/partial slot is never reused
        try:
            need(self.fd is not None and slot<SLOTS,'journal_slot_available')
            payload=encode({'schema':'tms_owner_journal_event_v2','phase':phase,
                            'slot':slot,'value':value,'preceding_persistence_errors':self.errors})
            need(len(payload)<=SLOT_BYTES-HEADER.size,'journal_event_extent')
            frame=HEADER.pack(MAGIC,slot,len(payload),hashlib.sha256(payload).digest())+payload
            at=0
            while at<len(frame):
                need(time.monotonic()<self.budget.deadline,'original_journal_deadline')
                n=os.pwrite(self.fd,frame[at:],slot*SLOT_BYTES+at)
                need(n>0,'journal_complete_write')
                self.body[slot*SLOT_BYTES+at:slot*SLOT_BYTES+at+n]=frame[at:at+n]
                at+=n
                self.budget.successful+=n
            need(time.monotonic()<self.budget.deadline,'original_journal_fsync_deadline')
            os.fsync(self.fd)
            need(time.monotonic()<self.budget.deadline,'original_journal_event_closed')
            return True
        except BaseException as error:
            self.error(phase,error)
            return False

    def close(self):
        if self.fd is None:
            return
        # A failure here cannot skip the independently owned descriptor close.
        try:
            need(time.monotonic()<self.budget.deadline,'original_journal_close_deadline')
            os.fsync(self.fd)
        except BaseException as error:
            self.error('final_fsync',error)
        self.emit('journal_closing',{'used_slots_before_close':self.used,
                                    'persistence_errors':list(self.errors)})
        try:
            os.close(self.fd)
            self.closed=True
        except BaseException as error:
            self.error('final_close',error)
        finally:
            self.fd=None

    def receipt(self):
        return {'path':str(self.path),**pin(bytes(self.body)),
                'schema':'tms_fixed_slot_private_journal_v2','slots':SLOTS,
                'slot_bytes':SLOT_BYTES,'used_slots':self.used,
                'reserved_logical_write_bytes':2*CAPACITY,
                'closed':self.closed,'persistence_errors':list(self.errors),
                'hash_basis':'initial zeros plus acknowledged pwrite prefixes; final owner census independently hashes the file'}
