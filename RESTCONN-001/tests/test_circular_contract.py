"""Manufactured-only draft tests. No source, bank, task or output imports."""
import copy
from decimal import Decimal
import math

import numpy as np
import pytest

import circular_contract as c


def example(clean=None,active=None):
    clean=np.asarray(clean if clean is not None else [[1,1],[0,1],[-1,0],[0,0],[0,0]],float)
    n=len(clean);active=np.asarray([True,True] if active is None else active,dtype=bool)
    labels=np.asarray(["R DMN","Cereb"]+[f"map_{i}" for i in range(2,39)])
    raw=np.arange(n*39,dtype=float).reshape(n,39)/37
    basis=dict(participant_id=c.SUBJECT,frame_indices=np.arange(n),map_ids=np.arange(39),map_labels=labels,
               raw_coefficients=raw,cleaned_series=clean,target_labels=c.TARGETS,active=active)
    receipt=dict(participant_id=np.array(c.SUBJECT),frame_indices=np.arange(n),map_ids=np.arange(39),
                 map_labels=labels.copy(),raw_coefficients=raw.copy())
    rows=[dict(frame_index=str(i),**{label:repr(float(clean[i,k])) for k,label in enumerate(c.TARGETS)}) for i in range(n)]
    return basis,receipt,rows,c.circular_evidence(clean,active)


def test_complete_basic_tied_offsets():
    basis,receipt,rows,report=example()
    assert report["inference"]["shifts"]==[1,2,3,4]
    assert report["inference"]["n_exceedances"]==3
    assert report["p_value"]==.8
    assert c.validate_submission(receipt,rows,report,basis)["status"]=="accepted"


@pytest.mark.parametrize("kind",["positive","negative","zero"])
def test_signed_results_no_direction_gate(kind):
    x=np.array([-1.,0,1,0]);y={"positive":x,"negative":-x,"zero":np.array([0.,1,0,-1])}[kind]
    result=c.circular_evidence(np.column_stack([x,y]),[True,True])
    assert result["r"]==pytest.approx({"positive":1.,"negative":-1.,"zero":0.}[kind],abs=1e-14)
    assert type(result["significant"]) is bool


def test_periodic_vectors_not_deduplicated_and_sign_ties_count():
    x=np.tile([1.,-1.],4)
    result=c.circular_evidence(np.column_stack([x,x]),[True,True])
    assert result["inference"]["shifts"]==list(range(1,8))
    assert len(set(result["inference"]["null_r"]))==2
    assert result["inference"]["exceeds"]==[True]*7
    assert result["inference"]["n_exceedances"]==7 and result["p_value"]==1.


@pytest.mark.parametrize("numerator,denominator,expected",[(1,20,False),(1,21,True),(2,40,False),(2,41,True),(3,59,False),(1,4,False)])
def test_exact_strict_alpha(numerator,denominator,expected):
    assert c.strict_alpha(numerator,denominator) is expected


@pytest.mark.parametrize("active",[[False,False],[False,True],[True,False]])
def test_explicit_inactive_nulls_with_full_offsets(active):
    clean=np.array([[0,0],[1,0],[0,1],[-1,0],[0,-1]],float)
    clean[:,~np.array(active)]=0
    basis,receipt,rows,result=example(clean,active)
    assert result["status"]=="inactive_target"
    assert all(result[k] is None for k in ("r","p_value","significant"))
    assert result["inference"]["denominator"]==5
    assert result["inference"]["null_r"]==[None]*4
    assert result["inference"]["exceeds"]==[None]*4
    assert c.validate_submission(receipt,rows,result,basis)["status"]=="accepted"


def test_inactive_receipt_jitter_cannot_restore_inference():
    basis,receipt,rows,result=example(np.column_stack([np.zeros(5),[1,0,-1,0,0]]),[False,True])
    for row in rows:row["R DMN"]=str(int(row["frame_index"])*1e-9)
    assert c.validate_submission(receipt,rows,result,basis)["inference_status"]=="inactive_target"
    wrong=c.circular_evidence(np.array([[float(row[k]) for k in c.TARGETS] for row in rows]),[True,True])
    with pytest.raises(ValueError,match="literal exact|null required"):c.validate_submission(receipt,rows,wrong,basis)


