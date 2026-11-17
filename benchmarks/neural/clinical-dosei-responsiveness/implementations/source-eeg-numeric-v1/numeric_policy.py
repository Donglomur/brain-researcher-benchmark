"""Pure, bounded DoSEI EEG token policy; no source reads or row-selection logic.

Only a literal empty string is missing. The bounded grammar accepts ASCII
signed decimal coefficients, an optional decimal point, and optional signed
ASCII e/E exponents. No trimming, Unicode digits, underscores or sentinels.
ASCII NaN/Inf/Infinity (any case, optional sign) are recognized nonfinite forms;
sNaN and NaN payloads are not in that explicit vocabulary.

Hardware flags describe the exact SOURCE decimal, before binary64 rounding.
Finite endpoints are diagnostic, not an admission of usable participant data.
The prospective numeric-validity predicate excludes bits0,1,2,3,5,6; a later
packet contract must separately decide endpoint/saturation policy.

All string inputs return a value/status, including malformed, non-ASCII and
oversize strings. Bit1 includes violations of the explicit 4096-byte bounded
ASCII grammar; classify_lexeme exposes that reason instead of calling an
oversize but mathematically numeric token a syntax error. Non-string inputs are
API errors. No invalid token causes a row to be dropped by this core.
"""
import math
import re
import struct
from decimal import Decimal

MAX_TOKEN_BYTES = 4096
FINITE_ASCII_PATTERN = r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z'
_FINITE = re.compile(FINITE_ASCII_PATTERN, re.ASCII)
NONFINITE_BASE_FORMS = ('nan', 'inf', 'infinity')

BLANK = 1 << 0
MALFORMED = 1 << 1
SOURCE_NONFINITE = 1 << 2
OUT_OF_RANGE = 1 << 3
EXACT_ENDPOINT = 1 << 4
NONZERO_UNDERFLOW = 1 << 5
FINITE_OVERFLOW = 1 << 6
INVALID_MASK = BLANK | MALFORMED | SOURCE_NONFINITE | OUT_OF_RANGE | NONZERO_UNDERFLOW | FINITE_OVERFLOW
DEFINED_MASK = (1 << 7) - 1
ALLOWED_STATUSES = frozenset((0, BLANK, MALFORMED, SOURCE_NONFINITE, OUT_OF_RANGE,
                              EXACT_ENDPOINT, NONZERO_UNDERFLOW, OUT_OF_RANGE | FINITE_OVERFLOW))
SOURCE_HARDWARE_LIMIT = Decimal('187.5')
FIXED_NAN_BITS = 0x7FF8000000000000
FIXED_NAN_BYTES = struct.pack('<Q', FIXED_NAN_BITS)
_FIXED_NAN = struct.unpack('<d', FIXED_NAN_BYTES)[0]
# Any nonzero coefficient of <=4096 source bytes, multiplied by 10**e,
# necessarily overflows binary64 when e>10000 and underflows when e<-10000.
# The coefficient can shift its decimal magnitude by fewer than4096 places.
# This exact bound also covers exponents too large for Decimal's C exponent.
_EXPONENT_CLASSIFICATION_BOUND = 10000


def classify_lexeme(raw: str) -> str:
    """Return an explicit lexical category without coercing source text."""
    if type(raw) is not str:
        raise TypeError('numeric source cell must be an exact str')
    if raw == '':
        return 'blank'
    if not raw.isascii():
        return 'non_ascii_outside_grammar'
    if len(raw) > MAX_TOKEN_BYTES:
        return 'token_exceeds_4096_ascii_bytes'
    body = raw[1:] if raw[0] in '+-' else raw
    if body.lower() in NONFINITE_BASE_FORMS:
        return 'recognized_source_nonfinite'
    if _FINITE.fullmatch(raw) is not None:
        return 'finite_ascii_decimal'
    return 'malformed_ascii_decimal'


def _bounded_exponent(text: str) -> int:
    """Exact within +/-10000; otherwise only a sign-qualified sentinel.

    Never turn a thousands-digit exponent into a Python integer. The sentinel
    is used for a proven representability classification, not as a substituted
    source decimal or a fabricated numeric measurement.
    """
    if not text:
        return 0
    negative = text[0] == '-'
    unsigned = text[1:] if text[0] in '+-' else text
    significant = unsigned.lstrip('0')
    if not significant:
        return 0
    if len(significant) > 5 or (len(significant) == 5 and significant > '10000'):
        return -10001 if negative else 10001
    value = int(significant)
    return -value if negative else value


def parse_sample(raw: str) -> tuple[float, int]:
    """Convert one literal source cell to (binary64 approximation, quality).

    Allowed status combinations are frozen in ALLOWED_STATUSES. Missing,
    malformed, source-nonfinite and finite-overflow payloads use the same fixed
    positive quiet-NaN bits. Representable out-of-range values are preserved;
    exact finite nonzero underflow preserves signed binary64 zero and bit5.
    """
    category = classify_lexeme(raw)
    if category == 'blank':
        return _FIXED_NAN, BLANK
    if category == 'recognized_source_nonfinite':
        return _FIXED_NAN, SOURCE_NONFINITE
    if category != 'finite_ascii_decimal':
        return _FIXED_NAN, MALFORMED

    negative = raw[0] == '-'
    lower = raw.lower()
    coefficient, marker, exponent_text = lower.partition('e')
    digits = coefficient.lstrip('+-').replace('.', '')
    # Zero is exactly known regardless of exponent length and must retain sign.
    if not digits.strip('0'):
        return (-0.0 if negative else 0.0), 0
    exponent = _bounded_exponent(exponent_text if marker else '')
    if exponent > _EXPONENT_CLASSIFICATION_BOUND:
        return _FIXED_NAN, OUT_OF_RANGE | FINITE_OVERFLOW
    if exponent < -_EXPONENT_CLASSIFICATION_BOUND:
        return (-0.0 if negative else 0.0), NONZERO_UNDERFLOW

    # Decimal(string) is exact, independent of context precision. copy_abs()
    # does not round; built-in abs(Decimal) would obey the ambient context and
    # could turn a just-outside source number into an apparent endpoint.
    source = Decimal(raw)
    magnitude = source.copy_abs()
    status = (OUT_OF_RANGE if magnitude > SOURCE_HARDWARE_LIMIT else
              EXACT_ENDPOINT if magnitude == SOURCE_HARDWARE_LIMIT else 0)
    try:
        converted = float(source)
    except OverflowError:
        return _FIXED_NAN, OUT_OF_RANGE | FINITE_OVERFLOW
    if not math.isfinite(converted):
        return _FIXED_NAN, OUT_OF_RANGE | FINITE_OVERFLOW
    if converted == 0.0:
        # The exact coefficient was proven nonzero above. This is conversion
        # underflow, not an ordinary zero or an absent observation.
        return converted, status | NONZERO_UNDERFLOW
    return converted, status


def conversion_valid(status: int) -> bool:
    """Check numeric conversion flags, not final participant observation policy.

    Endpoint-only status passes this numerical predicate but remains explicitly
    flagged for the separately specified endpoint/saturation policy.
    """
    if type(status) is not int or status not in ALLOWED_STATUSES:
        raise ValueError('unknown or impossible numeric quality state')
    return status & INVALID_MASK == 0


def pack_sample(raw: str) -> tuple[bytes, int]:
    """Return exactly eight little-endian IEEE-754 bytes and one quality int."""
    value, status = parse_sample(raw)
    if status & (BLANK | MALFORMED | SOURCE_NONFINITE | FINITE_OVERFLOW):
        return FIXED_NAN_BYTES, status
    return struct.pack('<d', value), status
