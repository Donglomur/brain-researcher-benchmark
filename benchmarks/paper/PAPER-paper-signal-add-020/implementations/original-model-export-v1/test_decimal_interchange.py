"""New generated controls for the versioned numeric serialization correction only."""
import copy,decimal,importlib.util,math,sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
bridge=module('corrected_erp_bridge',HERE/'finalize.py')
fixtures=module('adjacent_generated_fixture_factory',HERE/'test_interchange.py')
CTX=decimal.Context(prec=15,rounding=decimal.ROUND_HALF_EVEN)
def encoder_reference(value):
    # Independent decimal arithmetic oracle for C %.15g under nearest/even;
    # no production formatter is called to generate these expected values.
    return float(CTX.create_decimal_from_float(float(value)))
def panel(rounded):
    export,prepared,contract=fixtures.fixture()
    export['export_runtime']['packages']['jsonlite']='1.8.4'
    for model_index,(name,model) in enumerate(export['models'].items()):
        fields=[bridge.OUTCOMES[name]]+contract['models'][name]['terms'][1:]
        for column,field in enumerate(fields):
            for row_index,row in enumerate(prepared[name]):
                value=(-1 if (row_index+column)%2 else 1)*(1.2345678901234567+model_index*2+column*.125+row_index*.03125)
                row[field]=repr(value)
                model['frame'][field][row_index]=encoder_reference(value) if rounded else value
    return export,prepared,contract
class DecimalInterchangeTests(unittest.TestCase):
    def test_documented_precision_and_ties_have_independent_expected_values(self):
        pairs=[(1.2345678901234567,1.23456789012346),(-9.876543210987654,-9.87654321098765),
               (9.999999999999996,10.),(123456789012344.5,123456789012344.),
               (123456789012345.5,123456789012346.),(-123456789012345.5,-123456789012346.),
               (1.2345678901234567e-100,1.23456789012346e-100),(1.2345678901234567e100,1.23456789012346e100)]
        for source,encoded in pairs:
            with self.subTest(case=pairs.index((source,encoded))):
                self.assertEqual(encoder_reference(source),encoded)
                self.assertEqual(bridge.frame_number_match(encoded,repr(source),'1.8.4'),'jsonlite_1.8.4_15g')
        for source in (0.,-0.,math.ulp(0.),-math.ulp(0.),sys.float_info.min,sys.float_info.max):
            self.assertEqual(bridge.frame_number_match(source,repr(source),'unknown'),'exact')
        self.assertIsNone(bridge.frame_number_match(math.nextafter(sys.float_info.max,0),repr(sys.float_info.max),'1.8.4'))

    def test_new_rounded_panel_passes_without_changing_coefficients_or_contrasts(self):
        export,prepared,contract=panel(True)
        summary,provenance=bridge.validate_export(export,prepared,contract)
        exact,exact_prepared,exact_contract=panel(False)
        baseline=bridge.validate_export(exact,exact_prepared,exact_contract)[0]
        self.assertEqual(summary['models'],baseline['models'])
        self.assertEqual(summary['P3b_report'],baseline['P3b_report'])
        self.assertEqual(set(summary),set(baseline))
        for name in provenance:
            binding=provenance[name]['numeric_frame_binding']
            self.assertGreater(binding['jsonlite_1_8_4_15g_values'],0)
            self.assertEqual(binding['checked_values'],binding['exact_numeric_values']+binding['jsonlite_1_8_4_15g_values'])
            self.assertFalse(binding['within_encoding_bin_identity_established'])
        self.assertIn('finer within-bin identity is not established',summary['method'])

    def test_unknown_versions_retain_exact_only_behavior(self):
        for version in ('1.8.5','fixture',1.84,None):
            export,prepared,contract=panel(True)
            export['export_runtime']['packages']['jsonlite']=version
            with self.assertRaises(bridge.ExportError):bridge.validate_export(export,prepared,contract)
        export,prepared,contract=panel(False)
        export['export_runtime']['packages']['jsonlite']='unknown'
        bridge.validate_export(export,prepared,contract)
        self.assertEqual(bridge.frame_number_match(1.25,'1.25','unknown'),'exact')

    def test_noncanonical_adjacent_or_meaningful_changes_are_rejected(self):
        source=1.2345678901234567;encoded=1.23456789012346
        for changed in (math.nextafter(encoded,math.inf),math.nextafter(encoded,-math.inf),encoded+.001):
            self.assertNotEqual(changed,source)
            self.assertIsNone(bridge.frame_number_match(changed,repr(source),'1.8.4'))
            export,prepared,contract=panel(True)
            prepared['FRN'][0]['FRN_N2_offer_s']=repr(source)
            export['models']['FRN']['frame']['FRN_N2_offer_s'][0]=changed
            with self.assertRaisesRegex(bridge.ExportError,'Fitted-frame value/order differs'):
                bridge.validate_export(export,prepared,contract)

    def test_wrong_rows_columns_and_identity_remain_rejected(self):
        mutations=[lambda m:m['frame']['FRN_N2_offer_s'].reverse(),
                   lambda m:m['frame'].__setitem__('FRN_N2_offer_s',m['frame']['abs_rpe_s'][:]),
                   lambda m:m['operator_bound_source_rows'].__setitem__(0,3),
                   lambda m:m['frame']['sub'].reverse(),
                   lambda m:m['frame']['abs_rpe_s'].pop()]
        for mutate in mutations:
            export,prepared,contract=panel(True);mutate(export['models']['FRN'])
            with self.assertRaises(bridge.ExportError):bridge.validate_export(export,prepared,contract)

    def test_nonfinite_and_boolean_numbers_remain_rejected(self):
        for actual,source in ((True,'1'),(float('nan'),'1'),(float('inf'),'1'),(1.,'nan'),(1.,'inf'),(1.,True)):
            with self.assertRaises((bridge.ExportError,ValueError)):
                bridge.frame_number_match(actual,source,'1.8.4')
        for value in (True,float('nan'),float('inf')):
            export,prepared,contract=panel(True);export['models']['FRN']['frame']['abs_rpe_s'][0]=value
            with self.assertRaises(bridge.ExportError):bridge.validate_export(export,prepared,contract)

    def test_other_scientific_gates_remain_active_with_serialized_frames(self):
        mutations=[lambda e:e['models']['FRN'].__setitem__('REML',False),
                   lambda e:e['models']['FRN'].__setitem__('weights',[1,1,1,1]),
                   lambda e:e['models']['FRN'].__setitem__('random_design_verified',False),
                   lambda e:e['models']['FRN']['covariance'][0].__setitem__(0,-1.),
                   lambda e:e.__setitem__('schema','unexpected-schema')]
        for mutate in mutations:
            export,prepared,contract=panel(True);mutate(export)
            with self.assertRaises(bridge.ExportError):bridge.validate_export(export,prepared,contract)
if __name__=='__main__':unittest.main(verbosity=2)
