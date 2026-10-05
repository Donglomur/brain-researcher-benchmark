"""Offline empirical-Pearson binary-graph sensitivity control, not brain ranking.

No source reads or computation occur at import. The public method fixes the
estimand before source outcomes; exact rational graph scores define ties.
"""
import argparse
import csv
from fractions import Fraction
import hashlib
import importlib.util
import json
import platform
from pathlib import Path

import nibabel as nib
import numpy as np
import scipy
from scipy.ndimage import affine_transform
from scipy.sparse.csgraph import connected_components, shortest_path

TASK_ID = "NETINTEG-001"
PIPELINE_ID = "adhd40-empirical-pearson-binary-efficiency-v2"
METHOD_SHA256 = "8053a2afbe2a23d1dabd70e03e55bace10e70b221b84a97a959e7f7894f5273d"
SOURCE_SHA256 = "6bc0e95fdd48ed3d3229acc9ce9e48a55860837a5e10d3acade4f0d645cbc5aa"
PARTICIPANTS = [10042,10064,10128,21019,23008,23012,27011,27018,27034,27037,
    1019436,1206380,1418396,1517058,1552181,1562298,1679142,2014113,2497695,
    2950754,3007585,3154996,3205761,3520880,3624598,3699991,3884955,3902469,
    3994098,4016887,4046678,4134561,4164316,4275075,6115230,7774305,8409791,
    8697774,9744150,9750701]
CONFOUNDS = ["csf","constant","linearTrend","wm","global","motion-pitch",
    "motion-roll","motion-yaw","motion-x","motion-y","motion-z","gm",
    "compcor1","compcor2","compcor3","compcor4","compcor5"]
DENSITIES = [.05,.075,.1,.15,.2]
KS = [248,371,495,742,990]
ABSOLUTES = [.2,.3,.4]
CONFIGURATIONS = [("proportional",d,k) for d,k in zip(DENSITIES,KS)] + [
    ("absolute",c,None) for c in ABSOLUTES]
SHAPE = (61,73,61)
AFFINE = np.array([[-3,0,0,90],[0,3,0,-126],[0,0,3,-72],[0,0,0,1]],float)
UPPER = np.triu_indices(100,1)
PAIR_COUNT = 4950
GRAPH_FIELDS = ["participant","scheme","parameter","n_nodes","n_possible_edges",
    "k_requested","correlation_cutoff","n_at_cutoff","n_edges","realized_density",
    "n_negative_edges","n_zero_edges","n_components","n_connected_pairs",
    "n_disconnected_pairs","minimum_selected_correlation","global_efficiency"]
EFFICIENCY_FIELDS = ["participant","n_densities","global_efficiency",
    "mean_signed_correlation","mean_positive_part_correlation"]


class PreserveExistingEvidence(ValueError):
    """An existing artifact is not an input to overwrite or silently reuse."""


def prepare_output_directories(output, private):
    for path in (output,private):
        if any(p.is_symlink() for p in (path,*path.parents)):
            raise PreserveExistingEvidence("Preserve symlink in output/evidence path")
        if path.exists() and (not path.is_dir() or any(path.iterdir())):
            raise PreserveExistingEvidence("Output/private directories must be new or empty; preserve existing evidence")
    if output.resolve()==private.resolve() or output.resolve() in private.resolve().parents or private.resolve() in output.resolve().parents:
        raise PreserveExistingEvidence("Public and private output directories must be separate")
    output.mkdir(parents=True,exist_ok=True)
    private.mkdir(parents=True,exist_ok=True)


def finite(array, name):
    array = np.asarray(array,dtype=np.float64)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"Nonfinite {name}")
    return array


def write_json(path, data):
    Path(path).write_text(json.dumps(data,indent=2,allow_nan=False)+"\n")


def write_csv(path, fields, rows):
    with Path(path).open("w",newline="") as stream:
        writer = csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def resolve_stager_path(module_path=None, build_path=Path("/opt/source/stage_data.py")):
    module_path = Path(__file__ if module_path is None else module_path)
    local = module_path.resolve().parents[1]/"environment"/"stage_data.py"
    for candidate in (local,Path(build_path)):
        if candidate.is_file() and not candidate.is_symlink():
            return candidate
    raise ValueError("Offline source-verification helper missing")


