"""Finite validator for source-owned schema tables. Input cannot provide a schema."""
import math
import re
from .common import Refusal, need, same, bounded_size

_ALLOWED = frozenset(("$schema","$id","$defs","$ref","type","properties","required",
                      "additionalProperties","items","minItems","maxItems","minLength","maxLength",
                      "minimum","maximum","exclusiveMinimum","pattern","enum","const","oneOf","anyOf",
                      "uniqueItems","description","title"))

def check(value, schema, *, root=None, depth=0):
    need(type(schema) is dict and set(schema) <= _ALLOWED and depth <= 64,
         "source-owned finite schema dialect")
    root = schema if root is None else root
    if "$ref" in schema:
        ref = schema["$ref"]
        need(type(ref) is str and ref.startswith("#/$defs/") and ref.count("/") == 2,
             "local fixed schema reference")
        return check(value, root["$defs"][ref.split("/")[-1]], root=root, depth=depth + 1)
    for choice in ("oneOf", "anyOf"):
        if choice in schema:
            matches = 0
            for branch in schema[choice]:
                try:
                    check(value, branch, root=root, depth=depth + 1)
                except (Refusal, KeyError, TypeError, ValueError):
                    continue
                matches += 1
            need(matches == 1 if choice == "oneOf" else matches > 0, "closed union branch")
    if "const" in schema:
        need(same(value, schema["const"]), "exact literal including scalar type")
    if "enum" in schema:
        need(any(same(value, x) for x in schema["enum"]), "closed literal enum")
    kind = schema.get("type")
    if kind == "object":
        need(type(value) is dict, "exact record")
        props = schema["properties"]
        need(set(schema.get("required", ())) <= set(value), "all required fields")
        if schema.get("additionalProperties") is False:
            need(set(value) <= set(props), "no extra field")
        for key, member in value.items():
            need(key in props, "source-declared field")
            check(member, props[key], root=root, depth=depth + 1)
    elif kind == "array":
        need(type(value) is list and schema.get("minItems",0) <= len(value) <= schema.get("maxItems",16384),
             "bounded exact sequence")
        if schema.get("uniqueItems"):
            need(all(not same(x, y) for i, x in enumerate(value) for y in value[:i]), "unique items")
        for member in value:
            check(member, schema["items"], root=root, depth=depth + 1)
    elif kind == "string":
        need(type(value) is str and schema.get("minLength",0) <= len(value) <= schema.get("maxLength",1048576),
             "bounded exact string")
        if "pattern" in schema:
            need(re.fullmatch(schema["pattern"], value) is not None, "source-fixed pattern")
    elif kind in ("integer","number"):
        need(type(value) is int if kind == "integer" else type(value) in (int,float) and math.isfinite(value),
             "exact finite number; bool excluded")
        need(schema.get("minimum",float("-inf")) <= value <= schema.get("maximum",float("inf")),
             "selected numeric bound")
        if "exclusiveMinimum" in schema:
            need(value > schema["exclusiveMinimum"], "selected strict numeric bound")
    elif kind == "boolean":
        need(type(value) is bool, "exact bool")
    elif kind == "null":
        need(value is None, "exact null")
    else:
        need(kind is None, "known source-owned JSON kind")
    return value

class Schemas:
    def __init__(self, tables):
        # The caller authenticates this complete literal source table, never a public request.
        self.tables = tables
    def validate(self, family, name, value, meter):
        meter.charge("work_units", bounded_size(value))
        return check(value, self.tables[family][name])
