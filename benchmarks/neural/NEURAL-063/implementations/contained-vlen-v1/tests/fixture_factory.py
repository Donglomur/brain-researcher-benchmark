"""Invented NEURAL-063 HDF5 fixtures; deferred libraries, no action on import.

This source is preparation only. A separately admitted generated qualification
may supply its authenticated h5py/NumPy modules. It is not an NWB downloader or
an alternative scientific reader. Every buffer write is charged before it is
performed; HDF5 and Python allocator memory still need kernel containment.
"""
import hashlib
import io
import os
from pathlib import Path
import stat

EXTENT_CAP = 131072
HDF_WRITE_CAP = 1048576
VARIANTS = ("mixed512", "ascii513", "unicode513", "consensus_mismatch", "zero_omissions")


class InventedBuffer(io.BytesIO):
    def __init__(self):
        super().__init__()
        self.requested_write_bytes = 0
        self.high_extent = 0

    def write(self, data):
        requested = len(data)
        self.requested_write_bytes += requested
        if self.requested_write_bytes > HDF_WRITE_CAP:
            raise ValueError("invented HDF write-request ceiling")
        end = self.tell() + requested
        if not 0 <= end <= EXTENT_CAP:
            raise ValueError("invented HDF extent ceiling")
        count = super().write(data)
        self.high_extent = max(self.high_extent, end)
        return count

    def seek(self, offset, whence=io.SEEK_SET):
        if whence == io.SEEK_SET:
            target = offset
        elif whence == io.SEEK_CUR:
            target = self.tell() + offset
        elif whence == io.SEEK_END:
            target = len(self.getbuffer()) + offset
        else:
            raise ValueError("invented seek origin")
        if not 0 <= target <= EXTENT_CAP:
            raise ValueError("invented seek ceiling")
        return super().seek(offset, whence)

    def truncate(self, size=None):
        target = self.tell() if size is None else size
        if not 0 <= target <= EXTENT_CAP:
            raise ValueError("invented truncate ceiling")
        return super().truncate(target)


def row(experiment):
    """Two invented complete-session members; never a production selection."""
    if experiment not in ("101", "102"):
        raise ValueError("two invented plane identities only")
    return {
        "ophys_experiment_id": experiment, "ophys_session_id": "501",
        "mouse_id": "1", "split": "fit",
        "rois": [{"cell_roi_id": "10", "cell_specimen_id": "100"}],
        "context": {"cre_line": "invented", "targeted_structure": "VISp",
                    "imaging_depth": 100, "image_set": "A", "passive": False,
                    "experience_level": "Familiar", "session_number": 1},
    }


def build(variant, *, h5py, numpy):
    """Return <=128 KiB invented bytes, with request counts; do not write disk.

    The real h5py reader must decode an actual UTF-8 VLEN dataset. This is not a
    fabricated layout dictionary. Native neural_metadata/presentations and the
    unchanged derive_session are the scientific comparison path. No production
    adapter admission is waived by this fixture factory.
    """
    if variant not in VARIANTS:
        raise ValueError("fixed invented fixture variant")
    names = ["a" * 512 if i % 2 == 0 else "é" * 256 for i in range(11)]
    if variant == "ascii513":
        names[0] = "a" * 513
    elif variant == "unicode513":
        names[0] = "é" * 256 + "x"
    elif variant == "consensus_mismatch":
        names[0] = "b" * 512
    buffer = InventedBuffer()
    with h5py.File(buffer, "w") as file:
        table = file.create_group("processing/ophys/image_segmentation/cell_specimen_table")
        table.create_dataset("id", data=numpy.array([10, 11, 12, 13], dtype="int64"))
        table.create_dataset("cell_specimen_id", data=numpy.array([100, 101, 102, 103], dtype="int64"))
        table.create_dataset("valid_roi", data=numpy.array([True, False, False, False], dtype="bool"))
        trace = file.create_group("processing/ophys/dff/traces")
        values = numpy.arange(161 * 4, dtype="float32").reshape(161, 4) / 100
        dataset = trace.create_dataset("data", data=values, chunks=(10, 2),
                                       compression="gzip", compression_opts=1)
        dataset.attrs["unit"] = "NA"
        times = trace.create_dataset("timestamps", data=numpy.arange(161, dtype="float64") / 20,
                                     chunks=(32,))
        times.attrs["unit"] = "seconds"
        rois = trace.create_dataset("rois", data=numpy.arange(4, dtype="int64"))
        rois.attrs["neurodata_type"] = "DynamicTableRegion"
        rois.attrs["table"] = table.ref
        table = file.create_group("intervals/presentation")
        table.create_dataset("id", data=numpy.arange(11, dtype="int64"))
        table.create_dataset("start_time", data=numpy.arange(11, dtype="float64") * .75)
        omitted = numpy.zeros(11, dtype="bool")
        if variant != "zero_omissions":
            omitted[[4, 8]] = True
        table.create_dataset("omitted", data=omitted)
        table.create_dataset("image_name", data=names, dtype=h5py.string_dtype("utf-8"))
    body = buffer.getvalue()
    if not 0 < len(body) <= EXTENT_CAP:
        raise ValueError("invented final extent")
    return body, {"variant": variant, "bytes": len(body),
                  "sha256": hashlib.sha256(body).hexdigest(),
                  "requested_hdf_write_bytes": buffer.requested_write_bytes,
                  "high_extent_bytes": buffer.high_extent,
                  "invented": True, "original_data_read": False}


def publish_once(path, body):
    """One exclusive fixture artifact; caller charges the full request first."""
    if not isinstance(body, bytes) or not 0 < len(body) <= EXTENT_CAP:
        raise ValueError("bounded immutable invented fixture body")
    path = Path(path)
    if (not path.is_absolute() or path.is_symlink()
            or any(p.is_symlink() for p in path.parents)
            or not path.parent.is_dir()):
        raise ValueError("ordinary selected fixture output")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        offset = 0
        while offset < len(body):
            count = os.write(fd, memoryview(body)[offset:offset + 65536])
            if count <= 0:
                raise OSError("incomplete invented fixture write")
            offset += count
        os.fsync(fd)
        os.fchmod(fd, 0o444)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != len(body):
            raise ValueError("invented fixture custody")
    finally:
        os.close(fd)
    return {"path": str(path), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
