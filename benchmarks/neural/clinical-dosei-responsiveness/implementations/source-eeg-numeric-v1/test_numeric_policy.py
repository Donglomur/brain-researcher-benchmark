"""Generated scalar controls only. No original files, arrays, drivers or IO."""
import decimal
import math
from pathlib import Path
import struct
import sys
import types
import unittest

SOURCE = Path(__file__).with_name('numeric_policy.py')
p = types.ModuleType('numeric_policy')
p.__file__ = str(SOURCE)
exec(compile(SOURCE.read_bytes(), str(SOURCE), 'exec'), p.__dict__)


def bits(value):
    return struct.unpack('<Q', struct.pack('<d', value))[0]


class NumericPolicyTests(unittest.TestCase):
    def assert_masked(self, raw, expected):
        value, status = p.parse_sample(raw)
        self.assertEqual(status, expected)
        self.assertEqual(bits(value), p.FIXED_NAN_BITS)
        self.assertFalse(p.conversion_valid(status))
        self.assertEqual(p.pack_sample(raw), (bytes.fromhex('000000000000f87f'), expected))

    def test_blank_is_not_whitespace_or_a_sentinel(self):
        self.assert_masked('', p.BLANK)
        for raw in (' ', '\t', '\n', ' 1', '1 ', '1\n', 'None', 'null', 'NA', 'N/A'):
            with self.subTest(raw=raw): self.assert_masked(raw, p.MALFORMED)
        self.assertEqual(p.parse_sample('300'), (300.0, p.OUT_OF_RANGE))

    def test_finite_ascii_grammar_and_no_implicit_normalization(self):
        cases = {'1':1.0, '+1':1.0, '-.5':-.5, '1.':1.0, '.5':.5,
                 '0001.2500':1.25, '1e2':100.0, '1E+02':100.0, '1.2e-1':.12}
        for raw, expected in cases.items():
            with self.subTest(raw=raw): self.assertEqual(p.parse_sample(raw), (expected, 0))
        for raw in ('+', '-', '.', '1e', '1e+', '1e--2', '1_0', '0x1p0', '1,2', '1.2.3', '１', '−1', '\u00a01', '1\x00'):
            with self.subTest(raw=raw): self.assert_masked(raw, p.MALFORMED)

    def test_nonfinite_vocabulary_is_frozen_and_nan_bits_are_fixed(self):
        for word in ('nan', 'NaN', 'NAN', 'nAn', 'inf', 'INF', 'InF', 'infinity', 'Infinity', 'INFINITY'):
            for sign in ('', '+', '-'):
                with self.subTest(raw=sign+word): self.assert_masked(sign+word, p.SOURCE_NONFINITE)
        for raw in ('sNaN', 'NaN42', 'nan(1)', 'Infinity ', 'infinite', '+-Inf'):
            with self.subTest(raw=raw): self.assert_masked(raw, p.MALFORMED)

    def test_signed_exact_zero_survives_every_accepted_zero_form(self):
        for raw in ('0', '+0.0', '.0', '000e10000', '0e-10000'):
            value,status=p.parse_sample(raw)
            self.assertEqual((bits(value),status),(0,0))
        for raw in ('-0', '-0.', '-.000', '-000e10000', '-0e-10000'):
            value,status=p.parse_sample(raw)
            self.assertEqual((bits(value),status),(1<<63,0))

    def test_exact_hardware_endpoints_and_preserved_out_of_range_values(self):
        for raw in ('187.5','+187.5000','1.875e2','-187.5','-1875e-1'):
            value,status=p.parse_sample(raw)
            self.assertEqual(abs(value),187.5)
            self.assertEqual(status,p.EXACT_ENDPOINT)
            self.assertTrue(p.conversion_valid(status))
        self.assertEqual(p.parse_sample('188'),(188.0,p.OUT_OF_RANGE))
        self.assertEqual(p.parse_sample('-300'),(-300.0,p.OUT_OF_RANGE))

    def test_source_boundary_is_not_binary64_boundary(self):
        for sign in ('','-'):
            outside=sign+'187.500000000000000000000000000000000000000000000001'
            inside=sign+'187.499999999999999999999999999999999999999999999999'
            value,status=p.parse_sample(outside)
            self.assertEqual(abs(value),187.5)
            self.assertEqual(status,p.OUT_OF_RANGE)
            value,status=p.parse_sample(inside)
            self.assertEqual(abs(value),187.5)
            self.assertEqual(status,0)

    def test_decimal_context_cannot_round_source_classification(self):
        with decimal.localcontext() as ctx:
            ctx.prec=1;ctx.Emax=2;ctx.Emin=-2
            for signal in (decimal.Inexact,decimal.Rounded,decimal.Underflow,decimal.Overflow):ctx.traps[signal]=True
            for sign in ('','-'):
                self.assertEqual(p.parse_sample(sign+'187.50000000000000000000000000000001')[1],p.OUT_OF_RANGE)
                self.assertEqual(p.parse_sample(sign+'187.49999999999999999999999999999999')[1],0)
                self.assertEqual(p.parse_sample(sign+'187.5')[1],p.EXACT_ENDPOINT)
                self.assertEqual(p.parse_sample(sign+'1e-4000')[1],p.NONZERO_UNDERFLOW)

    def test_finite_nonzero_underflow_is_invalid_signed_zero(self):
        for raw, signbit in (('1e-4000',0),('-1e-4000',1<<63),('2e-324',0),('-2e-324',1<<63)):
            value,status=p.parse_sample(raw)
            self.assertEqual((bits(value),status),(signbit,p.NONZERO_UNDERFLOW))
            self.assertFalse(p.conversion_valid(status))
        for raw in ('5e-324','-5e-324'):
            value,status=p.parse_sample(raw)
            self.assertNotEqual(value,0.0)
            self.assertEqual(status,0)

    def test_finite_overflow_is_distinct_from_source_nonfinite(self):
        for raw in ('1e309','-1e309','9'*4096):self.assert_masked(raw,p.OUT_OF_RANGE|p.FINITE_OVERFLOW)
        value,status=p.parse_sample(repr(sys.float_info.max))
        self.assertEqual(value,sys.float_info.max)
        self.assertEqual(status,p.OUT_OF_RANGE)

    def test_extreme_exponent_is_not_mislabeled_malformed(self):
        huge='9'*4000
        for sign in ('','-'):
            self.assert_masked(sign+'1e'+huge,p.OUT_OF_RANGE|p.FINITE_OVERFLOW)
            value,status=p.parse_sample(sign+'1e-'+huge)
            self.assertEqual((bits(value),status),((1<<63) if sign else 0,p.NONZERO_UNDERFLOW))
            for exponent in (huge,'-'+huge):
                value,status=p.parse_sample(sign+'0e'+exponent)
                self.assertEqual((bits(value),status),((1<<63) if sign else 0,0))
        # Long leading-zero exponents are still small exact exponents.
        self.assertEqual(p.parse_sample('1e'+'0'*4000+'2'),(100.0,0))

    def test_explicit_token_bound_and_nonstring_api_errors(self):
        self.assertEqual(p.parse_sample('0'*4096),(0.0,0))
        raw='0'*4097
        self.assertEqual(p.classify_lexeme(raw),'token_exceeds_4096_ascii_bytes')
        self.assert_masked(raw,p.MALFORMED)
        self.assertEqual(p.classify_lexeme('１２'),'non_ascii_outside_grammar')
        for raw in (None,1,b'1',1.0):
            with self.assertRaises(TypeError):p.parse_sample(raw)

    def test_allowed_combinations_validity_and_little_endian_bytes(self):
        self.assertEqual(p.ALLOWED_STATUSES,frozenset((0,1,2,4,8,16,32,72)))
        self.assertEqual(p.INVALID_MASK,111)
        for status in p.ALLOWED_STATUSES:self.assertEqual(p.conversion_valid(status),status in (0,16))
        for status in (True,False,-1,3,64,128,255,1.0):
            with self.assertRaises(ValueError):p.conversion_valid(status)
        self.assertEqual(p.pack_sample('1'),(bytes.fromhex('000000000000f03f'),0))
        self.assertEqual(p.pack_sample('-0'),(bytes.fromhex('0000000000000080'),0))
        self.assertEqual(p.pack_sample('300'),(struct.pack('<d',300.0),p.OUT_OF_RANGE))


if __name__=='__main__':unittest.main(verbosity=2)
