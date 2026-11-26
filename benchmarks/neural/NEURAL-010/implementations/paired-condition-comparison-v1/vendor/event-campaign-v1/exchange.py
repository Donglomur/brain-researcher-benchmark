"""Bounded file RPC to independently supervised worker/custody services.

No participant code runs in this controller. The independent custody service owns
launch, restricted mounts/state, termination and physical observations. A timeout
leaves an incomplete campaign and retained evidence; it does not certify cleanup.
"""
import time
from pathlib import Path
import common as u


class Exchange:
    def __init__(self, io, root, context_id, role, cap):
        self.io,self.root,self.context,self.role=io,u.c.absolute(str(root)),context_id,role
        self.sequence=0;self.cap=u.c.integer(cap,1,u.CAP)
        u.need(role in ('participant','custody','renderer'),'explicit external service role')
        io.directory(self.root)
        self.sent=io.directory(self.root/'requests')
        self.received=io.directory(self.root/'responses')

    def request(self, value):
        self.io.budget.charge('actions',1)
        self.sequence+=1
        body=u.encoded({'schema':'neural010-service-request-v1','context_id':self.context,
            'role':self.role,'sequence':self.sequence,'body':value})
        u.need(len(body)<=self.cap,'request fits selected complete frame cap')
        request_pin=self.io.create(self.sent/f'{self.sequence:06d}.json',body)
        answer=self.received/f'{self.sequence:06d}.json'
        while not answer.exists():
            self.io.budget.tick();time.sleep(min(.05,max(0,self.io.budget.end-self.io.budget.clock())))
        raw=self.io.incoming(answer,self.role+'_response',self.cap)
        value=u.parse(raw)
        u.exact(value,('schema','context_id','role','sequence','request_sha256','body'))
        u.need(value['schema']=='neural010-service-response-v1'and value['context_id']==self.context
            and value['role']==self.role and type(value['sequence'])is int and value['sequence']==self.sequence
            and value['request_sha256']==request_pin['sha256'],'exact nonreplayed service response')
        return value['body'],raw,request_pin


class Display:
    def __init__(self, exchange):self.exchange=exchange
    def render(self, svg, policy):
        result,_,_=self.exchange.request({'operation':'render_svg_to_pixels','svg':svg.decode('ascii'),
            'render_sha256':u.pin(svg)['sha256'],'policy':policy,'participant_receives_svg_source':False})
        return result
