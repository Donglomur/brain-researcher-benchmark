"""Prospective literal-template engine; pure data transformation, never authority.

The only grammar is one literal {{REQUEST_JSON}} and one literal
{{TRANSCRIPT_JSON}}. Substitution is over the original template spans, so marker
text in admitted products stays literal. The canonical encoder is the existing
source-pinned backend_json implementation, including its trailing LF.

This module does not admit a public request ABI, a PendingAgentStep, a selected
template or a physical bound. The fixed caller must supply those actual owners
and preadmit this compiler itself before reading/encoding their full products.
"""
import hashlib
from .common import need
from .backend_json import parse,canonical,scalar_text

REQUEST=b'{{REQUEST_JSON}}'
TRANSCRIPT=b'{{TRANSCRIPT_JSON}}'
_PLAN=object()

class LiteralTemplatePlanV1:
    def __init__(self,token,template,request,transcript,positions,maximum_prompt):
        need(token is _PLAN,'fixed full literal-template compiler')
        self.template=template;self.request=request;self.transcript=transcript
        self.positions=tuple(positions);self.maximum_prompt=maximum_prompt
        self.input_bytes=len(template)+len(request)+len(transcript)
        self.prompt_bytes=self.input_bytes-len(REQUEST)-len(TRANSCRIPT)
        # Three template spans and two exact complete products. No transcript
        # suffix, truncation, recursive substitution or alternate serialization.
        self.span_count=5
        self.input_sha256=tuple(hashlib.sha256(x).hexdigest()for x in (template,request,transcript))
        self.render_entered=False;self.prompt=None;self.raw_prompt=None;self.prompt_sha256=None
        self.raw_first=None
    def structural_bound(self):
        """Exact source extents; physical coefficients are deliberately absent.

        Byte traversals enumerate this implementation: input digest, canonical
        inverse validation, grammar scan, and final span copy. Encoder/parser
        and Python allocator internals require the separately selected source
        qualification; these extents are their complete input dimensions.
        """
        t,r,h=map(len,(self.template,self.request,self.transcript));o=self.prompt_bytes
        return {'schema':'four_literal_template_structural_bound_v1',
            'template_bytes':t,'request_bytes':r,'transcript_bytes':h,'prompt_bytes':o,
            'filesystem_read_bytes':0,
            'input_decode_extents':[t,r,h],'input_hash_bytes':2*(t+r+h),
            'template_grammar_scan_upper':8*t,
            'canonical_comparison_bytes':r+h,
            'write_bytes':0,'process_starts':0,'span_count':5,
            'substitution_copied_bytes':o,'prompt_encode_bytes':o,'prompt_hash_bytes':o,
            'explicit_retained_byte_payload_upper':4*(t+r+h)+4*o+512,
            'canonical_input_extents':[r,h],
            'parser_encoder_scalar_text_and_allocator_source_bounds_required':True,
            'physical_and_encoder_bounds_required':True}
    def render_once(self):
        need(not self.render_entered,'one original literal rendering attempt, including failure')
        self.render_entered=True
        try:
            need(tuple(hashlib.sha256(x).hexdigest()for x in (self.template,self.request,self.transcript))==self.input_sha256,
                 'exact retained original complete inputs')
            parts=[];at=0
            for position,marker,product in self.positions:
                parts.append(self.template[at:position]);parts.append(product);at=position+len(marker)
            parts.append(self.template[at:]);raw=b''.join(parts);self.raw_prompt=raw
            need(len(parts)==5 and len(raw)==self.prompt_bytes<=self.maximum_prompt,
                 'exact five original spans and complete preadmitted output extent')
            prompt=raw.decode('utf8','strict');scalar_text(prompt,maximum=1048576)
            need(prompt.encode('utf8')==raw,'lossless original prompt UTF-8')
            self.prompt=prompt;self.prompt_sha256=hashlib.sha256(raw).hexdigest();return prompt
        except BaseException as error:self.raw_first=error;raise

def compile_literal_template_v1(template,request_raw,transcript_raw,maximum_prompt):
    need(type(maximum_prompt)is int and 0<maximum_prompt<=1048576,'existing bounded prompt domain')
    for raw in (template,request_raw,transcript_raw):
        need(type(raw)is bytes and 0<len(raw)<=maximum_prompt,'complete bounded original input product')
        scalar_text(raw.decode('utf8','strict'),maximum=1048576)
    # The fixed caller supplies the already admitted closed ABI products. These
    # checks establish only exact original canonical representation, not ABI or
    # private source authority; there is no generic validator callback.
    for raw in (request_raw,transcript_raw):
        value=parse(raw,len(raw),maximum_depth=64,maximum_members=len(raw),maximum_string_bytes=len(raw))
        need(canonical(value,len(raw))==raw,'same existing lossless full canonical product bytes')
    need(template.count(REQUEST)==1 and template.count(TRANSCRIPT)==1,'one of each exact literal marker')
    rest=template.replace(REQUEST,b'').replace(TRANSCRIPT,b'')
    need(b'{{'not in rest and b'}}'not in rest,'no unknown, malformed or additional marker grammar')
    positions=sorted([(template.index(REQUEST),REQUEST,request_raw),(template.index(TRANSCRIPT),TRANSCRIPT,transcript_raw)])
    extent=len(template)-len(REQUEST)-len(TRANSCRIPT)+len(request_raw)+len(transcript_raw)
    need(0<extent<=maximum_prompt,'entire original output fits before rendering')
    return LiteralTemplatePlanV1(_PLAN,template,request_raw,transcript_raw,positions,maximum_prompt)
