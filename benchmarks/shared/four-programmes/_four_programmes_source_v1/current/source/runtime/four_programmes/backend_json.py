"""Fixed bounded JSON for the new issuer/backend records only.

The original common.encode and scientific bytes remain unchanged. Callers must
preadmit raw text, parsed nodes, retained copies and canonical expansion under
their original owner before invoking these pure metadata functions.
"""
import json
import math
import re
from .common import need, integer

_NUMBER = re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?')
_MAX_EXACT = 9007199254740991


def scalar_text(value, *, maximum=1048576):
    need(type(value) is str and len(value) <= maximum, 'bounded builtin scalar text')
    need(all(c != '\0' and not 0xD800 <= ord(c) <= 0xDFFF for c in value),
         'no NUL or lone surrogate')
    return value


def _tree(value, depth, maximum_depth, nodes, maximum_nodes):
    need(depth <= maximum_depth, 'canonical metadata depth')
    nodes[0] += 1
    need(nodes[0] <= maximum_nodes, 'canonical nodes fit selected finite byte extent')
    typ = type(value)
    if value is None or typ is bool:
        return
    if typ is int:
        need(-_MAX_EXACT <= value <= _MAX_EXACT, 'canonical exact integer')
        return
    if typ is float:
        need(math.isfinite(value), 'canonical finite scalar')
        return
    if typ is str:
        scalar_text(value, maximum=maximum_nodes)
        return
    if typ is list:
        need(len(value) <= maximum_nodes, 'canonical bounded sequence')
        for child in value:
            _tree(child, depth + 1, maximum_depth, nodes, maximum_nodes)
        return
    need(typ is dict and len(value) <= maximum_nodes, 'canonical builtin closed metadata')
    for key, child in value.items():
        scalar_text(key, maximum=4096)
        _tree(child, depth + 1, maximum_depth, nodes, maximum_nodes)


def canonical(value, cap, *, maximum_depth=64):
    """Exact V3 UTF-8 record bytes, including the one trailing LF."""
    integer(cap, 1)
    integer(maximum_depth, 1)
    need(maximum_depth <= 64, 'source-selected maximum metadata depth')
    _tree(value, 0, maximum_depth, [0], cap)
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False) + '\n').encode('utf8')
    need(len(raw) <= cap, 'complete canonical output within original cap')
    return raw


class _Parser:
    """Source-fixed decoder; no caller hooks, coercions or permissive extensions."""
    def __init__(self, raw, *, cap, maximum_depth, maximum_members, maximum_string_bytes):
        integer(cap, 1)
        need(type(raw) is bytes and len(raw) <= cap and not raw.startswith(b'\xef\xbb\xbf'),
             'bounded exact UTF-8 JSON without BOM')
        need(0 < maximum_depth <= 64 and type(maximum_depth) is int,
             'source-selected depth')
        need(type(maximum_members) is int and 0 < maximum_members <= _MAX_EXACT,
             'source-selected member count')
        need(type(maximum_string_bytes) is int and 0 < maximum_string_bytes <= _MAX_EXACT,
             'source-selected string byte bound')
        self.text = raw.decode('utf8', 'strict')
        self.at = 0
        self.depth_limit = maximum_depth
        self.member_limit = min(maximum_members, cap)
        self.string_limit = maximum_string_bytes
        self.members = 0

    def space(self):
        while self.at < len(self.text) and self.text[self.at] in ' \t\r\n':
            self.at += 1

    def string(self):
        need(self.at < len(self.text) and self.text[self.at] == '"', 'JSON string token')
        value, end = json.decoder.scanstring(self.text, self.at + 1, True)
        scalar_text(value, maximum=self.string_limit)
        need(len(value.encode('utf8')) <= self.string_limit, 'bounded decoded string bytes')
        self.at = end
        return value

    def member(self):
        # Admission precedes constructing/inserting the next member.
        need(self.members < self.member_limit, 'bounded complete JSON member count')
        self.members += 1

    def value(self, depth=0):
        need(depth <= self.depth_limit, 'bounded JSON nesting')
        self.space()
        need(self.at < len(self.text), 'complete JSON value')
        c = self.text[self.at]
        if c == '"':
            return self.string()
        if c == '{':
            self.at += 1
            result = {}
            self.space()
            if self.at < len(self.text) and self.text[self.at] == '}':
                self.at += 1
                return result
            while True:
                self.member()
                key = self.string()
                need(key not in result, 'duplicate JSON member')
                self.space()
                need(self.at < len(self.text) and self.text[self.at] == ':', 'JSON member colon')
                self.at += 1
                result[key] = self.value(depth + 1)
                self.space()
                need(self.at < len(self.text), 'complete JSON object')
                delimiter = self.text[self.at]
                self.at += 1
                if delimiter == '}':
                    return result
                need(delimiter == ',', 'JSON object delimiter')
                self.space()
        if c == '[':
            self.at += 1
            result = []
            self.space()
            if self.at < len(self.text) and self.text[self.at] == ']':
                self.at += 1
                return result
            while True:
                self.member()
                result.append(self.value(depth + 1))
                self.space()
                need(self.at < len(self.text), 'complete JSON array')
                delimiter = self.text[self.at]
                self.at += 1
                if delimiter == ']':
                    return result
                need(delimiter == ',', 'JSON array delimiter')
        for literal, value in (('true', True), ('false', False), ('null', None)):
            if self.text.startswith(literal, self.at):
                self.at += len(literal)
                return value
        number = _NUMBER.match(self.text, self.at)
        need(number is not None, 'strict JSON token')
        token = number.group()
        need(len(token) <= 64, 'bounded number lexeme before conversion')
        self.at = number.end()
        if '.' in token or 'e' in token or 'E' in token:
            value = float(token)
            need(math.isfinite(value), 'finite JSON number, no exponent overflow')
            return value
        value = int(token)
        need(-_MAX_EXACT <= value <= _MAX_EXACT, 'bounded exact JSON integer')
        return value


def parse(raw, cap, *, maximum_depth=8, maximum_members=128,
          maximum_string_bytes=1048576):
    parser = _Parser(raw, cap=cap, maximum_depth=maximum_depth,
                     maximum_members=maximum_members, maximum_string_bytes=maximum_string_bytes)
    value = parser.value()
    parser.space()
    need(parser.at == len(parser.text), 'no trailing JSON tokens')
    return value

