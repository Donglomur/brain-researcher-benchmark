"""Streaming structural metadata only. No numerical arrays, fits or filesystem I/O.

MAT5 field grammar follows the retained, reviewed Compositional structural reader;
this streaming implementation is NEW, unexecuted and not donor-qualified. Objects,
sparse/function/subsystem and HDF5 metadata are explicit unsupported routes. Every
successful MAT5 result covers the entire logical stream, but reads no scalar data
values; shape is never asserted to establish biological axes or units.
"""
import io
import math
import struct
import zlib


class Held(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise Held(message)


class Cursor:
    def __init__(self, raw, budget, *, limit=None, charge=None):
        self.raw, self.budget, self.limit, self.charge = raw, budget, limit, charge
        self.pos = 0

    def read(self, n):
        need(type(n) is int and n >= 0, 'bounded read required')
        if self.limit is not None:
            n = min(n, self.limit - self.pos)
        self.budget.check()
        if self.charge:
            self.budget.allow(self.charge, n)
        value = self.raw.read(n)
        if self.charge:
            self.budget.add(self.charge, len(value))
        self.pos += len(value)
        return value

    def exact(self, n):
        chunks = []
        left = n
        while left:
            value = self.read(min(left, 65536))
            need(bool(value), 'truncated metadata stream')
            chunks.append(value)
            left -= len(value)
        return b''.join(chunks)

    def skip(self, n):
        while n:
            block = self.exact(min(n, 65536))
            n -= len(block)


class Inflater:
    """Bounded streaming zlib; no complete inflated array buffer."""
    def __init__(self, parent, count, budget):
        self.parent, self.left, self.budget = parent, count, budget
        self.decoder, self.pending = zlib.decompressobj(), b''

    def read(self, n):
        need(0 <= n <= 65536, 'inflater request cap')
        output = bytearray()
        while len(output) < n and not self.decoder.eof:
            self.budget.check()
            if not self.pending and self.left:
                size = min(self.left, 65536)
                self.pending = self.parent.exact(size)
                self.left -= size
            maximum = n - len(output)
            self.budget.allow('mat_expanded', maximum)
            part = self.decoder.decompress(self.pending, maximum)
            self.budget.add('mat_expanded', len(part))
            self.pending = self.decoder.unconsumed_tail
            output.extend(part)
            need(not self.decoder.unused_data, 'trailing zlib bytes')
            need(part or self.pending or self.left or self.decoder.eof,
                 'truncated zlib stream')
        if self.decoder.eof:
            need(not self.left and not self.pending, 'zlib declared extent differs')
        return bytes(output)


class Mat5:
    classes = {1:'cell', 2:'struct', 4:'char', 6:'double', 7:'single', 8:'int8',
               9:'uint8', 10:'int16', 11:'uint16', 12:'int32', 13:'uint32',
               14:'int64', 15:'uint64'}
    widths = {1:1, 2:1, 3:2, 4:2, 5:4, 6:4, 7:4, 9:8, 12:8, 13:8,
              16:1, 17:2, 18:4}

    def __init__(self, cursor, budget):
        self.c, self.budget, self.nodes = cursor, budget, []

    def tag(self, c, *, eof=False):
        raw = c.read(8)
        if not raw and eof:
            return None
        need(len(raw) == 8, 'short MAT tag')
        kind, count = struct.unpack(self.endian+'II', raw)
        if kind >> 16:
            count, kind = kind >> 16, kind & 65535
            need(count <= 4, 'invalid small MAT tag')
            return kind, count, Cursor(io.BytesIO(raw[4:4+count]), self.budget), 0
        need(count <= self.budget.caps['member_bytes'], 'MAT element extent cap')
        return kind, count, c, 0 if kind == 15 else (-count) % 8

    def small(self, c, maximum=4096):
        kind, count, source, pad = self.tag(c)
        need(count <= maximum, 'MAT metadata field cap')
        raw = source.exact(count)
        source.skip(pad)
        return kind, raw

    def matrix(self, c, count, path, depth):
        need(depth <= 32, 'MAT nesting cap')
        start = c.pos
        kind, flags = self.small(c, 8)
        need(kind == 6 and len(flags) == 8, 'MAT flags')
        flag, _ = struct.unpack(self.endian+'II', flags)
        cls = flag & 255
        need(cls in self.classes and not flag & ~0xeff, 'unsupported MAT class or flags')
        kind, dimsraw = self.small(c, 64)
        need(kind == 5 and len(dimsraw) >= 8 and len(dimsraw) % 4 == 0, 'MAT dimensions')
        dims = list(struct.unpack(self.endian+'i'*(len(dimsraw)//4), dimsraw))
        need(all(x >= 0 for x in dims), 'negative MAT shape')
        size = math.prod(dims)
        kind, nameraw = self.small(c, 1024)
        need(kind in (1,16) and b'\x00' not in nameraw, 'MAT name')
        name = nameraw.decode('utf-8' if kind == 16 else 'ascii', 'strict')
        current = path if path else [name]
        need(bool(current[0]), 'empty top variable')
        self.budget.add('nodes', 1)
        node = {'path':current, 'class':self.classes[cls], 'dims':dims,
                'complex':bool(flag & 0x800), 'logical':bool(flag & 0x200)}
        self.nodes.append(node)
        if cls in (1,2):
            need(not flag & 0xa00, 'invalid container flags')
            fields = None
            if cls == 2:
                kind, raw = self.small(c, 4)
                need(kind == 5 and len(raw) == 4, 'MAT field width')
                width, = struct.unpack(self.endian+'i', raw)
                need(1 <= width <= 256, 'MAT field width cap')
                kind, raw = self.small(c, 131072)
                need(kind == 1 and len(raw) % width == 0, 'MAT field names')
                fields = []
                for i in range(0,len(raw),width):
                    slot = raw[i:i+width]
                    at = slot.find(b'\x00')
                    need(at > 0 and not any(slot[at:]), 'MAT field termination')
                    fields.append(slot[:at].decode('ascii','strict'))
                need(len(fields) <= 512 and len(fields) == len(set(fields)), 'MAT fields cap/duplicate')
                node['fields'] = fields
            slots = size * (len(fields) if fields is not None else 1)
            need(slots <= self.budget.caps['nodes']-self.budget.counts['nodes'], 'MAT children cap')
            for index in range(size):
                for field in fields if fields is not None else [None]:
                    kind, length, source, pad = self.tag(c)
                    need(kind == 14 and source is c, 'MAT child matrix')
                    self.matrix(c,length,current+[index]+([field] if field is not None else []),depth+1)
                    c.skip(pad)
        else:
            components = 2 if flag & 0x800 else 1
            need(not (cls == 4 and flag & 0xa00), 'invalid char flags')
            for _ in range(components):
                kind,length,source,pad = self.tag(c)
                need(kind in self.widths, 'unsupported MAT data type')
                if cls != 4:
                    need(kind not in (16,17,18) and length == size*self.widths[kind], 'MAT numerical shape mismatch')
                else:
                    need(kind in (1,2,4,16,17,18), 'MAT char storage')
                source.skip(length)
                source.skip(pad)
        need(c.pos-start == count, 'MAT matrix extent mismatch')

    def run(self):
        header = self.c.exact(128)
        need(header[126:128] in (b'IM',b'MI'), 'not Level5 MAT')
        self.endian = '<' if header[126:128] == b'IM' else '>'
        version, = struct.unpack(self.endian+'H', header[124:126])
        need(version == 0x100 and header[116:124] == bytes(8), 'MAT version/subsystem route held')
        top = set()
        while True:
            tag = self.tag(self.c,eof=True)
            if tag is None:
                break
            kind,count,source,pad = tag
            before = len(self.nodes)
            if kind == 15:
                inner = Cursor(Inflater(source,count,self.budget),self.budget)
                ik, ic, istream, ip = self.tag(inner)
                need(ik == 14 and istream is inner, 'compressed MAT matrix')
                self.matrix(inner,ic,[],0)
                inner.skip(ip)
                need(inner.read(1) == b'', 'multiple compressed MAT variables')
            else:
                need(kind == 14 and source is self.c, 'top MAT matrix')
                self.matrix(source,count,[],0)
                source.skip(pad)
            name = self.nodes[before]['path'][0]
            need(name not in top,'duplicate MAT variable')
            top.add(name)
        return {'variables':self.nodes, 'complete_structure':True,
                'numerical_values_read':False, 'semantic_axes_verified':False,
                'numeric_payload_streamed_and_discarded':True}


def wav_metadata(c):
    raw = c.exact(12)
    need(raw[:4] == b'RIFF' and raw[8:12] == b'WAVE','unsupported WAV container')
    end = struct.unpack('<I',raw[4:8])[0] + 8
    fmt = None
    data_bytes = None
    while c.pos < end:
        name,count = struct.unpack('<4sI',c.exact(8))
        need(count <= end-c.pos,'WAV chunk boundary')
        if name == b'fmt ':
            need(fmt is None and 16 <= count <= 65536,'WAV fmt extent/duplicate')
            body = c.exact(count)
            encoding,channels,rate,byte_rate,align,bits = struct.unpack('<HHIIHH',body[:16])
            need(encoding in (1,3),'unsupported WAV extensible or codec route')
            need(count in (16,18) and (count==16 or body[16:18]==b'\x00\x00'),
                 'unsupported WAV format extension')
            need(channels > 0 and rate > 0 and bits > 0 and bits % 8 == 0,'WAV format')
            need((encoding==1 and bits in (8,16,24,32)) or
                 (encoding==3 and bits in (32,64)),'unsupported WAV sample encoding')
            need(align==channels*(bits//8) and byte_rate==rate*align,
                 'WAV alignment or byte-rate mismatch')
            fmt = dict(channels=channels,sample_rate=rate,bits_per_sample=bits,
                       block_align=align,encoding=encoding)
        elif name == b'data':
            need(data_bytes is None,'multiple WAV data chunks')
            data_bytes=count
            c.skip(count)
        else:
            c.skip(count)
        c.skip(count % 2)
    need(c.pos == end and c.read(1) == b'' and fmt is not None and data_bytes is not None,'WAV completeness')
    need(data_bytes % fmt['block_align'] == 0,'WAV frame alignment')
    fmt['frames'] = data_bytes // fmt['block_align']
    return {'audio':fmt,'complete_structure':True,'waveform_values_read':False}