def test_coherent_axes_rows_and_shift_permutations():
    basis,receipt,rows,result=example()
    receipt["frame_indices"]=receipt["frame_indices"][::-1].astype(float)
    receipt["map_ids"]=receipt["map_ids"][::-1].astype(float)
    receipt["map_labels"]=receipt["map_labels"][::-1].astype("S")
    receipt["raw_coefficients"]=receipt["raw_coefficients"][::-1,::-1]
    receipt["participant_id"]=receipt["participant_id"].astype("S")
    rows=[dict(reversed(list(row.items()))) for row in rows[::-1]]
    for row in rows:row["frame_index"]+= "e0"
    for key in ("shifts","null_r","exceeds"):result["inference"][key].reverse()
    assert c.validate_submission(receipt,rows,result,basis)["status"]=="accepted"


def test_six_decimal_receipts_do_not_define_rank():
    basis,receipt,rows,result=example()
    result["r"]=round(result["r"],6)
    result["inference"]["null_r"]=[round(x,6) for x in result["inference"]["null_r"]]
    assert c.validate_submission(receipt,rows,result,basis)["status"]=="accepted"


def test_float32_primitive_serialization_within_candidates():
    basis,receipt,rows,result=example()
    receipt["raw_coefficients"]=receipt["raw_coefficients"].astype(np.float32)
    for row in rows:
        for label in c.TARGETS:row[label]=repr(float(np.float32(row[label])))
    assert c.validate_submission(receipt,rows,result,basis)["status"]=="accepted"


def test_coherent_near_tie_can_change_count_and_p():
    basis,receipt,rows,old=example()
    candidate=basis["cleaned_series"].copy();candidate[0,1]+=1e-8
    new=c.circular_evidence(candidate,basis["active"])
    assert old["inference"]["n_exceedances"]!=new["inference"]["n_exceedances"]
    assert abs(old["r"]-new["r"])<c.RECEIPT_ATOL
    rows[0]["Cereb"]=repr(float(candidate[0,1]))
    assert c.validate_submission(receipt,rows,new,basis)["status"]=="accepted"
    with pytest.raises(ValueError,match="numeric precision|integer exact|Boolean exact"):
        c.validate_submission(receipt,rows,old,basis)


def test_counting_rounded_null_receipts_is_not_the_public_rank():
    clean=np.array([[1,1+1e-8],[0,1],[-1,0],[0,0],[0,0]],float)
    expected=c.circular_evidence(clean,[True,True]);actual=copy.deepcopy(expected)
    actual["r"]=round(actual["r"],6)
    actual["inference"]["null_r"]=[round(v,6) for v in actual["inference"]["null_r"]]
    rounded_count=sum(abs(v)>=abs(actual["r"]) for v in actual["inference"]["null_r"])
    assert rounded_count!=expected["inference"]["n_exceedances"]
    assert c.validate_report(actual,expected)["status"]=="accepted"
    actual["inference"]["n_exceedances"]=rounded_count
    with pytest.raises(ValueError,match="integer exact"):c.validate_report(actual,expected)


@pytest.mark.parametrize("wrong_comparison",["strict_greater","one_sided"])
def test_comparison_component_controls(wrong_comparison):
    _,_,_,expected=example();actual=copy.deepcopy(expected);inf=actual["inference"]
    observed=expected["r"]
    wrong=[abs(value)>abs(observed) if wrong_comparison=="strict_greater" else value>=observed for value in inf["null_r"]]
    assert wrong!=inf["exceeds"]
    inf["exceeds"]=wrong
    with pytest.raises(ValueError,match="Boolean exact"):c.validate_report(actual,expected)


def test_reverse_shift_direction_changes_keyed_null_not_p():
    clean=np.column_stack([[1.,0,0,0,0],[0.,1,2,3,4]])
    _,_,_,result=example(clean)
    wrong=copy.deepcopy(result);wrong["inference"]["null_r"].reverse()
    assert result["p_value"]==wrong["p_value"]
    assert not np.allclose(wrong["inference"]["null_r"],result["inference"]["null_r"],atol=1e-6)
    with pytest.raises(ValueError,match="numeric precision"):c.validate_report(wrong,result)


def test_huge_and_tiny_finite_series_do_not_overflow_norms():
    pattern=np.array([-1.,-.5,.25,1.,.75])
    ordinary=c.circular_evidence(np.column_stack([pattern,pattern[::-1]]),[True,True])
    for scale in (1e-300,1e300):
        result=c.circular_evidence(np.column_stack([pattern*scale,pattern[::-1]*scale]),[True,True])
        assert math.isfinite(result["r"])
        assert result["r"]==pytest.approx(ordinary["r"],abs=1e-14)


