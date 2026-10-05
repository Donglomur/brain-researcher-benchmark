"""Manufactured geometry/reduction/safety fixtures, not original-source evidence."""
import os
from pathlib import Path
import numpy as np
import pytest
import nibabel as nib
import build_reference as b
import proof_of_work as p
import qc_contract as q
from fixture_support import fixture_reference, emit


def test_sphere_boundary_equal_weights_and_overlap():
    affine=np.eye(4); transform=np.eye(4)
    offsets,ijk,rows=b.sphere_geometry(np.array([[0,0,0],[1,0,0]]),affine,(7,2,2),transform)
    first=set(map(tuple,ijk[offsets[0]:offsets[1]]))
    second=set(map(tuple,ijk[offsets[1]:offsets[2]]))
    assert (5,0,0) in first and (6,0,0) not in first
    assert first & second and rows[0]["boundary_min_abs_mm2"] == 0
    assert np.array_equal(ijk[:offsets[1]],np.array(sorted(first)))


def test_physical_world_transform_not_index_sphere():
    affine=np.diag([3.,3.,3.,1.]); transform=np.eye(4); transform[0,3]=3
    offsets,ijk,rows=b.sphere_geometry([[0,0,0]],affine,(5,2,2),transform,radius=1)
    assert np.array_equal(ijk,[[1,0,0]])
    assert rows[0]["world_x_mm"] == 3


def test_no_nearest_voxel_rescue():
    with pytest.raises(AssertionError,match="empty"):
        b.sphere_geometry([[100,100,100]],np.eye(4),(2,2,2),np.eye(4))


def test_roi_mean_source_peak_not_peak_of_means():
    values=np.array([[[[100.,-100.]]],[[[-100.,100.]]]],dtype=np.float32)
    image=nib.Nifti1Image(values,np.eye(4))
    means,peaks=b.source_means(image,np.array([0,2]),np.array([[0,0,0],[1,0,0]]))
    assert np.array_equal(means,np.zeros((2,1)))
    assert peaks.tolist()==[100.]


def test_source_nonfinite_outside_spheres_fails():
    values=np.ones((2,2,2,3)); values[1,1,1,1]=np.nan
    with pytest.raises(AssertionError,match="nonfinite original"):
        b.source_means(nib.Nifti1Image(values,np.eye(4)),np.array([0,1]),np.array([[0,0,0]]))


@pytest.mark.parametrize("placement", ["inside_source","same_as_source","source_parent","same_target","nested_targets"])
def test_destination_scope(tmp_path,placement):
    source=tmp_path/"originals"; source.mkdir(); (source/"kept.txt").write_text("immutable")
    out=tmp_path/"out.npz"; report=tmp_path/"report.json"
    if placement=="inside_source":out=source/"out.npz"
    elif placement=="same_as_source":out=source
    elif placement=="source_parent":out=tmp_path
    elif placement=="same_target":report=out
    elif placement=="nested_targets":report=out/"report.json"
    with pytest.raises(AssertionError):b.destinations(source,out,report)
    assert (source/"kept.txt").read_text()=="immutable"


@pytest.mark.parametrize("kind", ["existing", "symlink", "dangling", "ancestor", "fifo"])
def test_destination_no_overwrite_or_symlinks(tmp_path,kind):
    source=tmp_path/"source"; source.mkdir(); out=tmp_path/"out.npz"
    if kind=="existing":out.write_text("keep")
    elif kind=="symlink":out.symlink_to(source)
    elif kind=="dangling":out.symlink_to(tmp_path/"absent")
    elif kind=="ancestor":
        folder=tmp_path/"link"; folder.symlink_to(source); out=folder/"out.npz"
    elif kind=="fifo":os.mkfifo(out)
    with pytest.raises(AssertionError):b.destinations(source,out,tmp_path/"report.json")


