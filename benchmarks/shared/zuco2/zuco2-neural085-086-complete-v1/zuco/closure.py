"""Bounded nonrecursive controller tail admission.
A prepaid controller tail is charged before serializing the final record. Its
actual tail is checked before return. Independent parent completion remains
mandatory; the child cannot certify its own post-return completion.
"""
import time
from .io import *
def reserve_tail(ledger,seconds):
    need(finite(seconds) and seconds>0,'controller_tail_reservation');ledger.charge_controller(seconds);return time.process_time(),seconds
def end_tail(ledger,token):
    actual=time.process_time()-token[0]
    if actual>token[1]:ledger.unknown=True;raise Refusal('controller_finalization_CPU_overshoot',{'actual':actual,'reserved':token[1]})
    ledger.final()
def final_file(path,body,ledger,tail_seconds):
    token=reserve_tail(ledger,tail_seconds)
    # The final resource snapshot includes its own reserved byte capacity, without
    # recursively enlarging an embedded accounting object.
    reserve=len(encode(body))+16384;ledger.reserve_bytes(reserve,'bounded final report including resource snapshot');body['resources']=ledger.snapshot();raw=encode(body);need(len(raw)<=reserve,'final_report_reservation_extent');pin=write(path,raw);end_tail(ledger,token);return pin