@pytest.mark.parametrize("value",[True,np.bool_(False),"1",None,1.5,np.nan,np.inf,Decimal("1e100000000"),2**63,-2**63-1])
def test_integer_rejects_invalid_types_fraction_nonfinite_and_bounds(value):
    with pytest.raises(ValueError):c.integer(value)


@pytest.mark.parametrize("value",[0,1.,np.int64(2),Decimal("3e0"),2**53+1,2**63-1,-2**63])
def test_integer_exact_without_float_cast(value):
    assert c.integer(value)==int(value)


@pytest.mark.parametrize("bad",[[0,True],[0,.5],np.array([False,True]),np.array([0,np.inf]),np.array([0,2**63],dtype=np.uint64)])
def test_bad_integer_axes(bad):
    with pytest.raises(ValueError):c.integer_axis(bad,[0,1])


@pytest.mark.parametrize("bad",[[1,True],np.array([True,False]),["1","2"],[1,None],np.array([1+2j]),np.array([1],dtype=object),[1,np.nan]])
def test_real_array_type_and_finiteness(bad):
    with pytest.raises(ValueError):c.real_array(bad)


@pytest.mark.parametrize("bad",[True,"1",None,float("inf"),Decimal("NaN")])
def test_typed_json_numbers(bad):
    with pytest.raises(ValueError):c.number(bad)


@pytest.mark.parametrize("bad",[{"note":{"x":float("inf")}},[Decimal("1e999")],{"x":np.array([1.])},{1:"bad-key"}])
def test_nonfinite_extra_json_rejected(bad):
    with pytest.raises(ValueError):c.finite_json(bad)


def test_harmless_json_extras_accepted():
    _,_,_,result=example();actual=copy.deepcopy(result)
    actual["notes"]={"free":True,"unused":None,"extra":1.}
    actual["inference"]["description"]="No mandatory claim"
    assert c.validate_report(actual,result)["status"]=="accepted"


@pytest.mark.parametrize("value",[1.0000001,-1.0000001])
def test_correlation_natural_domain_not_relaxed_by_receipt_tolerance(value):
    x=np.array([-1.,0,1,0]);expected=c.circular_evidence(np.column_stack([x,x if value>0 else -x]),[True,True])
    actual=copy.deepcopy(expected);actual["r"]=value
    with pytest.raises(ValueError,match="correlation domain"):c.validate_report(actual,expected)


@pytest.mark.parametrize("mode",["missing_raw_key","subject","raw_shape","raw_wrong","raw_nonfinite","map_duplicate","map_label","map_fraction",
                               "frame_duplicate","frame_missing","frame_extra","frame_fraction","frame_bool","clean_nonfinite",
                               "clean_swapped","clean_wrong","two_map_only"])
def test_bad_source_primitives(mode):
    basis,receipt,rows,result=example()
    if mode=="missing_raw_key":del receipt["map_labels"]
    elif mode=="subject":receipt["participant_id"]=np.array("10064")
    elif mode=="raw_shape":receipt["raw_coefficients"]=receipt["raw_coefficients"][:-1]
    elif mode=="raw_wrong":receipt["raw_coefficients"][0,3]+=1
    elif mode=="raw_nonfinite":receipt["raw_coefficients"][0,3]=np.nan
    elif mode=="map_duplicate":receipt["map_ids"][0]=receipt["map_ids"][1]
    elif mode=="map_label":receipt["map_labels"][0]="wrong"
    elif mode=="map_fraction":receipt["map_ids"]=receipt["map_ids"].astype(float);receipt["map_ids"][0]=.5
    elif mode=="frame_duplicate":rows[1]["frame_index"]=rows[0]["frame_index"]
    elif mode=="frame_missing":rows.pop()
    elif mode=="frame_extra":rows.append(rows[-1].copy())
    elif mode=="frame_fraction":rows[0]["frame_index"]=".5"
    elif mode=="frame_bool":rows[0]["frame_index"]=False
    elif mode=="clean_nonfinite":rows[0]["R DMN"]="NaN"
    elif mode=="clean_swapped":
        for row in rows:row["R DMN"],row["Cereb"]=row["Cereb"],row["R DMN"]
    elif mode=="clean_wrong":rows[0]["R DMN"]="100"
    else:receipt["raw_coefficients"]=receipt["raw_coefficients"][:,:2]
    with pytest.raises(ValueError):c.validate_submission(receipt,rows,result,basis)


