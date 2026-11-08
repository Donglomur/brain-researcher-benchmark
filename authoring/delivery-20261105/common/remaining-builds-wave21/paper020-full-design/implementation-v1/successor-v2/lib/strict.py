"""Small plain-JSON and metadata primitives; no scientific imports or input readers."""
import hashlib
import json
import math
import re


class ContractError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def need(condition, code, message):
    if not condition:
        raise ContractError(code, message)


def plain(value):
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        need(math.isfinite(value), "json", "Nonfinite JSON number")
        return
    if type(value) is list:
        for child in value:
            plain(child)
        return
    if type(value) is dict:
        need(all(type(k) is str for k in value), "json", "Plain string JSON keys required")
        for child in value.values():
            plain(child)
        return
    raise ContractError("json", "Only plain JSON values are admitted")


def encoded(value):
    plain(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def decode(raw, cap=1048576):
    need(type(raw) is bytes and len(raw) <= cap, "json", "Bounded UTF-8 JSON bytes required")
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "json", "Duplicate JSON key")
            result[key] = value
        return result
    def nonfinite(_):
        raise ContractError("json", "Nonfinite JSON constant")
    try:
        value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=pairs,
                           parse_constant=nonfinite)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ContractError("json", "Malformed UTF-8 JSON") from error
    plain(value)
    return value


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def natural(value, field, zero=False):
    need(type(value) is int and value >= (0 if zero else 1), "schema", "Invalid " + field)
    return value


def text(value, field, limit=512):
    need(type(value) is str and 0 < len(value.encode("utf-8")) <= limit,
         "schema", "Invalid " + field)
    return value


def sha(value):
    need(type(value) is str and re.fullmatch("[0-9a-f]{64}", value) is not None,
         "schema", "Exact SHA-256 required")
    return value


def exact_keys(value, keys, name):
    need(type(value) is dict and set(value) == set(keys), "schema", "Exact " + name + " fields required")
    return value


def length_delimited(*parts):
    """UTF-8 strings, each preceded by an unsigned big-endian eight-byte length."""
    result = bytearray()
    for part in parts:
        raw = text(part, "hash component", 16384).encode("utf-8")
        result.extend(len(raw).to_bytes(8, "big"))
        result.extend(raw)
    return bytes(result)


def schedule_hash(*parts):
    return hashlib.sha256(length_delimited(*parts)).digest()
