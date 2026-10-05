"""Independent binary-graph arithmetic and strict participant-format validation.

This module does not import the reference solution or read the source images.
Exact graph scores govern categorical ties; printed floating values are tolerant.
"""
from collections import deque
import csv
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import json
import math
from pathlib import Path

import numpy as np

TASK_ID = "NETINTEG-001"
PIPELINE_ID = "adhd40-empirical-pearson-binary-efficiency-v2"
PARTICIPANTS = (10042,10064,10128,21019,23008,23012,27011,27018,27034,27037,
    1019436,1206380,1418396,1517058,1552181,1562298,1679142,2014113,2497695,
    2950754,3007585,3154996,3205761,3520880,3624598,3699991,3884955,3902469,
    3994098,4016887,4046678,4134561,4164316,4275075,6115230,7774305,8409791,
    8697774,9744150,9750701)
DENSITIES = (.05,.075,.1,.15,.2)
KS = (248,371,495,742,990)
ABSOLUTES = (.2,.3,.4)
CONFIGURATIONS = tuple(("proportional",d,k) for d,k in zip(DENSITIES,KS)) + tuple(
    ("absolute",d,None) for d in ABSOLUTES)
FC_FIELDS = ("participant","roi_i","roi_j","correlation")
GRAPH_FIELDS = ("participant","scheme","parameter","n_nodes","n_possible_edges",
    "k_requested","correlation_cutoff","n_at_cutoff","n_edges","realized_density",
    "n_negative_edges","n_zero_edges","n_components","n_connected_pairs",
    "n_disconnected_pairs","minimum_selected_correlation","global_efficiency")
EFFICIENCY_FIELDS = ("participant","n_densities","global_efficiency",
    "mean_signed_correlation","mean_positive_part_correlation")
GRAPH_INTS = frozenset(("participant","n_nodes","n_possible_edges","k_requested",
    "n_at_cutoff","n_edges","n_negative_edges","n_zero_edges","n_components",
    "n_connected_pairs","n_disconnected_pairs"))
FC_TOL = (1e-8,1e-6)
SCALAR_TOL = (1e-8,1e-6)
CORR_TOL = (1e-6,1e-6)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def integer(value):
    require(not isinstance(value,(bool,np.bool_)), "Boolean is not an integer identity/count")
    require(isinstance(value,(str,int,float,np.integer,np.floating)), "Invalid integer type")
    try:
        number = Decimal(str(value).strip())
    except InvalidOperation as error:
        raise AssertionError("Invalid integer notation") from error
    require(number.is_finite() and number == number.to_integral_value(), "Nonintegral/nonfinite identity/count")
    return int(number)


def number(value):
    require(not isinstance(value,(bool,np.bool_)), "Boolean is not a numeric measurement")
    require(isinstance(value,(str,int,float,np.integer,np.floating)), "Invalid numeric type")
    try:
        result = float(value)
    except (TypeError,ValueError,OverflowError) as error:
        raise AssertionError("Invalid numeric measurement") from error
    require(math.isfinite(result), "Nonfinite measurement")
    return result


def close(actual, expected, tolerance=SCALAR_TOL, name="value"):
    actual = number(actual)
    require(abs(actual-float(expected)) <= tolerance[0]+tolerance[1]*abs(float(expected)),
        f"{name} differs from complete source-derived result")


def bounded(value, lower, upper, name):
    parsed = number(value)
    require(lower <= parsed <= upper, f"{name} outside its mathematical domain")
    return parsed


def read_json(path):
    def pairs(items):
        result = {}
        for key,value in items:
            require(key not in result, f"Duplicate JSON key {key}")
            result[key] = value
        return result
    def nonfinite(value):
        raise AssertionError(f"Nonstandard nonfinite JSON value {value}")
    try:
        return json.loads(Path(path).read_text(),object_pairs_hook=pairs,parse_constant=nonfinite)
    except (OSError,ValueError) as error:
        raise AssertionError(f"Cannot read required JSON {Path(path).name}") from error