def test_centered_fidelity_blocks_small_signal_fabrication():
    reference=np.column_stack([[0.,1e-10,0.,-1e-10],[1.,0.,-1.,0.]])
    candidate=reference.copy();candidate[:,0]=[1e-9,0,-1e-9,0]
    assert np.all(np.abs(candidate-reference)<=c.SIGNAL_ATOL+c.SIGNAL_RTOL*np.abs(reference))
    with pytest.raises(ValueError,match="centered source fidelity"):c.signal_fidelity(candidate,reference,[True,True])


@pytest.mark.parametrize("mode",["shift_zero","shift_duplicate","shift_missing","shift_float_fraction","shift_bool","shift_string",
                               "null_scalar","null_short","null_wrong","null_bool","null_string","exceed_wrong","exceed_int",
                               "count_bool","count_wrong","numerator_missing_plus_one","denominator_wrong","p_wrong",
                               "verdict_wrong","verdict_string","method_wrong","direction_wrong","alpha_approx",
                               "subject_wrong","r_wrong","headline_alias","missing_field"])
def test_bad_inference_receipts(mode):
    _,_,_,result=example();actual=copy.deepcopy(result);inf=actual["inference"]
    if mode=="shift_zero":inf["shifts"][0]=0
    elif mode=="shift_duplicate":inf["shifts"][0]=inf["shifts"][1]
    elif mode=="shift_missing":inf["shifts"].pop()
    elif mode=="shift_float_fraction":inf["shifts"][0]=1.5
    elif mode=="shift_bool":inf["shifts"][0]=True
    elif mode=="shift_string":inf["shifts"][0]="1"
    elif mode=="null_scalar":inf["null_r"]=0.
    elif mode=="null_short":inf["null_r"].pop()
    elif mode=="null_wrong":inf["null_r"][0]=0.
    elif mode=="null_bool":inf["null_r"][0]=True
    elif mode=="null_string":inf["null_r"][0]=str(inf["null_r"][0])
    elif mode=="exceed_wrong":inf["exceeds"][0]=not inf["exceeds"][0]
    elif mode=="exceed_int":inf["exceeds"][0]=int(inf["exceeds"][0])
    elif mode=="count_bool":inf["n_exceedances"]=True
    elif mode=="count_wrong":inf["n_exceedances"]+=1
    elif mode=="numerator_missing_plus_one":inf["numerator"]-=1
    elif mode=="denominator_wrong":inf["denominator"]-=1
    elif mode=="p_wrong":actual["p_value"]=inf["p_value"]=.01
    elif mode=="verdict_wrong":actual["significant"]=not actual["significant"]
    elif mode=="verdict_string":actual["significant"]="false"
    elif mode=="method_wrong":inf["method"]="max_p"
    elif mode=="direction_wrong":inf["shift_direction"]="negative_np_roll"
    elif mode=="alpha_approx":inf["alpha"]+=1e-10
    elif mode=="subject_wrong":actual["subject"]=10064
    elif mode=="r_wrong":actual["r"]=-actual["r"]
    elif mode=="headline_alias":inf["p_value"]=.1
    else:del actual["status"]
    with pytest.raises(ValueError):c.validate_report(actual,result)


@pytest.mark.parametrize("field",["r","p_value","significant","null_r","exceeds","n_exceedances","numerator"])
def test_undefined_receipts_cannot_be_filled(field):
    _,_,_,result=example(np.zeros((5,2)),[False,False]);actual=copy.deepcopy(result)
    if field in ("r","p_value","significant"):actual[field]=False if field=="significant" else 0.
    elif field in ("null_r","exceeds"):actual["inference"][field][0]=False if field=="exceeds" else 0.
    else:actual["inference"][field]=0
    with pytest.raises(ValueError,match="null required"):c.validate_report(actual,result)


@pytest.mark.parametrize("clean,active",[(np.zeros((5,2)),[True,True]),(np.ones((5,2)),[True,True]),
                                       (np.ones((3,2)),[False,False]),(np.ones((5,3)),[True,True]),
                                       (np.ones((5,2)),[1,1])])
def test_impossible_active_or_bad_input_support(clean,active):
    with pytest.raises(ValueError):c.circular_evidence(clean,active)
