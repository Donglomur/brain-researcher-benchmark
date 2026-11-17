"""Parse a narrow pickle grammar into inert records, never Python objects.

No pickle.load, imports from GLOBAL names, constructors, REDUCE calls, or BUILD
callbacks are performed. This is a bounded source-format reader, not a general
unpickler. Unknown opcodes fail closed. Source-specific interpretation is separate.
"""
from dataclasses import dataclass
import pickletools


class FormatError(ValueError):
    pass


@dataclass(eq=False)
class Symbol:
    name: str


@dataclass(eq=False)
class Record:
    constructor: object
    args: tuple
    state: object = None


def require(condition, message):
    if not condition:
        raise FormatError(message)


def parse(raw, *, max_bytes=2_000_000, max_ops=300_000, max_items=100_000):
    """Return only primitives, Symbol and Record; executable opcodes stay inert."""
    require(type(raw) is bytes and len(raw) <= max_bytes, "pickle byte bound")
    stack, memo, mark = [], {}, object()
    def pop_mark():
        try:
            index = next(i for i in range(len(stack)-1, -1, -1) if stack[i] is mark)
        except StopIteration as exc:
            raise FormatError("missing pickle MARK") from exc
        result = stack[index+1:]
        del stack[index:]
        return result
    def key_ok(key):
        require(type(key) in (str, int, bool, type(None)), "unsupported dictionary key")
    def set_pairs(target, values):
        require(type(target) is dict and len(values) % 2 == 0, "invalid dictionary items")
        require(len(target) + len(values)//2 <= max_items, "dictionary size bound")
        for key, value in zip(values[::2], values[1::2]):
            key_ok(key)
            require(key not in target, "duplicate dictionary key")
            target[key] = value
    try:
        for count, (op, arg, pos) in enumerate(pickletools.genops(raw), 1):
            require(count <= max_ops and len(stack) <= max_items and len(memo) <= max_items, "pickle complexity bound")
            name = op.name
            if name in ("PROTO", "FRAME"):
                if name == "PROTO":
                    require(2 <= arg <= 5, "unsupported pickle protocol")
            elif name == "MARK": stack.append(mark)
            elif name in ("NONE", "NEWTRUE", "NEWFALSE"):
                stack.append({"NONE": None, "NEWTRUE": True, "NEWFALSE": False}[name])
            elif name in ("BININT", "BININT1", "BININT2", "LONG1", "LONG4", "BINFLOAT", "BINUNICODE", "SHORT_BINUNICODE", "BINUNICODE8", "BINBYTES", "SHORT_BINBYTES", "BINBYTES8"):
                stack.append(arg)
            elif name == "EMPTY_LIST": stack.append([])
            elif name == "EMPTY_DICT": stack.append({})
            elif name == "EMPTY_TUPLE": stack.append(())
            elif name == "EMPTY_SET": stack.append(set())
            elif name in ("LIST", "TUPLE", "FROZENSET"):
                values = pop_mark()
                if name == "LIST": stack.append(values)
                elif name == "TUPLE": stack.append(tuple(values))
                else:
                    require(all(type(x) in (str, int) for x in values), "set item type")
                    stack.append(frozenset(values))
            elif name == "DICT":
                values = pop_mark(); target = {}; set_pairs(target, values); stack.append(target)
            elif name in ("TUPLE1", "TUPLE2", "TUPLE3"):
                n = int(name[-1]); require(len(stack) >= n, "tuple stack underflow")
                values = tuple(stack[-n:]); del stack[-n:]; stack.append(values)
            elif name in ("APPEND", "APPENDS", "ADDITEMS"):
                values = [stack.pop()] if name == "APPEND" else pop_mark()
                target = stack[-1]
                require(type(target) is (set if name == "ADDITEMS" else list), "append target type")
                require(len(target) + len(values) <= max_items, "collection size bound")
                if name == "ADDITEMS":
                    require(all(type(x) in (str, int) for x in values), "set item type")
                    target.update(values)
                else: target.extend(values)
            elif name in ("SETITEM", "SETITEMS"):
                values = pop_mark() if name == "SETITEMS" else [stack[-2], stack[-1]]
                if name == "SETITEM": del stack[-2:]
                set_pairs(stack[-1], values)
            elif name in ("BINPUT", "LONG_BINPUT", "MEMOIZE"):
                index = len(memo) if name == "MEMOIZE" else arg
                require(index not in memo and 0 <= index < max_items, "invalid/duplicate memo index")
                memo[index] = stack[-1]
            elif name in ("BINGET", "LONG_BINGET"):
                require(arg in memo, "unknown memo index"); stack.append(memo[arg])
            elif name == "GLOBAL": stack.append(Symbol(arg.replace(" ", ".", 1)))
            elif name == "STACK_GLOBAL":
                attr, module = stack.pop(), stack.pop()
                require(type(module) is str and type(attr) is str, "invalid global symbol")
                stack.append(Symbol(module + "." + attr))
            elif name in ("REDUCE", "NEWOBJ"):
                args, constructor = stack.pop(), stack.pop()
                require(type(args) is tuple and isinstance(constructor, Symbol), "invalid inert constructor")
                stack.append(Record(constructor, args))
            elif name == "BUILD":
                state = stack.pop()
                require(isinstance(stack[-1], Record) and stack[-1].state is None, "invalid or repeated inert BUILD")
                stack[-1].state = state
            elif name == "STOP":
                require(len(stack) == 1 and stack[0] is not mark, "invalid final stack")
                require(pos == len(raw)-1, "trailing bytes after pickle STOP")
                return stack[0]
            else:
                raise FormatError("unsupported pickle opcode: " + name)
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, FormatError): raise
        raise FormatError("malformed pickle structure") from exc
    raise FormatError("missing pickle STOP")
