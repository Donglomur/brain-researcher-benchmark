"""Prepare the existing exposed Purkinje inputs from authenticated public sources.

No download, tree analysis, reference access, R execution, or participant run.
The CLI has no option to replace the release or the existing output identities.
"""
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
import zipfile


HERE = Path(__file__).resolve().parent
PROFILE = HERE.parent / "registered-runtime" / "program-v1"
ARCHIVE = {"bytes": 4754064, "sha256": "5ad4cb8980203d9b5625bcd830d1a66c81fd1d3eba0d01d932c4e68fc4b8c2bb"}
RMD = {"bytes": 229916, "sha256": "11c93d06905fad525342e02564fc7f520b1bd798a13856c0bbfbf4ac618d42fd"}
PAPER = {"bytes": 622639, "sha256": "93f95bf289d228cabbbe6a98083c2831d074bd81848911a372977702425500e8"}
INPUT_PINS = {"bytes": 1991, "sha256": "3478e8bfbfdf7e6ba865f37ac9562427290f9cc770f9b780c6d192a53af4d6fe"}
RMD_URL = "https://zenodo.org/api/records/15066697/files/HumanvsMousePaperAnalysis.Rmd/content"
PREFIX = "Dendrite reconstructions/"
STEMS = ("H13 Poly 1", "H13 Split 1", "H13 Split 3", "H14 Poly 2",
         "Mse Normative 1", "Mse Normative 2", "Mse Poly 1", "Mse Split 1",
         "Mse Split 2", "T6051 Poly 1")
SNIPPETS = (("length_formula", 187, 191),
            ("radius_to_diameter_declaration", 303, 319),
            ("later_reload_without_diameter_conversion", 483, 489),
            ("retained_section_loop", 851, 879),
            ("thin_length_ratio", 1091, 1102))
INTERPRETATION = ("The radius-to-diameter declaration precedes a reload without conversion. "
                  "Both explicit conventions are evaluated; historical author runtime is unresolved.")
SHOLL_HEADER = ("START-RADIUS END-RADIUS DEND-LENGTH DEND-VOLUME DEND-SA BRANCH-POINTS "
                "SPINE-COUNT STUBBY-COUNT THIN-COUNT MUSHROOM-COUNT OTHER-COUNT").split()


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def encode(value):
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()


def ordinary_path(path):
    path = Path(os.path.abspath(path))
    need(not any(p.is_symlink() for p in (path, *path.parents)), "symlink path")
    return path


def capture(path, expected):
    """Bounded immutable capture; authenticate before parsing any payload."""
    path = ordinary_path(path)
    before = path.lstat()
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size,
                       s.st_mtime_ns, s.st_ctime_ns)
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
         before.st_size == expected["bytes"], "ordinary exact source extent")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        need(stamp(before) == stamp(os.fstat(fd)), "source changed before capture")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            body = stream.read(expected["bytes"] + 1)
        need(stamp(before) == stamp(os.fstat(fd)) == stamp(path.lstat()), "source changed during capture")
        need(pin(body) == expected, "source identity mismatch")
        return body
    finally:
        os.close(fd)


def swc_name(stem):
    # Preserve the actual anomalous release filename, not a guessed replacement.
    return stem + (" Reconstructionswc.swc" if stem == "H13 Split 1" else " Reconstruction.swc")


def selected_members(archive):
    """Read exact members in memory; never extract paths supplied by the archive."""
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        infos = z.infolist()
        need(len(infos) <= 128 and sum(i.file_size for i in infos) <= 16 * 1024**2,
             "archive member/expanded-byte limit")
        names = [i.filename for i in infos]
        need(len(names) == len(set(names)), "duplicate ZIP member")
        for i in infos:
            name = i.filename.rstrip("/")
            p = PurePosixPath(name)
            need(name and str(p) == name and not p.is_absolute() and ".." not in p.parts
                 and "\\" not in name and "\x00" not in name, "unsafe ZIP member")
            mode = i.external_attr >> 16
            need(not stat.S_ISLNK(mode) and (stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR)),
                 "nonordinary ZIP member")
            need(not i.flag_bits & 1 and i.file_size <= 5 * 1024**2, "encrypted/oversized ZIP member")
        wanted = {PREFIX + swc_name(s) for s in STEMS} | {PREFIX + s + " sholl.txt" for s in STEMS}
        observed = {n for n in names if n.startswith(PREFIX) and n.endswith((".swc", "sholl.txt"))}
        need(observed == wanted, "complete exact ten-cell SWC and Sholl panel required")
        bodies = {name: z.read(name) for name in sorted(wanted)}
        need(all(bodies.values()), "empty selected archive member")
        return bodies


