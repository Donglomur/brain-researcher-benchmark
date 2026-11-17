"""Synthetic closed-packet, exact-score and rounding controls; no neural data."""
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import struct

import kernel as k
import certificate as c
import scorer as s
import rounding as r
from closed_interface import FixtureControllerInterface, capture_closed_file

def run(save, temporary):
    records = []
    def check(name, value):
        if not value:
            raise AssertionError(name)
        records.append({'name': name, 'passed': True})
    def refuses(name, fn, kinds=(ValueError,)):
        try:
            fn()
        except kinds:
            check(name, True)
        else:
            raise AssertionError(name + ': expected refusal')
    def context():
        return c.FixtureContext(*(hashlib.sha256(x).hexdigest() for x in
                                 (b'invented-fixture', b'invented-source', b'invented-runtime')),
                                'synthetic-interface')
    empty = k.Window(None, (0,)*7, 0)
    def reference(targets, ctx):
        slots = [empty if q is None else k.Window(k.from_rat(k.Rat(q.numerator, q.denominator)),
                                                 (28,)*7, 7) for q in targets]
        return c.pack_fixture_reference(slots, ctx)
    def setup(targets):
        ctx = context(); raw = reference(targets, ctx); refpin = c.pin(raw); writes = {}
        def writer(name, body):
            if name in writes or type(body) is not bytes:
                raise AssertionError('unique exact private output')
            writes[name] = body
        controller = FixtureControllerInterface(reference_body=raw, reference_pin=refpin,
                                                context=ctx, private_writer=writer)
        return controller, writes, raw, refpin, ctx
    def outcome(writes, ordinal=1):
        return json.loads(writes[f'submission-{ordinal:02d}.outcome.private.json'])
    def rational(x):
        return Fraction(int(x['numerator']), int(x['denominator']))
    def interval(x):
        return rational(x['lower']), rational(x['upper'])
    def full_metrics(out, targets, values):
        score = out['score']; errors = []
        for idx, (target, value, slot) in enumerate(zip(targets, values, score['slots'])):
            assert slot['index'] == idx
            if target is None:
                assert slot['category'] == 'source_undefined' and slot['signed'] is None and slot['absolute'] is None
                errors.append(None)
            else:
                z = Fraction.from_float(value); delta = z-target
                assert slot['category'] == 'finite'
                assert interval(slot['signed']) == (delta, delta)
                assert interval(slot['absolute']) == (abs(delta), abs(delta))
                errors.append(abs(delta))
        for metric, subset in [(score['pooled'], errors), *[(score['maps'][name], errors[i*62:(i+1)*62])
                                                          for i, name in enumerate(c.MAPS)]]:
            finite = [x for x in subset if x is not None]
            assert metric['finite_slots'] == len(finite)
            if finite:
                assert interval(metric['MAE']) == (sum(finite)/len(finite),)*2
                assert interval(metric['Linf']) == (max(finite),)*2
            else:
                assert metric['MAE'] is None and metric['Linf'] is None
        return True

    targets = [None if i % 62 == 0 else Fraction((i % 5)-2, 8) for i in range(248)]
    values = [math.nan if x is None else float(x) for x in targets]
    controller, writes, raw, refpin, ctx = setup(targets)
    packet = s.candidate_bytes(values)
    receipt = controller.submit_closed_bytes(packet)
    expected_keys = {'schema','ordinal','bytes','sha256','closed'}
    check('ingestion_only_receipt', set(receipt) == expected_keys and receipt['bytes'] == 2232 and
          receipt['ordinal'] == 1 and receipt['closed'] is True and
          receipt['sha256'] == hashlib.sha256(packet).hexdigest())
    check('complete_positive_248_fraction_metrics', full_metrics(outcome(writes), targets, values))
    rd = json.loads(writes['submission-01.rounding.private.json'])
    check('positive_full_rounding_categories', rd['counts'] ==
          {'contained':244,'disjoint':0,'indeterminate':0,'source_undefined':4} and
          rd['authentic_source'] is False and rd['production_authority_claimed'] is False and
          rd['requires_operator_private_handling'] is True and 'all_results_private' not in rd)

    wrong = [math.nan if math.isnan(x) else x+2.0 for x in values]
    wrong_packet = s.candidate_bytes(wrong)
    controller.submit_closed_bytes(wrong_packet)
    check('complete_wrong_248_fraction_metrics', full_metrics(outcome(writes,2), targets, wrong))
    check('all_finite_wrong_values_unclipped', outcome(writes,2)['score']['out_of_proved_range_candidate_values'] == 244 and
          interval(outcome(writes,2)['score']['pooled']['MAE']) == (Fraction(2),)*2)
    check('wrong_full_rounding_disjoint', json.loads(writes['submission-02.rounding.private.json'])['counts'] ==
          {'contained':0,'disjoint':244,'indeterminate':0,'source_undefined':4})
    save('SYNTHETIC_REFERENCE.json',raw)
    save('SYNTHETIC_POSITIVE.bin',packet)
    save('SYNTHETIC_WRONG.bin',wrong_packet)
    for name, body in writes.items():
        save('example-'+name,body)

    mismatch = list(values); mismatch[1] = math.nan
    mismatch_receipt = controller.submit_closed_bytes(s.candidate_bytes(mismatch))
    check('target_category_refusal_stays_private', set(mismatch_receipt) == expected_keys and
          outcome(writes,3)['status'] == 'refused' and
          'score' not in mismatch_receipt and 'reason' not in mismatch_receipt and
          'submission-03.rounding.private.json' not in writes)

    def private_refusal(name, bad):
        obj, log, *_ = setup(targets)
        rec = obj.submit_closed_bytes(bad)
        check(name, set(rec) == expected_keys and outcome(log)['status'] == 'refused')
    invalid = bytearray(packet); invalid[1985] = 2
    private_refusal('invalid_flag_receipt_not_score',bytes(invalid))
    invalid = bytearray(packet); invalid[1985] = 1
    private_refusal('incoherent_nan_flag_private_refusal',bytes(invalid))
    invalid = bytearray(packet); invalid[8:16] = struct.pack('<d',math.inf)
    private_refusal('infinite_candidate_private_refusal',bytes(invalid))
    private_refusal('truncated_candidate_private_refusal',packet[:-1])

    obj, log, *_ = setup(targets)
    refuses('oversized_candidate_before_hash_or_write',lambda:obj.submit_closed_bytes(packet+b'\0'))
    refuses('mutable_candidate_body_refused',lambda:obj.submit_closed_bytes(bytearray(packet)))
    check('prehash_refusals_have_no_private_artifact',log == {})
    for _ in range(4):obj.submit_closed_bytes(packet)
    refuses('failed_admissions_consume_attempts',lambda:obj.submit_closed_bytes(packet))
    check('attempt_ordinals_include_failed_admissions',outcome(log,3)['status'] == 'scored' and
          outcome(log,6)['status'] == 'scored')

    obj, log, raw, refpin, ctx = setup(targets)
    refpin['sha256'] = '0'*64
    object.__setattr__(ctx,'attempt','changed-caller-context')
    obj.submit_closed_bytes(packet)
    check('reference_pin_context_defensive_snapshot',outcome(log)['status'] == 'scored')
    for limit in (True,0,7,6.0):
        refuses('strict_submission_limit_'+str(limit),lambda limit=limit:FixtureControllerInterface(
            reference_body=raw,reference_pin=c.pin(raw),context=context(),private_writer=lambda *_:None,
            max_submissions=limit))

    obj, log, *_ = setup([None]*248)
    obj.submit_closed_bytes(s.candidate_bytes([math.nan]*248))
    sc = outcome(log)['score']; diag = json.loads(log['submission-01.rounding.private.json'])
    check('empty_case_not_perfect_accuracy',sc['finite_slots']==0 and not sc['informative'] and
          sc['pooled']=={'finite_slots':0,'MAE':None,'Linf':None} and
          diag['certified_fraction_bounds'] is None and not diag['informative'])

    unequal = [Fraction(0)]*63+[None]*185
    obj, log, *_ = setup(unequal)
    unequal_values = [1.0]*62+[0.0]+[math.nan]*185
    obj.submit_closed_bytes(s.candidate_bytes(unequal_values))
    check('pooled_errors_weight_all_finite_slots',full_metrics(outcome(log),unequal,unequal_values) and
          interval(outcome(log)['score']['pooled']['MAE']) == (Fraction(62,63),)*2 and
          interval(outcome(log)['score']['maps']['NT.delay1']['MAE']) == (Fraction(1),)*2 and
          outcome(log)['score']['maps']['T.delay1']['MAE'] is None)

    obj, log, *_ = setup([Fraction(0)]*248)
    obj.submit_closed_bytes(s.candidate_bytes([-0.0,0.0]*124))
    check('signed_zero_numerical_identity',interval(outcome(log)['score']['pooled']['MAE'])==(Fraction(0),)*2 and
          json.loads(log['submission-01.rounding.private.json'])['counts']['contained']==248)

    root = Path(temporary); file = root/'closed.bin'; file.write_bytes(packet)
    check('complete_ordinary_file_capture',capture_closed_file(file)==packet)
    obj, log, *_ = setup(targets)
    obj.submit_closed_file(file)
    check('closed_file_interface_same_packet',log['submission-01.request.private.bin']==packet)
    missing = root/'missing'
    refuses('missing_file_capture_attempt',lambda:obj.submit_closed_file(missing),(OSError,))
    for _ in range(4):obj.submit_closed_bytes(packet)
    refuses('failed_file_capture_consumes_attempt',lambda:obj.submit_closed_bytes(packet))
    alias = root/'link'; alias.symlink_to(file.name)
    refuses('symlink_file_capture_refused',lambda:capture_closed_file(alias),(OSError,))
    large = root/'oversized'; large.write_bytes(packet+b'\0')
    refuses('oversized_file_capture_refused',lambda:capture_closed_file(large))
    refuses('directory_file_capture_refused',lambda:capture_closed_file(root),(ValueError,OSError))

    raw = reference([Fraction(0)]*248,context())
    bad = json.loads(raw);bad['slots'][0]['channel']='different-invented-channel'
    badraw = c.encode(bad)
    refuses('malformed_reference_cannot_create_controller',lambda:FixtureControllerInterface(
        reference_body=badraw,reference_pin=c.pin(badraw),context=context(),private_writer=lambda *_:None))
    refuses('mutable_reference_body_refused',lambda:FixtureControllerInterface(
        reference_body=bytearray(raw),reference_pin=c.pin(raw),context=context(),private_writer=lambda *_:None))
    refuses('fixture_cannot_be_promoted_to_production',lambda:c.admit_production_reference(raw,c.pin(raw),context()))
    refuses('production_scorer_remains_closed',lambda:s.score_production(reference_body=raw))

    cross_ctx = context()
    cross_slots = [k.Window(k.Interval(-1,1),(28,)*7,7)] + [k.Window(k.Interval(0,0),(28,)*7,7)]*247
    cross_ref = c.pack_fixture_reference(cross_slots,cross_ctx); cross_log = {}
    cross = FixtureControllerInterface(reference_body=cross_ref,reference_pin=c.pin(cross_ref),
        context=cross_ctx,private_writer=lambda name,body:cross_log.__setitem__(name,body))
    cross.submit_closed_bytes(s.candidate_bytes([0.0]*248))
    cross_score = outcome(cross_log)['score']
    check('crossing_zero_absolute_interval_and_aggregation',
          interval(cross_score['slots'][0]['signed']) == (-Fraction(1,k.D),Fraction(1,k.D)) and
          interval(cross_score['slots'][0]['absolute']) == (Fraction(0),Fraction(1,k.D)) and
          interval(cross_score['pooled']['MAE']) == (Fraction(0),Fraction(1,248*k.D)) and
          interval(cross_score['pooled']['Linf']) == (Fraction(0),Fraction(1,k.D)))

    halfsub = Fraction(1,1<<1075)
    check('zero_subnormal_rounding_cell',r.cell(0.0)==(-halfsub,halfsub,True) and
          r.cell(-0.0)==r.cell(0.0) and r.verdict(0.0,-halfsub,halfsub)=='contained')
    tiny = float.fromhex('0x0.0000000000001p-1022')
    low, high, even = r.cell(tiny)
    check('odd_smallest_subnormal_ties_excluded',not even and low==halfsub and high==3*halfsub and
          r.verdict(tiny,low,low)=='disjoint' and r.verdict(tiny,high,high)=='disjoint')
    low, high, even = r.cell(0.5)
    check('even_rounding_ties_included',even and r.verdict(0.5,low,low)=='contained' and
          r.verdict(0.5,high,high)=='contained')
    odd = math.nextafter(0.5,math.inf);lo,hi,even = r.cell(odd)
    check('odd_normal_rounding_ties_excluded',not even and r.verdict(odd,lo,lo)=='disjoint' and
          r.verdict(odd,hi,hi)=='disjoint')
    check('partial_rounding_overlap_indeterminate',r.verdict(0.5,low-halfsub,low+halfsub)=='indeterminate')
    check('binade_asymmetric_cell',r.cell(1.0)==(Fraction(1)-Fraction(1,1<<54),Fraction(1)+Fraction(1,1<<53),True))
    minimum_normal = float.fromhex('0x1.0000000000000p-1022')
    q = Fraction.from_float(minimum_normal)
    check('normal_subnormal_transition_cell',r.cell(minimum_normal)==(q-halfsub,q+halfsub,True))
    check('far_outside_target_domain_disjoint',r.verdict(3.0,Fraction(-1),Fraction(1))=='disjoint')
    refuses('nonreduced_rational_refused',lambda:r.rational({'numerator':'2','denominator':'2'}))
    refuses('owned_score_schema_not_accepted_as_fixture',lambda:r.from_score(packet,
            {'schema':'tms_exact_real_owned_continuous_score_v1','all248_categories_match':True,'slots':[{}]*248}))
    original = outcome(writes)['score']; promoted = dict(original);promoted['authentic_source']=True
    refuses('rounding_fixture_authority_cannot_be_promoted',lambda:r.from_score(packet,promoted))

    assert len({x['name'] for x in records})==len(records)
    return {'schema':'tms_closed_interface_synthetic_controls_v1','all_passed':True,
            'controls':records,'control_count':len(records),'authentic_inputs':0,'models':0,
            'native_candidates':0,'new_benchmarks':0,'fixture_only':True,
            'complete_candidate_coordinates':248}
