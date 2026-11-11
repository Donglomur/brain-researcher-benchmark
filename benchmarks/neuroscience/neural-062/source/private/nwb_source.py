"""Narrow Allen Visual Behavior NWB source boundary, usable by062/063.

No whole-recording neural read, filtering, fitting, or event analysis here.
The caller owns its endpoint. Only metadata columns/timestamps are decoded;
the neural function returns a live dataset for bounded caller-selected slices.
"""
from contextlib import contextmanager
import hashlib
import os
import stat


def signature(s):
    return (s.st_dev, s.st_ino, s.st_size, s.st_nlink, s.st_mtime_ns, s.st_ctime_ns)


@contextmanager
def opened_source(path, binding):
    """Exact provider hash on held FD; body error survives every cleanup tail."""
    import delivery_io as io
    stream=None;fd=None;f=None;before=None;first=None
    try:
        size=binding.get("bytes")
        if type(size)is not int or size<=0:raise ValueError("Exact future byte binding absent")
        expected=binding["blake2b_512"]
        if type(expected)is not str or len(expected)!=128:raise ValueError("Provider BLAKE2b512 required")
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        stream=os.fdopen(fd,"rb");fd=None;before=os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode)or before.st_nlink!=1 or before.st_size!=size:raise ValueError("Original source type/size")
        io.reserve("read_bytes",size+1);digest=hashlib.blake2b();remaining=size
        while remaining:
            block=stream.read(min(8*1024*1024,remaining))
            if not block:raise ValueError("Truncated original source")
            digest.update(block);remaining-=len(block)
        if stream.read(1)or digest.hexdigest()!=expected or signature(before)!=signature(os.fstat(stream.fileno())):raise ValueError("Original hash/identity")
        stream.seek(0)
        import h5py
        f=h5py.File(stream,"r");yield f
    except BaseException as error:
        first=error;io.retain(error,"native_source_body")
    finally:
        operations=[]
        if f is not None:operations.append(("hdf5_close",f.close))
        if stream is not None and before is not None:
            def check():
                if signature(before)!=signature(os.fstat(stream.fileno())):raise ValueError("Source changed during projection")
            operations.append(("source_revalidation",check))
        if stream is not None:operations.append(("source_stream_close",stream.close))
        elif fd is not None:operations.append(("source_fd_close",lambda:os.close(fd)))
        for name,operation in operations:
            try:operation()
            except BaseException as error:
                if first is None:first=error
                io.retain(error,name)
    if first is not None:raise first


def internal(f, path):
    import h5py
    import numpy as np
    obj = f
    for part in path.strip("/").split("/"):
        if not isinstance(obj, h5py.Group) or not isinstance(obj.get(part, getlink=True), h5py.HardLink):
            raise ValueError("Missing, soft or external NWB source link")
        obj = obj[part]
    if isinstance(obj, h5py.Dataset) and (obj.is_virtual or obj.external):
        raise ValueError("Virtual or external NWB dataset forbidden")
    return obj


def vector(f, path, length=None, kind=None, cap=2_000_000):
    import h5py
    import numpy as np
    ds = internal(f, path)
    if not isinstance(ds, h5py.Dataset) or ds.ndim != 1 or len(ds) > cap or (length is not None and len(ds) != length):
        raise ValueError("Invalid bounded metadata-vector shape")
    if kind is not None and ds.dtype.kind not in kind:
        raise ValueError("Unexpected source metadata dtype")
    return ds[:]


def neural(f, row):
    import h5py
    import numpy as np
    prefix = "processing/ophys/dff/traces/"
    table_path = "processing/ophys/image_segmentation/cell_specimen_table"
    ds = internal(f, prefix + "data")
    if not isinstance(ds, h5py.Dataset) or ds.ndim != 2 or ds.dtype.kind != "f" or not 0 < ds.shape[0] <= 2_000_000 or not 0 < ds.shape[1] <= 20_000:
        raise ValueError("Unsupported time×ROI dF/F source shape")
    if ds.attrs.get("unit") not in ("NA", b"NA"):
        raise ValueError("Expected source-declared arbitrary dF/F unit NA")
    if float(ds.attrs.get("conversion", 1)) != 1 or float(ds.attrs.get("offset", 0)) != 0:
        raise ValueError("Unqualified dF/F conversion/offset")
    ts = vector(f, prefix + "timestamps", ds.shape[0], "f")
    if internal(f, prefix + "timestamps").attrs.get("unit") not in ("seconds", b"seconds"):
        raise ValueError("Native imaging clock must declare seconds")
    if not np.isfinite(ts).all() or np.any(np.diff(ts) <= 0):
        raise ValueError("Invalid full native imaging clock")
    region_ds = internal(f, prefix + "rois")
    if region_ds.attrs.get("neurodata_type") not in ("DynamicTableRegion", b"DynamicTableRegion"):
        raise ValueError("Expected explicit ROI DynamicTableRegion")
    region = vector(f, prefix + "rois", ds.shape[1], "iu", 20_000)
    table = internal(f, table_path)
    ref = region_ds.attrs.get("table")
    if ref is None or not ref or f[ref].id != table.id:
        raise ValueError("DynamicTableRegion does not reference exact ROI table")
    roi_id = vector(f, table_path + "/id", kind="iu", cap=20_000)
    specimen_id = vector(f, table_path + "/cell_specimen_id", len(roi_id), "iuf", 20_000)
    valid = vector(f, table_path + "/valid_roi", len(roi_id), "b", 20_000)
    if len(set(roi_id.tolist())) != len(roi_id) or np.any(region < 0) or np.any(region >= len(roi_id)) or len(set(region.tolist())) != len(region):
        raise ValueError("Ambiguous ROI region/identity mapping")
    mapped = {int(roi_id[r]): (i, r) for i, r in enumerate(region)}
    expected = {int(r["cell_roi_id"]): int(r["cell_specimen_id"]) for r in row["rois"]}
    actual_valid = {int(roi_id[r]) for r in region if valid[r]}
    if not expected or set(expected) != actual_valid:
        raise ValueError("Published valid ROI census differs from NWB")
    cols = []
    for roi, csid in sorted(expected.items()):
        col, index = mapped[roi]
        value = specimen_id[index]
        if not np.isfinite(value) or value != csid:
            raise ValueError("Published cell lineage→ROI join differs from NWB")
        cols.append(col)
    return ds, ts, np.asarray(cols, dtype=np.int64)


def presentations(f):
    import h5py
    import numpy as np
    """Image tables only; excludes movie/spontaneous/trials and future outcomes."""
    root = internal(f, "intervals")
    result = []
    fields = {"id", "start_time", "image_name", "omitted"}
    for name in sorted(root.keys()):
        group = internal(f, "intervals/" + name)
        if not isinstance(group, h5py.Group) or not fields <= set(group.keys()):
            continue
        base = "intervals/" + name + "/"
        ids = vector(f, base + "id", kind="iu", cap=200_000)
        starts = vector(f, base + "start_time", len(ids), "f", 200_000)
        omitted = vector(f, base + "omitted", len(ids), "bif", 200_000)
        ds = internal(f, base + "image_name")
        if ds.ndim != 1 or len(ds) != len(ids) or h5py.check_string_dtype(ds.dtype) is None:
            raise ValueError("Expected native image-name strings")
        names = ds.asstr()[:].tolist()
        if any(not isinstance(n, str) or len(n.encode()) > 512 for n in names):
            raise ValueError("Invalid image-name strings")
        result.append({"group": name, "ids": ids, "starts": starts, "omitted": omitted, "image_names": names})
    if not result:
        raise ValueError("No native image/omission presentation table")
    return result
