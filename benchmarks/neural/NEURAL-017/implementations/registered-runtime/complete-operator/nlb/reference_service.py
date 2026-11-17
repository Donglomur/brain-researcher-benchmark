"""Public frozen-program reference client; contains no scientific method bodies.

The supervisor independently binds and executes every request. Python globals
are not a security boundary; changing this client cannot change that authority.
"""
import base64
import sys
from .contracts import need, closed, canonical, parse, digest, integer, Custody, Refusal

PREFIX = b'\x1eNLB017_REFERENCE_V1 '
FRAME_CAP = 128 * 2**10
PREDICTION_CAP = 32 * 2**20
_client = None


def bind(public, inputs, outputs, trace, incoming=None, outgoing=None):
    global _client
    need(_client is None, 'one frozen-program service channel')
    closed(public, {'schema', 'binding', 'bank', 'references', 'metadata', 'max_calls'})
    need(public['schema'] == 'NLB017_frozen_reference_service_v1', 'source-owned service API')
    integer(public['max_calls'], 1)
    _client = Client(public, inputs, outputs, trace, incoming or sys.stdin.buffer, outgoing or sys.stdout.buffer)


def unbind():
    global _client
    _client = None


def inspect_reference(reference):
    """Read the same public state metadata exposed to the investigating actor."""
    need(_client is not None and reference in _client.public['references'], 'condition-specific public reference metadata')
    return parse(canonical(_client.public['metadata'][reference]))


def reference_predict(reference, case_index=None):
    """Return an ordinary local prediction artifact and its original receipt.

    case_index=None returns the whole permitted query pool. Otherwise select
    one of its 574 cases. This does not fit or adapt a new expert model.
    """
    need(_client is not None, 'reference service requires the original F worker')
    return _client.predict(reference, case_index)


class Client:
    def __init__(self, public, inputs, outputs, trace, incoming, outgoing):
        self.public = public
        self.inputs = inputs
        self.outputs = outputs
        self.trace = trace
        self.incoming = incoming
        self.outgoing = outgoing
        self.serial = 0
        self.read_custody = Custody('original_reference_service_reads')
        if hasattr(outputs,'custody'):outputs.custody.resources.append(self.read_custody)

    def line(self):
        budget=self.outputs.budget;c=self.read_custody;c.raise_if_failed()
        event={'phase':'admission','reserved_capacity':0,'known_returned_bytes':0,
               'known_returned_sha256':None,'unused_released':0,'read_attempted':False,
               'unreturned_consumption_unknown':False,'conservative_unknown_charge_attempted':0,'conservative_unknown_charge_completed':False,
               'complete':False}
        c.events.append(event);raw=None;capacity=0
        try:
            budget.admit();capacity=min(FRAME_CAP+1,budget.available('read_bytes'))
            integer(capacity,1,FRAME_CAP+1);budget.reserve('read_bytes',capacity)
            event['reserved_capacity']=capacity;event['phase']='read';event['read_attempted']=True
            raw=self.incoming.readline(capacity)
            # Hold actual extent before framing, parsing, clocks or charge.
            need(type(raw)is bytes,'original service transport returns bytes')
            event['known_returned_bytes']=len(raw);event['known_returned_sha256']=digest(raw)
            need(len(raw)<=capacity,'original bounded read respected reserved capacity')
        except BaseException as error:c.fail(error,'service_read:'+event['phase'])
        finally:
            if type(raw)is bytes:
                try:budget.charge('read_bytes',len(raw))
                except BaseException as error:c.fail(error,'service_read_charge')
                unused=max(0,capacity-len(raw))
                if unused:
                    try:budget.reserve('read_bytes',unused,release=True);event['unused_released']=unused
                    except BaseException as error:
                        c.fail(error,'service_read_unused_reservation');budget.stop('unresolved service read reservation')
            elif event['read_attempted']:
                # Unreturned consumption is unknown, not a zero-cost read.
                event['unreturned_consumption_unknown']=True
                budget.stop('unknown original service read consumption')
                event['conservative_unknown_charge_attempted']=capacity
                try:budget.charge('read_bytes',capacity);event['conservative_unknown_charge_completed']=True
                except BaseException as error:c.fail(error,'service_read_unknown_charge')
        c.raise_if_failed()
        try:
            event['phase']='framing'
            need(raw.endswith(b'\n') and len(raw)<=FRAME_CAP,'complete bounded original service frame')
            event['phase']='parse';value=parse(raw)
            event['phase']='final_clock';budget.guard()
        except BaseException as error:c.fail(error,'service_read:'+event['phase'])
        c.raise_if_failed();event['complete']=True;c.complete=True;return value

    def predict(self, reference, case_index):
        need(reference in self.public['references'], 'condition-specific reference')
        if case_index is not None:
            integer(case_index, 0, 573)
        self.serial += 1
        need(self.serial <= self.public['max_calls'], 'original finite service slots exhausted')
        request = {'schema': 'NLB017_frozen_reference_request_v1', 'binding': self.public['binding'],
                   'bank': self.public['bank'], 'serial': self.serial, 'reference': reference,
                   'case_index': case_index}
        body = canonical(request)
        need(len(PREFIX) + len(body) <= FRAME_CAP, 'bounded service request')
        self.outputs.budget.guard()
        # A newline separates arbitrary preceding stdout from the control line.
        self.outgoing.write(b'\n' + PREFIX + body)
        self.outgoing.flush()
        header = self.line()
        closed(header, {'schema', 'request_sha256', 'binding', 'serial', 'status', 'receipt', 'prediction'})
        need(header['schema'] == 'NLB017_frozen_reference_response_v1' and
             header['request_sha256'] == digest(body) and header['binding'] == self.public['binding'] and
             header['serial'] == self.serial, 'original same-call service response')
        if header['status'] != 'complete':
            need(header['status'] == 'tool_failed' and header['prediction'] is None, 'explicit failed service result')
            self.trace({'event': 'reference_service_failed', 'request': request, 'receipt': header['receipt']})
            return {'status': 'tool_failed', 'receipt': header['receipt']}
        prediction = header['prediction']
        closed(prediction, {'bytes', 'sha256'})
        integer(prediction['bytes'], 0, PREDICTION_CAP)
        chunks = []
        extent = 0
        sequence = 0
        while extent < prediction['bytes']:
            chunk = self.line()
            closed(chunk, {'schema', 'serial', 'sequence', 'data'})
            need(chunk['schema'] == 'NLB017_reference_prediction_chunk_v1' and
                 chunk['serial'] == self.serial and chunk['sequence'] == sequence, 'ordered prediction transport')
            raw = base64.b64decode(chunk['data'], validate=True)
            need(0 < len(raw) <= 64 * 2**10 and extent + len(raw) <= prediction['bytes'], 'bounded prediction chunk')
            chunks.append(raw)
            extent += len(raw)
            sequence += 1
        end = self.line()
        need(end == {'schema': 'NLB017_reference_prediction_end_v1', 'serial': self.serial,
                     'bytes': prediction['bytes'], 'sha256': prediction['sha256'], 'chunks': sequence},
             'complete original prediction transport')
        raw = b''.join(chunks)
        need(digest(raw) == prediction['sha256'], 'original prediction bytes, not a cache substitution')
        local = self.outputs.write('reference-%06d.npz' % self.serial, raw, PREDICTION_CAP)
        self.trace({'event': 'reference_service_complete', 'request': request,
                    'local_prediction': local, 'receipt': header['receipt']})
        return {'status': 'complete', 'prediction': local,
                'path': str(self.outputs.path(local['path'])), 'receipt': header['receipt']}