def sholl_total(body):
    """Expose the third-column author-export total in micrometres, as before."""
    lines = body.decode("utf-8").splitlines()
    need(lines and lines[0].split() == SHOLL_HEADER, "Sholl column semantics")
    lengths = []
    for line in lines[1:]:
        tokens = line.split("#", 1)[0].split()
        if not tokens:
            continue
        need(len(tokens) == len(SHOLL_HEADER) and all(len(t) <= 128 for t in tokens), "Sholl row shape")
        values = [float(t) for t in tokens]
        need(all(math.isfinite(v) for v in values) and values[2] >= 0, "finite nonnegative Sholl length")
        lengths.append(values[2])
    need(lengths, "empty Sholl export")
    total = math.fsum(lengths)
    need(math.isfinite(total) and total > 0, "positive finite author total")
    return total


def source_semantics(rmd):
    # splitlines matches the original numbered excerpts; no R evaluation.
    lines = rmd.decode("utf-8").splitlines()
    need(len(lines) >= 1102, "complete source excerpt ranges")
    snippets = [{"label": label, "line_start": start, "line_end": end,
                 "text": "\n".join(f"{i}: {lines[i-1]}" for i in range(start, end + 1))}
                for label, start, end in SNIPPETS]
    return encode({"url": RMD_URL, "sha256": RMD["sha256"], "numbered_snippets": snippets,
                   "interpretation_limit": INTERPRETATION})


def derive(archive, rmd, descriptors):
    """Pure preparation path, also exercised with generated ten-cell controls."""
    members = selected_members(archive)
    files = dict(descriptors)
    cells, totals = [], []
    for stem in STEMS:
        cid = stem.replace(" ", "_")
        species = "mouse" if stem.startswith("Mse") else "human"
        filename = "raw/" + cid + ".swc"
        files[filename] = members[PREFIX + swc_name(stem)]
        cells.append(dict(cell_id=cid, species=species,
                          specimen_label=stem.split()[0] if species == "human" else None,
                          mouse_individual_mapping="unavailable" if species == "mouse" else None,
                          file=filename, source_filename=swc_name(stem)))
        totals.append((cid, sholl_total(members[PREFIX + stem + " sholl.txt"])))
    files["cells.json"] = encode(cells)
    files["author_sholl_totals.csv"] = ("cell_id,author_sholl_length_um\n" +
                                      "".join(f"{c},{v:.12g}\n" for c, v in totals)).encode()
    files["source_semantics.json"] = source_semantics(rmd)
    return files


def verify_outputs(files, expected):
    need(set(files) == set(expected), "complete original input set")
    for name in sorted(expected):
        need(pin(files[name]) == expected[name], "prepared input identity mismatch: " + name)


def publish(files, destination):
    """No partial published packet; existing destinations are never overwritten."""
    destination = ordinary_path(destination)
    need(destination.parent.is_dir() and not destination.exists(), "fresh output with existing parent required")
    # The empty output is exclusively reserved before any write. On failure it
    # remains empty, while a temporary sibling is removed by TemporaryDirectory.
    destination.mkdir(mode=0o700)
    try:
        with tempfile.TemporaryDirectory(prefix=".purkinje-input-", dir=destination.parent) as tmp:
            staging = Path(tmp)
            for name, body in sorted(files.items()):
                target = staging / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(body)
            os.rename(staging, destination)
    except BaseException:
        if destination.is_dir() and not any(destination.iterdir()):
            destination.rmdir()
        raise


def prepare(archive_path, rmd_path, output, paper_path=None):
    expected = json.loads(capture(PROFILE / "INPUT_PINS.json", INPUT_PINS))
    archive, rmd = capture(archive_path, ARCHIVE), capture(rmd_path, RMD)
    descriptors = {n: capture(PROFILE / n, expected[n]) for n in ("TASK.md", "SCHEMA.json")}
    files = derive(archive, rmd, descriptors)
    verify_outputs(files, expected)
    files["HumanvsMousePaperAnalysis.Rmd"] = rmd
    if paper_path is not None:
        files["paper.html"] = capture(paper_path, PAPER)
    # Publish source/provenance, never computed morphology or hidden targets.
    publish(files, output)
    return {"schema": "purkinje-public-input-preparation/v1", "task_id": "PAPER-FIND-REP-013",
            "source_archive": ARCHIVE, "source_rmd": RMD, "original_input_pins": INPUT_PINS,
            "files": {n: pin(b) for n, b in sorted(files.items())},
            "original_inputs_exact": True, "paired_article_provisioned": paper_path is not None,
            "exposure": "public_development_including_answer_bearing_author_sholl_totals",
            "whole_paper_reproduction": False, "paper_improvement": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--rmd", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paper", type=Path, help="Optional exact historical article capture for A/B packets")
    args = parser.parse_args()
    result = prepare(args.archive, args.rmd, args.output, args.paper)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