def load_contract_and_sources(source_dir, method_path):
    method_path = Path(method_path)
    if method_path.is_symlink() or not method_path.is_file():
        raise ValueError("Method contract is not a regular file")
    content = method_path.read_bytes()
    if hashlib.sha256(content).hexdigest() != METHOD_SHA256:
        raise ValueError("Frozen method contract checksum mismatch")
    spec = importlib.util.spec_from_file_location("netinteg_source_stager",resolve_stager_path())
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = module.verify_staged(source_dir)
    if hashlib.sha256((Path(source_dir)/"source_manifest.json").read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("Frozen source manifest checksum mismatch")
    return json.loads(content),manifest


def resample_atlas(atlas, affine, target_shape=SHAPE, target_affine=AFFINE):
    atlas = finite(atlas,"atlas labels")
    if atlas.ndim != 3 or not np.array_equal(atlas,np.floor(atlas)):
        raise ValueError("Atlas labels must be a three-dimensional integer image")
    if not np.array_equal(np.unique(atlas),np.arange(101)):
        raise ValueError("Original atlas must contain background and every ROI 1..100")
    transform = np.linalg.inv(finite(affine,"atlas affine")) @ target_affine
    result = affine_transform(atlas.astype(np.int16),transform[:3,:3],
        offset=transform[:3,3],output_shape=target_shape,order=0,
        mode="constant",cval=0,prefilter=False)
    counts = np.bincount(result.ravel(order="C"),minlength=101)[1:]
    if len(counts) != 100 or np.any(counts == 0):
        raise ValueError("All 100 original ROIs must survive target-grid resampling")
    return result,counts


def load_atlas(root, manifest):
    images = [r for r in manifest["files"] if r["role"] == "atlas_image"]
    luts = [r for r in manifest["files"] if r["role"] == "atlas_labels"]
    if len(images) != 1 or len(luts) != 1:
        raise ValueError("Exactly one original atlas image and label table required")
    image_record,lut_record = images[0],luts[0]
    image = nib.load(root/image_record["path"])
    original = image.get_fdata(dtype=np.float64)
    labels = {}
    for line in (root/lut_record["path"]).read_text().splitlines():
        columns = line.split()
        if len(columns) != 6:
            raise ValueError("Unexpected original atlas label-table structure")
        roi = int(columns[0])
        if roi in labels:
            raise ValueError("Duplicate original ROI ID")
        labels[roi] = columns[1]
    if set(labels) != set(range(1,101)):
        raise ValueError("Original ROI label identity is incomplete")
    resampled,counts = resample_atlas(original,image.affine)
    observed = dict(image_path=image_record["path"],label_table_path=lut_record["path"],
        source_shape=list(image.shape),source_affine=image.affine.tolist(),
        storage_dtype=str(image.get_data_dtype()),intensity_slope=float(image.dataobj.slope),
        intensity_intercept=float(image.dataobj.inter),
        spatial_units=image.header.get_xyzt_units()[0],temporal_units=image.header.get_xyzt_units()[1],
        source_label_ids=np.unique(original).astype(int).tolist(),target_shape=list(SHAPE),
        target_affine=AFFINE.tolist(),parcels=[dict(roi_id=i,label=labels[i],
        n_voxels=int(counts[i-1])) for i in range(1,101)])
    return resampled,observed


def read_confounds(path, n_frames):
    with Path(path).open(newline="") as stream:
        reader = csv.DictReader(stream,delimiter="\t")
        if reader.fieldnames != CONFOUNDS:
            raise ValueError("Supplied confound names/order differ from public contract")
        rows = list(reader)
    if len(rows) != n_frames or any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError("Confounds must have exactly one complete row per source frame")
    return finite([[float(row[col]) for col in CONFOUNDS] for row in rows],"confounds")


def clean_and_correlate(raw, confounds):
    raw,confounds = finite(raw,"raw parcel signals"),finite(confounds,"confounds")
    if (raw.ndim != 2 or confounds.ndim != 2 or len(raw) != len(confounds)
            or len(raw)<2 or raw.shape[1]!=100 or confounds.shape[1]!=17):
        raise ValueError("Signal/confound dimensions invalid")
    t = len(raw)
    if np.any(np.all(raw == raw[0],axis=0)):
        raise ValueError("Exactly constant source parcel")
    constant = np.all(confounds == confounds[0],axis=0)
    retained = confounds[:,~constant].copy()
    retained -= retained.mean(axis=0)
    scale = np.sqrt(np.sum(retained**2,axis=0)/t)
    if np.any(scale <= 0) or not np.all(np.isfinite(scale)):
        raise ValueError("Nonconstant confounds require positive finite scale")
    retained /= scale
    centered = raw-raw.mean(axis=0)
    if retained.shape[1]:
        u,singular,_ = np.linalg.svd(retained,full_matrices=False)
        threshold = max(retained.shape)*np.finfo(np.float64).eps*singular[0]
        rank = int(np.sum(singular > threshold))
        basis = u[:,:rank]
        residual = centered-basis@(basis.T@centered)
    else:
        threshold,rank = 0.0,0
        singular,basis = np.empty(0),np.empty((t,0))
        residual = centered.copy()
    residual -= residual.mean(axis=0)
    norm = np.linalg.norm(residual,axis=0)
    original_norm = np.linalg.norm(centered,axis=0)
    zero_bound = 10*max(t,retained.shape[1])*np.finfo(np.float64).eps*np.maximum(
        original_norm,np.finfo(np.float64).tiny)
    if np.any(norm <= zero_bound) or np.any(original_norm == 0) or not np.all(np.isfinite(norm)):
        raise ValueError("Numerically constant residual parcel under the public roundoff bound")
    z = residual/(norm/np.sqrt(t-1))
    correlations = (z.T@z)/(t-1)
    weights = finite(correlations[UPPER],"empirical Pearson correlations")
    if np.any(np.abs(weights)>1+1e-12):
        raise ValueError("Pearson arithmetic outside mathematical bounds")
    correlations[UPPER] = weights
    correlations[(UPPER[1],UPPER[0])] = weights
    np.fill_diagonal(correlations,1)
    info = dict(constant_confound_columns=[n for n,c in zip(CONFOUNDS,constant) if c],
        retained_confound_columns=[n for n,c in zip(CONFOUNDS,constant) if not c],
        confound_rank=rank,confound_rank_threshold=float(threshold))
    evidence = dict(raw=raw,confounds=confounds,standardized_confounds=retained,
        singular_values=singular,nuisance_basis=basis,cleaned=z,correlations=correlations,
        residual_norm=norm,residual_zero_bound=zero_bound)
    return weights,info,evidence


def graph_measurements(weights, scheme, parameter, k):
    weights = finite(weights,"graph input")
    if weights.shape != (PAIR_COUNT,):
        raise ValueError("Expected all 4950 original ROI pairs")
    cutoff = float(np.partition(weights,PAIR_COUNT-k)[PAIR_COUNT-k]) if k is not None else parameter
    selected = weights >= cutoff
    adjacency = np.zeros((100,100),dtype=bool)
    adjacency[UPPER] = selected
    adjacency[(UPPER[1],UPPER[0])] = selected
    distances = shortest_path(adjacency,directed=False,unweighted=True)[UPPER]
    hops = distances[np.isfinite(distances)].astype(int)
    histogram = np.bincount(hops,minlength=100)
    exact = sum((Fraction(int(histogram[d]),d) for d in range(1,100)),Fraction(0))/PAIR_COUNT
    n_edges = int(selected.sum())
    row = dict(scheme=scheme,parameter=parameter,n_nodes=100,n_possible_edges=PAIR_COUNT,
        k_requested=k,correlation_cutoff=cutoff,n_at_cutoff=int(np.sum(weights==cutoff)),
        n_edges=n_edges,realized_density=n_edges/PAIR_COUNT,
        n_negative_edges=int(np.sum(selected & (weights<0))),
        n_zero_edges=int(np.sum(selected & (weights==0))),
        n_components=int(connected_components(adjacency,directed=False,return_labels=False)),
        n_connected_pairs=len(hops),n_disconnected_pairs=PAIR_COUNT-len(hops),
        minimum_selected_correlation=float(np.min(weights[selected])) if n_edges else None,
        global_efficiency=float(exact))
    return row,exact,adjacency,histogram


def average_ranks(values):
    ordered = sorted(range(len(values)),key=lambda i:values[i])
    ranks = np.empty(len(values),dtype=float)
    pos = 0
    while pos < len(ordered):
        end = pos+1
        while end < len(ordered) and values[ordered[end]] == values[ordered[pos]]:
            end += 1
        ranks[ordered[pos:end]] = (pos+1+end)/2
        pos = end
    return ranks


def correlation_record(left, right, spearman=False):
    n = len(left)
    if n != len(right) or n == 0:
        raise ValueError("Correlation requires aligned nonempty participant vectors")
    if all(x==left[0] for x in left) or all(x==right[0] for x in right):
        return dict(value=None,status="undefined_constant",n_participants=n)
    def centered(values):
        if all(isinstance(v,Fraction) for v in values):
            mean = sum(values,Fraction(0))/len(values)
            return finite([v-mean for v in values],"exact-centered graph scores")
        array = finite(values,"diagnostic values")
        return array-array.mean()
    if spearman:
        x,y = average_ranks(left),average_ranks(right)
        x,y = x-x.mean(),y-y.mean()
    else:
        x,y = centered(left),centered(right)
    value = float(np.dot(x,y)/(np.linalg.norm(x)*np.linalg.norm(y)))
    if not np.isfinite(value) or abs(value)>1+1e-12:
        raise ValueError("Correlation diagnostic outside mathematical range")
    return dict(value=max(-1.0,min(1.0,value)),status="ok",n_participants=n)


def rank_summary(participants, scores):
    ordered = sorted(range(len(participants)),key=lambda i:scores[i],reverse=True)
    threshold = scores[ordered[min(8,len(ordered))-1]]
    return ([participants[i] for i in ordered],
        [participants[i] for i in ordered if scores[i]>=threshold])


def make_rankings(participants, primary, configurations, signed, positive, densities, status):
    ranking,top = rank_summary(participants,primary)
    records = []
    for (scheme,parameter,_),scores,density in zip(CONFIGURATIONS,configurations,densities):
        order,subset = rank_summary(participants,scores)
        records.append(dict(scheme=scheme,parameter=parameter,ranking_by_efficiency=order,
            top_by_efficiency=subset,top_set_overlap_with_primary=len(set(subset)&set(top)),
            correlations=dict(efficiency_vs_mean_signed_correlation=correlation_record(scores,signed),
                efficiency_vs_mean_positive_part_correlation=correlation_record(scores,positive),
                realized_density_vs_mean_signed_correlation=correlation_record(density,signed),
                realized_density_vs_mean_positive_part_correlation=correlation_record(density,positive),
                spearman_vs_primary=correlation_record(scores,primary,True))))
    return dict(status=status,task_id=TASK_ID,pipeline_id=PIPELINE_ID,
        n_participants=len(participants),n_rois=100,n_configurations=8,top_k=8,
        ranking_by_efficiency=ranking,top_by_efficiency=top,
        primary_correlations=dict(efficiency_vs_mean_signed_correlation=correlation_record(primary,signed),
            efficiency_vs_mean_positive_part_correlation=correlation_record(primary,positive)),
        configuration_rankings=records,density_pairwise_spearman=[dict(density_low=DENSITIES[i],
            density_high=DENSITIES[j],spearman=correlation_record(configurations[i],configurations[j],True))
            for i in range(5) for j in range(i+1,5)])


def run(source_dir, method_path, output_dir, private_dir, pilot=False):
    root,output,private = Path(source_dir),Path(output_dir),Path(private_dir)
    prepare_output_directories(output,private)
    method,manifest = load_contract_and_sources(root,method_path)
    atlas,atlas_observed = load_atlas(root,manifest)
    np.save(private/"resampled_atlas.npy",atlas,allow_pickle=False)
    flat_labels = atlas.ravel(order="C")
    selections = [np.flatnonzero(flat_labels == i) for i in range(1,101)]
    records = {(r.get("participant"),r["role"]):r for r in manifest["files"]}
    participants = PARTICIPANTS[:1] if pilot else PARTICIPANTS
    observed,graph_rows,efficiency_rows = [],[],[]
    configurations,densities = [[] for _ in CONFIGURATIONS],[[] for _ in CONFIGURATIONS]
    primary,signed,positive = [],[],[]
    with (output/"connectomes.csv").open("w",newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["participant","roi_i","roi_j","correlation"])
        for participant in participants:
            bold_record,confound_record = records[participant,"bold"],records[participant,"confounds"]
            image = nib.load(root/bold_record["path"])
            if len(image.shape)!=4 or image.shape[:3]!=SHAPE or not np.array_equal(image.affine,AFFINE):
                raise ValueError("Original BOLD grid does not match the declared source grid")
            if image.header.get_xyzt_units() != ("mm","sec"):
                raise ValueError("Original spatial/temporal units do not match the public contract")
            data = finite(image.get_fdata(dtype=np.float64),"source BOLD")
            n_frames = data.shape[-1]
            flattened = data.reshape((-1,n_frames),order="C")
            raw = np.column_stack([flattened[index].mean(axis=0,dtype=np.float64) for index in selections])
            del data,flattened
            confounds = read_confounds(root/confound_record["path"],n_frames)
            weights,info,evidence = clean_and_correlate(raw,confounds)
            for i,j,value in zip(*UPPER,weights):
                writer.writerow([participant,int(i+1),int(j+1),float(value)])
            local_scores,adjacencies,histograms = [],[],[]
            for index,(scheme,parameter,k) in enumerate(CONFIGURATIONS):
                row,score,adjacency,histogram = graph_measurements(weights,scheme,parameter,k)
                row["participant"] = participant
                graph_rows.append(row)
                configurations[index].append(score)
                densities[index].append(Fraction(row["n_edges"],PAIR_COUNT))
                local_scores.append(score)
                adjacencies.append(adjacency)
                histograms.append(histogram)
            mean_score = sum(local_scores[:5],Fraction(0))/5
            mean_signed = float(weights.mean())
            mean_positive = float(np.maximum(weights,0).mean())
            primary.append(mean_score)
            signed.append(mean_signed)
            positive.append(mean_positive)
            efficiency_rows.append(dict(participant=participant,n_densities=5,global_efficiency=float(mean_score),
                mean_signed_correlation=mean_signed,mean_positive_part_correlation=mean_positive))
            observed.append(dict(participant=participant,bold_path=bold_record["path"],
                confounds_path=confound_record["path"],bold_shape=list(image.shape),affine=image.affine.tolist(),
                voxel_sizes_mm=[float(v) for v in image.header.get_zooms()[:3]],
                tr_s=float(image.header.get_zooms()[3]),n_frames=n_frames,n_confounds=len(CONFOUNDS),
                confound_columns=CONFOUNDS,storage_dtype=str(image.get_data_dtype()),
                intensity_slope=float(image.dataobj.slope),intensity_intercept=float(image.dataobj.inter),
                spatial_units="mm",temporal_units="sec",all_inputs_finite=True,
                all_residual_parcels_nonconstant=True,**info))
            np.savez_compressed(private/f"participant_{participant}.npz",**evidence,
                adjacency=np.array(adjacencies),path_histogram=np.array(histograms))
            write_json(private/f"participant_{participant}_exact_scores.json",dict(
                graph_scores=[str(s) for s in local_scores],primary_score=str(mean_score)))
            print(json.dumps(dict(participant=participant,n_frames=n_frames,confound_rank=info["confound_rank"],
                global_efficiency=float(mean_score))),flush=True)
    status = "resource_pilot" if pilot else "ok"
    write_csv(output/"graph_metrics.csv",GRAPH_FIELDS,graph_rows)
    write_csv(output/"efficiency.csv",EFFICIENCY_FIELDS,efficiency_rows)
    rankings = make_rankings(participants,primary,configurations,signed,positive,densities,status)
    write_json(output/"ranking.json",rankings)
    write_json(output/"run_metadata.json",dict(status=status,task_id=TASK_ID,pipeline_id=PIPELINE_ID,
        source_manifest_sha256=SOURCE_SHA256,method_contract_sha256=METHOD_SHA256,
        source_sha256={r["path"]:r["sha256"] for r in manifest["files"]},method_contract=method,
        source_observed=dict(atlas=atlas_observed,participants=observed),
        software_versions=dict(python=platform.python_version(),numpy=np.__version__,
            scipy=scipy.__version__,nibabel=nib.__version__)))
    (output/"findings.md").write_text(
        "# Cortical graph-method sensitivity control\n\n"
        f"Analyzed {len(participants)} released participants, one run each, with all 100 cortical parcels. "
        f"The primary efficiency spans {min(map(float,primary)):.6f} to "
        f"{max(map(float,primary)):.6f}, with equal-participant mean "
        f"{float(sum(primary,Fraction(0))/len(primary)):.6f}. "
        "The public endpoint is a five-density arithmetic mean of binary shortest-path efficiency, "
        "not an integral, neural information flow or intrinsic brain integration. "
        "The supplied nuisance set includes global signal and a linear trend. "
        "No additional filtering, smoothing or frame exclusion was applied; inherited preprocessing "
        "is incompletely documented. All original frames and signed correlations were retained.\n\n"
        "The three absolute thresholds are required parallel sensitivity descriptors. Realized "
        "density, components, cutoff ties and selected nonpositive edges are in graph_metrics.csv. "
        "The full rankings and tie-aware correlations are in ranking.json. No sign, magnitude, "
        "top-set change or superiority of proportional thresholding was assumed. These are "
        "same-person dependent comparisons, not a clinical group contrast or causal bias-removal test.\n\n"
        "This released 40-person/Schaefer100 recipe is a paper-derived method adaptation, not "
        "the cited papers' cohorts or numerical findings. ADHD source terms limit use to "
        "noncommercial research; public redistribution is not cleared by this analysis.\n")
    with (output/"findings.md").open("a") as stream:
        stream.write("\nMeasured absolute-threshold sensitivities relative to the primary ranking:\n\n")
        for record in rankings["configuration_rankings"]:
            if record["scheme"] != "absolute":
                continue
            descriptor = record["correlations"]["spearman_vs_primary"]
            value = f"{descriptor['value']:.6f}" if descriptor["status"]=="ok" else descriptor["status"]
            stream.write(f"- Cutoff {record['parameter']}: Spearman {value}; "
                f"inclusive top-set overlap {record['top_set_overlap_with_primary']} people.\n")
    return rankings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir",type=Path,default=Path("/app/data/netinteg"))
    parser.add_argument("--method-contract",type=Path,default=Path("/app/method_contract.json"))
    parser.add_argument("--output-dir",type=Path,default=Path("/app/output"))
    parser.add_argument("--private-dir",type=Path,default=Path("/app/oracle_private"))
    parser.add_argument("--pilot",action="store_true")
    args = parser.parse_args()
    try:
        run(args.source_dir,args.method_contract,args.output_dir,args.private_dir,args.pilot)
    except Exception as error:
        if isinstance(error,PreserveExistingEvidence):
            raise
        args.output_dir.mkdir(parents=True,exist_ok=True)
        write_json(args.output_dir/"run_metadata.json",dict(status="failed_precondition",task_id=TASK_ID,
            pipeline_id=PIPELINE_ID,reason=f"{type(error).__name__}: {error}"))
        write_csv(args.output_dir/"efficiency.csv",EFFICIENCY_FIELDS,[])
        (args.output_dir/"findings.md").write_text(f"Analysis failed before a valid complete result: {error}\n")
        raise


if __name__ == "__main__":
    main()
