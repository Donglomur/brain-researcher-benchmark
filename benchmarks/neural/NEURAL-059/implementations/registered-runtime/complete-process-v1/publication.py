"""Whole JSON originals streamed into bounded ordered text parts and an exact manifest."""
import hashlib
import json
from .core import need, encode


def document(journal,name,value,max_bytes):
    digest=hashlib.sha256(); parts=[]; buffer=bytearray(); total=0
    def flush():
        if not buffer: return
        body=bytes(buffer); buffer.clear()
        rec=journal.write(name+'-PART-%06d.txt'%len(parts),body)
        parts.append(rec)
    for text in json.JSONEncoder(sort_keys=True,separators=(',',':'),ensure_ascii=True,
                                 allow_nan=False).iterencode(value):
        raw=text.encode(); total+=len(raw)
        need(total<=max_bytes,'complete original document within prospective publication cap')
        digest.update(raw)
        offset=0
        while offset<len(raw):
            n=min(32768-len(buffer),len(raw)-offset)
            buffer.extend(raw[offset:offset+n]); offset+=n
            if len(buffer)==32768: flush()
    total+=1; need(total<=max_bytes,'terminal newline inside complete document cap')
    digest.update(b'\n'); buffer.extend(b'\n'); flush()
    manifest={'schema':'n059_complete_json_original_v1','bytes':total,'sha256':digest.hexdigest(),
              'ordered_parts':parts,'concatenate_exact_part_bytes':True}
    body=encode(manifest); need(len(body)<=1048576,'bounded exact complete-document manifest')
    return journal.write(name+'-MANIFEST.json',body)