def read_csv(path, required):
    try:
        with Path(path).open(newline="",encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames
            require(fields is not None and len(fields) == len(set(fields)), "Missing/duplicate CSV header")
            require(set(required) <= set(fields), f"Missing required columns in {Path(path).name}")
            rows = list(reader)
    except OSError as error:
        raise AssertionError(f"Missing required CSV {Path(path).name}") from error
    require(all(None not in row and all(row[field] is not None for field in required) for row in rows),
        "Malformed CSV row; rows are never silently omitted")
    return rows


def configuration(scheme, parameter):
    require(scheme in ("proportional","absolute"), "Unknown graph scheme")
    value = number(parameter)
    matches = [index for index,(s,p,_) in enumerate(CONFIGURATIONS) if s == scheme and abs(value-p) <= 1e-12]
    require(len(matches) == 1, "Unknown/ambiguous graph parameter")
    return matches[0]


def graph_measurements(weights, scheme, parameter, k, n_nodes=100):
    """Independent BFS; distance histogram preserves exact rational efficiency."""
    weights = np.asarray(weights,dtype=np.float64)
    pair_count = math.comb(n_nodes,2)
    require(n_nodes >= 2 and weights.shape == (pair_count,) and np.isfinite(weights).all(), "Invalid complete graph weights")
    cutoff = float(sorted(weights,reverse=True)[k-1]) if k is not None else float(parameter)
    selected = weights >= cutoff
    upper = np.triu_indices(n_nodes,1)
    neighbors = [[] for _ in range(n_nodes)]
    for left,right in zip(upper[0][selected],upper[1][selected]):
        neighbors[int(left)].append(int(right))
        neighbors[int(right)].append(int(left))
    histogram = [0] * n_nodes
    disconnected = 0
    components = 0
    remaining = set(range(n_nodes))
    for start in range(n_nodes):
        distance = [-1] * n_nodes
        distance[start] = 0
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for neighbor in neighbors[current]:
                if distance[neighbor] < 0:
                    distance[neighbor] = distance[current]+1
                    queue.append(neighbor)
        if start in remaining:
            components += 1
            remaining.difference_update(index for index,value in enumerate(distance) if value >= 0)
        for stop in range(start+1,n_nodes):
            if distance[stop] < 0:
                disconnected += 1
            else:
                histogram[distance[stop]] += 1
    exact = sum((Fraction(histogram[d],d) for d in range(1,n_nodes)),Fraction(0))/pair_count
    n_edges = int(selected.sum())
    row = dict(scheme=scheme,parameter=float(parameter),n_nodes=n_nodes,n_possible_edges=pair_count,
        k_requested=k,correlation_cutoff=cutoff,n_at_cutoff=int(np.sum(weights == cutoff)),n_edges=n_edges,
        realized_density=n_edges/pair_count,n_negative_edges=int(np.sum(selected & (weights < 0))),
        n_zero_edges=int(np.sum(selected & (weights == 0))),n_components=components,
        n_connected_pairs=pair_count-disconnected,n_disconnected_pairs=disconnected,
        minimum_selected_correlation=float(np.min(weights[selected])) if n_edges else None,
        global_efficiency=float(exact))
    return row,exact,np.asarray(histogram,dtype=np.int64),selected


def ranks(values):
    order = sorted(range(len(values)),key=values.__getitem__)
    output = np.empty(len(values),dtype=np.float64)
    start = 0
    while start < len(values):
        stop = start+1
        while stop < len(values) and values[order[stop]] == values[order[start]]:
            stop += 1
        output[order[start:stop]] = (start+1+stop)/2
        start = stop
    return output


def centered(values):
    # Center exact graph fractions before conversion, avoiding false constancy
    # when two distinct exact graph means happen to round to the same float.
    if all(isinstance(value,Fraction) for value in values):
        mean = sum(values,Fraction(0))/len(values)
        result = np.array([float(value-mean) for value in values],dtype=np.float64)
    else:
        values = np.asarray(values,dtype=np.float64)
        require(np.isfinite(values).all(), "Nonfinite correlation input")
        result = values-math.fsum(float(value) for value in values)/len(values)
    scale = float(np.max(np.abs(result)))
    require(math.isfinite(scale) and scale > 0, "Numerically unresolved nonconstant diagnostic input")
    return result/scale


def correlation(left, right, spearman=False):
    require(len(left) == len(right) and len(left) > 0, "Unaligned diagnostic vectors")
    n = len(left)
    if all(value == left[0] for value in left) or all(value == right[0] for value in right):
        return dict(value=None,status="undefined_constant",n_participants=n)
    if spearman:
        left,right = ranks(left),ranks(right)
    x,y = centered(left),centered(right)
    numerator = math.fsum(float(a)*float(b) for a,b in zip(x,y))
    denominator = math.sqrt(math.fsum(float(a)**2 for a in x)*math.fsum(float(b)**2 for b in y))
    value = numerator/denominator
    require(math.isfinite(value) and abs(value) <= 1+1e-12, "Correlation arithmetic outside declared range")
    return dict(value=max(-1.,min(1.,value)),status="ok",n_participants=n)


def ranking(participants, scores, k=8):
    require(len(participants) == len(scores) and len(participants) >= k, "Incomplete ranking cohort")
    order = sorted(range(len(scores)),key=scores.__getitem__,reverse=True)
    cutoff = scores[order[k-1]]
    return [int(participants[i]) for i in order],[int(participants[i]) for i in order if scores[i] >= cutoff]


def derive(participants, weights, top_k=8):
    participants = tuple(map(int,participants))
    weights = np.asarray(weights,dtype=np.float64)
    require(weights.shape == (len(participants),4950) and np.isfinite(weights).all(), "Complete participant-connectome matrix required")
    rows,efficiencies,histograms = [],[],[]
    scores = [[] for _ in CONFIGURATIONS]
    densities = [[] for _ in CONFIGURATIONS]
    primary,signed,positive = [],[],[]
    for participant,values in zip(participants,weights):
        local,local_hist = [],[]
        for index,(scheme,parameter,k) in enumerate(CONFIGURATIONS):
            row,exact,hist,_ = graph_measurements(values,scheme,parameter,k)
            rows.append(dict(participant=participant,**row))
            scores[index].append(exact)
            densities[index].append(Fraction(row["n_edges"],4950))
            local.append(exact)
            local_hist.append(hist)
        exact_primary = sum(local[:5],Fraction(0))/5
        mean_signed = math.fsum(map(float,values))/4950
        mean_positive = math.fsum(max(float(value),0.) for value in values)/4950
        efficiencies.append(dict(participant=participant,n_densities=5,global_efficiency=float(exact_primary),
            mean_signed_correlation=mean_signed,mean_positive_part_correlation=mean_positive))
        primary.append(exact_primary)
        signed.append(mean_signed)
        positive.append(mean_positive)
        histograms.append(local_hist)
    primary_order,primary_top = ranking(participants,primary,top_k)
    config_rows = []
    for (scheme,parameter,_),values,density in zip(CONFIGURATIONS,scores,densities):
        order,top = ranking(participants,values,top_k)
        config_rows.append(dict(scheme=scheme,parameter=parameter,ranking_by_efficiency=order,
            top_by_efficiency=top,top_set_overlap_with_primary=len(set(top)&set(primary_top)),
            correlations=dict(efficiency_vs_mean_signed_correlation=correlation(values,signed),
                efficiency_vs_mean_positive_part_correlation=correlation(values,positive),
                realized_density_vs_mean_signed_correlation=correlation(density,signed),
                realized_density_vs_mean_positive_part_correlation=correlation(density,positive),
                spearman_vs_primary=correlation(values,primary,True))))
    result = dict(status="ok",task_id=TASK_ID,pipeline_id=PIPELINE_ID,n_participants=len(participants),
        n_rois=100,n_configurations=8,top_k=top_k,ranking_by_efficiency=primary_order,top_by_efficiency=primary_top,
        primary_correlations=dict(efficiency_vs_mean_signed_correlation=correlation(primary,signed),
            efficiency_vs_mean_positive_part_correlation=correlation(primary,positive)),
        configuration_rankings=config_rows,density_pairwise_spearman=[dict(density_low=DENSITIES[i],
            density_high=DENSITIES[j],spearman=correlation(scores[i],scores[j],True)) for i in range(5) for j in range(i+1,5)])
    return dict(participants=participants,weights=weights,graph_rows=rows,efficiency_rows=efficiencies,
        exact_primary=primary,exact_configurations=scores,histograms=np.asarray(histograms),ranking=result)


def required_object(actual, expected, tolerance=SCALAR_TOL, path="object", closed=False):
    require(isinstance(actual,dict), f"{path} must be an object")
    require(set(expected) <= set(actual), f"Missing required field in {path}")
    if closed:
        require(set(actual) == set(expected), f"Extra identity/contract field in {path}")
    for key,value in expected.items():
        current = actual[key]
        name = f"{path}.{key}"
        if isinstance(value,dict):
            required_object(current,value,tolerance,name,closed)
        elif isinstance(value,list):
            require(isinstance(current,list) and len(current) == len(value), f"Wrong list shape in {name}")
            for i,(a,b) in enumerate(zip(current,value)):
                required_object({"item":a},{"item":b},tolerance,f"{name}[{i}]",closed)
        elif value is None:
            require(current is None, f"Undefined {name} must be JSON null")
        elif isinstance(value,bool):
            require(isinstance(current,bool) and current == value, f"Wrong boolean {name}")
        elif isinstance(value,int):
            require(integer(current) == value, f"Wrong integer {name}")
        elif isinstance(value,float):
            close(current,value,tolerance,name)
        else:
            require(isinstance(current,str) and current == value, f"Wrong identity/status {name}")


def validate_connectomes(path, reference):
    rows = read_csv(path,FC_FIELDS)
    participants = reference["participants"]
    require(len(rows) == len(participants)*4950, "Complete participant-pair coverage required")
    positions = {p:index for index,p in enumerate(participants)}
    pair_positions = {(int(i+1),int(j+1)):index for index,(i,j) in enumerate(zip(*np.triu_indices(100,1)))}
    values = np.empty_like(reference["weights"])
    seen = set()
    for row in rows:
        participant,i,j = (integer(row[field]) for field in FC_FIELDS[:3])
        key = (participant,i,j)
        require(participant in positions and (i,j) in pair_positions, "Unknown participant/ROI identity or lower-triangle pair")
        require(key not in seen, "Duplicate participant-pair identity")
        seen.add(key)
        values[positions[participant],pair_positions[i,j]] = bounded(row["correlation"],-1-1e-12,1+1e-12,"Pearson weight")
    tolerance = FC_TOL[0]+FC_TOL[1]*np.abs(reference["weights"])
    require(np.all(np.abs(values-reference["weights"]) <= tolerance), "Connectome differs from original source-derived weights")
    return values


def validate_graphs(path, reference):
    rows = read_csv(path,GRAPH_FIELDS)
    expected = {(row["participant"],configuration(row["scheme"],row["parameter"])):row for row in reference["graph_rows"]}
    require(len(rows) == len(expected), "Complete eight-configuration graph coverage required")
    seen = set()
    for row in rows:
        key = (integer(row["participant"]),configuration(row["scheme"],row["parameter"]))
        require(key in expected and key not in seen, "Missing/duplicate/unknown participant-configuration identity")
        seen.add(key)
        for field in GRAPH_FIELDS:
            value = expected[key][field]
            if value is None:
                require(row[field].strip() == "", f"Undefined {field} must be blank")
            elif field in GRAPH_INTS:
                require(integer(row[field]) == value, f"Wrong source-derived graph count {field}")
            elif field == "scheme":
                require(row[field] == value, "Wrong graph scheme")
            elif field == "parameter":
                close(row[field],value,(1e-12,0),field)
            else:
                close(row[field],value,FC_TOL if field in ("correlation_cutoff","minimum_selected_correlation") else SCALAR_TOL,field)
        close(row["realized_density"],integer(row["n_edges"])/4950,SCALAR_TOL,"realized_density arithmetic")
        bounded(row["realized_density"],0,1,"Realized density")
        bounded(row["global_efficiency"],0,1,"Global efficiency")
        require(integer(row["n_connected_pairs"])+integer(row["n_disconnected_pairs"]) == 4950,
            "Connected and disconnected pair counts must exhaust all distinct pairs")


def validate_efficiencies(path, reference):
    rows = read_csv(path,EFFICIENCY_FIELDS)
    expected = {row["participant"]:row for row in reference["efficiency_rows"]}
    require(len(rows) == len(expected), "Complete primary-efficiency cohort required")
    seen = set()
    for row in rows:
        participant = integer(row["participant"])
        require(participant in expected and participant not in seen, "Missing/duplicate/unknown primary participant")
        seen.add(participant)
        require(integer(row["n_densities"]) == 5, "Primary mean requires exactly five densities")
        for field in EFFICIENCY_FIELDS[2:]:
            close(row[field],expected[participant][field],SCALAR_TOL,field)
        bounded(row["global_efficiency"],0,1,"Primary global efficiency")
        bounded(row["mean_signed_correlation"],-1-1e-12,1+1e-12,"Mean signed correlation")
        bounded(row["mean_positive_part_correlation"],0,1+1e-12,"Mean positive-part correlation")


def validate_order(actual, participants, scores, top_k):
    require(isinstance(actual,dict) and {"ranking_by_efficiency","top_by_efficiency"} <= set(actual), "Ranking fields missing")
    order = actual["ranking_by_efficiency"]
    require(isinstance(order,list), "Ranking must be an ID list")
    order = [integer(value) for value in order]
    require(len(order) == len(participants) and set(order) == set(participants), "Ranking must include every person exactly once")
    by_id = dict(zip(participants,scores))
    require(all(by_id[a] >= by_id[b] for a,b in zip(order,order[1:])), "Ranking changes source-authoritative exact score order")
    require(isinstance(actual["top_by_efficiency"],list), "Top set must be an ID list")
    top = [integer(value) for value in actual["top_by_efficiency"]]
    _,expected_top = ranking(participants,scores,top_k)
    require(len(top) == len(set(top)) and set(top) == set(expected_top), "Top set must include every exact eighth-boundary tie")


def validate_ranking(actual, reference):
    expected = reference["ranking"]
    basic = {key:value for key,value in expected.items() if key not in (
        "ranking_by_efficiency","top_by_efficiency","configuration_rankings","density_pairwise_spearman")}
    required_object(actual,basic,CORR_TOL,"ranking")
    validate_diagnostics(actual["primary_correlations"],expected["primary_correlations"])
    validate_order(actual,reference["participants"],reference["exact_primary"],expected["top_k"])
    require("configuration_rankings" in actual and isinstance(actual["configuration_rankings"],list), "Missing configuration ranking records")
    require(len(actual["configuration_rankings"]) == 8, "All eight configuration rankings required")
    seen = set()
    for row in actual["configuration_rankings"]:
        require(isinstance(row,dict) and {"scheme","parameter"} <= set(row), "Invalid configuration ranking identity")
        index = configuration(row["scheme"],row["parameter"])
        require(index not in seen, "Duplicate configuration ranking")
        seen.add(index)
        required_object(row,{key:value for key,value in expected["configuration_rankings"][index].items()
            if key not in ("ranking_by_efficiency","top_by_efficiency")},CORR_TOL,"configuration ranking")
        validate_diagnostics(row["correlations"],expected["configuration_rankings"][index]["correlations"])
        validate_order(row,reference["participants"],reference["exact_configurations"][index],expected["top_k"])
    require("density_pairwise_spearman" in actual and isinstance(actual["density_pairwise_spearman"],list), "Missing density sensitivity records")
    pairs = {(row["density_low"],row["density_high"]):row for row in expected["density_pairwise_spearman"]}
    require(len(actual["density_pairwise_spearman"]) == 10, "All ten density-pair comparisons required")
    seen = set()
    for row in actual["density_pairwise_spearman"]:
        require(isinstance(row,dict) and {"density_low","density_high"} <= set(row), "Invalid density-pair identity")
        low = CONFIGURATIONS[configuration("proportional",row["density_low"])][1]
        high = CONFIGURATIONS[configuration("proportional",row["density_high"])][1]
        key = (low,high)
        require(key in pairs and key not in seen, "Missing/duplicate/unordered density-pair identity")
        seen.add(key)
        required_object(row,pairs[key],CORR_TOL,"density pair")
        validate_diagnostics({"spearman":row["spearman"]},{"spearman":pairs[key]["spearman"]})


def validate_diagnostics(actual, expected):
    require(isinstance(actual,dict) and set(actual)==set(expected), "Wrong required diagnostic identity set")
    for name,row in actual.items():
        required_object(row,expected[name],CORR_TOL,"diagnostic correlation")
        if row["value"] is not None:
            bounded(row["value"],-1,1,"Diagnostic correlation")


def validate_metadata(actual, expected):
    basic = {key:value for key,value in expected.items() if key not in ("source_observed","software_versions","source_sha256","method_contract")}
    required_object(actual,basic,(0,0),"metadata")
    for key in ("source_sha256","method_contract"):
        require(key in actual, f"Missing metadata {key}")
        required_object(actual[key],expected[key],(0,0),key,closed=True)
    versions = actual.get("software_versions")
    require(isinstance(versions,dict) and versions and all(isinstance(k,str) and k.strip()
        and isinstance(v,str) and v.strip() for k,v in versions.items()), "Report actual nonempty software versions")
    observed = actual.get("source_observed")
    require(isinstance(observed,dict) and {"atlas","participants"} <= set(observed), "Missing source-observed metadata")
    atlas,atlas_expected = observed["atlas"],expected["source_observed"]["atlas"]
    require(isinstance(atlas,dict) and set(atlas_expected) <= set(atlas), "Missing atlas observations")
    require(isinstance(atlas["parcels"],list) and len(atlas["parcels"]) == 100, "All original parcel support records required")
    indexed = {}
    for row in atlas["parcels"]:
        require(isinstance(row,dict) and "roi_id" in row, "Invalid parcel support identity")
        roi = integer(row["roi_id"])
        require(roi not in indexed, "Duplicate parcel support identity")
        indexed[roi] = row
    require(set(indexed) == set(range(1,101)), "Incomplete original parcel support")
    for row in atlas_expected["parcels"]:
        required_object(indexed[row["roi_id"]],row,(0,0),"parcel support")
    require(isinstance(atlas["source_label_ids"],list), "Invalid original label IDs")
    ids = [integer(value) for value in atlas["source_label_ids"]]
    require(len(ids) == len(set(ids)) and set(ids) == set(atlas_expected["source_label_ids"]), "Wrong original atlas label IDs")
    validate_observed_fields(atlas,atlas_expected,exclude=("parcels","source_label_ids"))
    rows = observed["participants"]
    expected_rows = expected["source_observed"]["participants"]
    require(isinstance(rows,list) and len(rows) == len(expected_rows), "All source participant observations required")
    indexed = {}
    for row in rows:
        require(isinstance(row,dict) and "participant" in row, "Invalid observed participant identity")
        participant = integer(row["participant"])
        require(participant not in indexed, "Duplicate observed participant")
        indexed[participant] = row
    require(set(indexed) == {row["participant"] for row in expected_rows}, "Wrong observed source cohort")
    for row in expected_rows:
        validate_observed_fields(indexed[row["participant"]],row)


def validate_observed_fields(actual, expected, exclude=()):
    for key,value in expected.items():
        if key in exclude:
            continue
        require(key in actual, f"Missing observed field {key}")
        tolerance = (0,0)
        if key in ("affine","source_affine","target_affine","voxel_sizes_mm"):
            tolerance = (1e-6,0)
        elif key == "tr_s":
            tolerance = (1e-8,1e-8)
        elif key in ("intensity_slope","intensity_intercept"):
            tolerance = (0,1e-10)
        elif key == "confound_rank_threshold":
            tolerance = (0,1e-8)
        if key == "storage_dtype":
            try:
                require(np.dtype(actual[key]) == np.dtype(value), "Wrong source storage dtype")
            except (TypeError,ValueError) as error:
                raise AssertionError("Invalid source storage dtype") from error
        else:
            required_object({key:actual[key]},{key:value},tolerance,"source observation")


def validate_output_directory(output, reference):
    output = Path(output)
    validate_connectomes(output/"connectomes.csv",reference)
    validate_graphs(output/"graph_metrics.csv",reference)
    validate_efficiencies(output/"efficiency.csv",reference)
    validate_ranking(read_json(output/"ranking.json"),reference)
    validate_metadata(read_json(output/"run_metadata.json"),reference["metadata"])
    require((output/"findings.md").is_file() and (output/"findings.md").read_text().strip(), "Nonempty findings required")