def test_bank_write_exclusive(tmp_path):
    ref=fixture_reference(); out=tmp_path/"toy-bank.npz"
    b.write_bank(out,ref,pilot=True); original=out.read_bytes()
    with pytest.raises(FileExistsError):b.write_bank(out,ref,pilot=True)
    assert out.read_bytes()==original
    with np.load(out,allow_pickle=False) as z:
        assert str(z["bank_schema"])=="precisfc-resource-pilot-v2"
        assert "ref_roi_means" in z.files


@pytest.mark.parametrize("n,expected", [(0,False),(272,False),(273,True),(818,True)])
def test_qc_exact_integer_boundary(n,expected):
    ref=fixture_reference(frames=818,rois=2)
    ref["tmask"][:]=False; ref["tmask"][:,:n]=True
    out=q.derive(ref)
    assert all(r["duration_qc_pass"] is expected for r in out["session_qc"])
    assert out["reliability"][0]["qc_pass"] is expected


def test_geometry_metadata_rounding_within_public_tolerance(tmp_path):
    import json
    ref=fixture_reference();emit(tmp_path,ref)
    path=tmp_path/"run_metadata.json";meta=json.loads(path.read_text())
    meta["source_observed"]["headers"][0]["sform"][0][0] += 5e-10
    path.write_text(json.dumps(meta));p.validate_output_directory(tmp_path,ref)


def test_exact_timing_metadata_not_relaxed(tmp_path):
    import json
    ref=fixture_reference();emit(tmp_path,ref)
    path=tmp_path/"run_metadata.json";meta=json.loads(path.read_text())
    meta["source_observed"]["headers"][0]["raw_header_tr_seconds"] += 5e-10
    path.write_text(json.dumps(meta))
    with pytest.raises(AssertionError):p.validate_output_directory(tmp_path,ref)


def test_offline_python3_entrypoint():
    path=Path(__file__).with_name("test.sh");text=path.read_text()
    assert "python3 -m pytest" in text
    assert all(x not in text for x in ("pip install","curl ","apt-get","uvx"))
    assert text.index("printf '0")<text.index("python3")
    assert os.access(path,os.X_OK)


@pytest.mark.parametrize("extra", ["empty_directory", "file", "fifo", "symlink"])
def test_closed_source_inventory(tmp_path,extra):
    (tmp_path/"source_manifest.json").write_text("{}")
    (tmp_path/"data").mkdir(); (tmp_path/"data"/"source").write_text("original")
    records=[{"path":"data/source"}]
    b.validate_inventory(tmp_path,records)
    if extra=="empty_directory":(tmp_path/"unexpected").mkdir()
    elif extra=="file":(tmp_path/"unexpected").write_text("x")
    elif extra=="fifo":os.mkfifo(tmp_path/"unexpected")
    else:(tmp_path/"unexpected").symlink_to(tmp_path/"data")
    with pytest.raises(AssertionError):b.validate_inventory(tmp_path,records)


@pytest.mark.parametrize("mode", ["output_dotdot", "source_dotdot", "equivalent_targets"])
def test_lexical_dotdot_cannot_bypass_source_overlap(tmp_path,mode):
    source=tmp_path/"source";source.mkdir();(tmp_path/"other").mkdir()
    output=tmp_path/"out.npz";report=tmp_path/"report.json"
    if mode=="output_dotdot":output=tmp_path/"other"/".."/"source"/"out.npz"
    elif mode=="source_dotdot":source=tmp_path/"other"/".."/"source";output=tmp_path/"source"/"out.npz"
    else:report=tmp_path/"other"/".."/"out.npz"
    with pytest.raises(AssertionError):b.destinations(source,output,report)


def test_benign_dotdot_resolves_after_symlink_checks(tmp_path):
    source=tmp_path/"source";source.mkdir();(tmp_path/"other").mkdir()
    outputs=b.destinations(source,tmp_path/"other"/".."/"out.npz",tmp_path/"report.json")
    assert outputs[0]==tmp_path/"out.npz"
