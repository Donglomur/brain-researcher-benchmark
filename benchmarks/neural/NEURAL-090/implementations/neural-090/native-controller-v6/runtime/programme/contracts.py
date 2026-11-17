"""Strict ordinary identities and finite work descriptions, never an issuer."""
from dataclasses import dataclass
from fractions import Fraction
from pathlib import PurePosixPath
import re

class Refusal(ValueError): pass

def need(ok, message):
    if not ok: raise Refusal(message)

def fields(value, names):
    need(type(value) is dict and set(value)==set(names), 'exact fields: '+','.join(names))

def identity(value):
    need(type(value) is str and 0<len(value)<=256 and '\x00' not in value, 'nonempty bounded identity')
    return value

@dataclass(frozen=True)
class Pin:
    bytes: int
    sha256: str
    def __post_init__(self):
        need(type(self.bytes) is int and 0<self.bytes<=10**12, 'finite whole-member extent')
        need(type(self.sha256) is str and re.fullmatch('[0-9a-f]{64}',self.sha256), 'SHA256 identity')
    @classmethod
    def parse(cls, value):
        fields(value, ('bytes','sha256')); return cls(**value)
    def json(self): return {'bytes':self.bytes,'sha256':self.sha256}

@dataclass(frozen=True)
class Asset:
    path: str
    pin: Pin
    def __post_init__(self):
        p=PurePosixPath(self.path)
        need(type(self.path) is str and self.path and not p.is_absolute() and
             all(x not in ('','.','..') for x in self.path.split('/')) and '\\' not in self.path,
             'exact local relative asset path')
        need(type(self.pin) is Pin, 'typed asset content pin')
    @classmethod
    def parse(cls,value):
        fields(value,('path','bytes','sha256'))
        return cls(value['path'],Pin(value['bytes'],value['sha256']))

def rational(value):
    # Decimal strings preserve declared source alignment; no float rounding rule
    # or implicit zero-origin inference is smuggled into an offset conversion.
    need(type(value) is str and len(value)<=64, 'explicit finite rational clock text')
    try: result=Fraction(value)
    except (ValueError,ZeroDivisionError): raise Refusal('invalid rational clock') from None
    need(abs(result)<=10**9, 'bounded clock');return result

def exact_unique(rows, label):
    result=tuple(rows);need(result and len(result)==len(set(result)), 'complete unique '+label)
    return result

def no_qualification():
    return {'runnable':False,'research_qualified':False,
            'reason':'Source identity and compiled support do not issue data, clock, native or execution authority.'}
