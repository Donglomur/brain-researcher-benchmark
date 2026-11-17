"""Explicit invented engineering corpus; never satisfies production source identity.

The source constructor is separate. Actual Asset integrity, syntax decoding, CSV
grammar, window calibration and consumer mathematics are shared with production.
"""
import hashlib
import io
import json
from pathlib import Path
from types import MappingProxyType

from helsinki_intake import (Asset, Corpus, INFANTS, ANNOTATIONS, Refusal, require,
    canonical, decode_fixed_record_header, parse_recorded_grid_csv, derive_quality_flags)
from helsinki_profile import source_code_identity, PINS

FIXTURE_PROTOCOL_ID = "helsinki_recorded_grid_quality_flags_v2.synthetic_fixture_v1"
FIXTURE_COORDINATE_ID = "synthetic_record_sample_grid_v1"
FIXTURE_DURATIONS = MappingProxyType({i: (31 if i == 1 else 30) for i in INFANTS})


def fixture_identity(manifest_sha256):
    value = {"schema": "helsinki_invented_fixture_profile_v1",
        "protocol_id": FIXTURE_PROTOCOL_ID, "coordinate_id": FIXTURE_COORDINATE_ID,
        "fixture_only": True, "fixture_manifest_sha256": manifest_sha256,
        "owner_source_module_sha256": dict(source_code_identity())}
    value["profile_sha256"] = hashlib.sha256(canonical(value)).hexdigest()
    return value


def fixture_support():
    return {"schema": "helsinki_complete_invented_fixture_support_v1", "fixture_only": True,
        "infants": 79, "experts": 3, "record_seconds": 2371, "primary_cases": 80,
        "annotation_data_records": 31, "annotation_header_records": 1,
        "invented_assets_authenticated": True, "authentic_neural_waveforms_authenticated": False,
        "all_three_invented_streams_validated": True}


def validate_fixture_lineage(lineage):
    require(type(lineage) is dict and set(lineage) == {
        "manifest_sha256", "assets", "headers", "durations", "profile", "support"},
        "incomplete_fixture_lineage")
    require(all(type(lineage[k]) is dict for k in ("assets", "headers", "durations", "profile", "support")),
        "fixture_lineage_container_types")
    pin = lineage["manifest_sha256"]
    require(type(pin) is str and len(pin) == 64 and set(pin) <= set("0123456789abcdef") and
        pin != PINS["release_manifest.json"], "fixture_cannot_claim_production_manifest")
    require(canonical(lineage["profile"]) == canonical(fixture_identity(pin)) and
        canonical(lineage["support"]) == canonical(fixture_support()), "fixture_profile_or_support_mismatch")
    require(set(lineage["assets"]) == {f"eeg{i}.edf" for i in INFANTS} | set(ANNOTATIONS) and
        set(lineage["headers"]) == set(map(str, INFANTS)), "fixture_asset_or_header_census")
    require(all(type(v) is str and len(v) == 64 and set(v) <= set("0123456789abcdef")
        for values in (lineage["assets"], lineage["headers"]) for v in values.values()), "fixture_source_sha_format")
    require(lineage["durations"] == {str(i): v for i, v in FIXTURE_DURATIONS.items()},
        "fixture_record_grid_changed")
    return lineage


class FixtureCorpus(Corpus):
    """All 82 invented files authenticated; source identity stays explicitly synthetic."""
    def __init__(self, root, manifest_path):
        raw = Path(manifest_path).read_bytes()
        self.manifest_sha256 = hashlib.sha256(raw).hexdigest()
        require(self.manifest_sha256 != PINS["release_manifest.json"], "production_manifest_is_not_fixture")
        manifest = json.loads(raw)
        require(type(manifest) is dict and set(manifest) == {"schema", "source_kind", "files"} and
            manifest["schema"] == "helsinki_invented_corpus_manifest_v1" and
            manifest["source_kind"] == "invented_fixture", "explicit_fixture_manifest_required")
        rows = manifest["files"]
        names = {r["name"] for r in rows}
        require(len(rows) == len(names) == 82 and
            names == {f"eeg{i}.edf" for i in INFANTS} | set(ANNOTATIONS), "fixture_full82_census")
        self.assets, self.headers, self.annotations = {}, {}, {}
        self._intake_complete = False
        self._window_cache, self._case_cache = {}, {}
        try:
            by_name = {r["name"]: r for r in rows}
            for row in rows:
                asset = Asset(root, row)
                self.assets[row["name"]] = asset
                require(asset.sha256 == row["sha256"], "invented_full_asset_sha_mismatch")
            for i in INFANTS:
                row = by_name[f"eeg{i}.edf"]
                require(set(row) == {"name", "bytes", "md5", "sha256", "header_sha256", "recorded_seconds", "marker"},
                    "invented_edf_manifest_fields")
                marker = "EDF+C" if i in (4, 29, 50) else ""
                require(row["marker"] == marker and row["recorded_seconds"] == FIXTURE_DURATIONS[i],
                    "invented_marker_or_duration_changed")
                asset = self.assets[row["name"]]
                header = decode_fixed_record_header(asset.handle, asset.size, marker)
                require(header.sha256 == row["header_sha256"] and header.records == FIXTURE_DURATIONS[i] and
                    len(header.channels) == 21 and len(header.electrode_indices) == 19,
                    "invented_header_identity_or_support")
                self.headers[i] = header
            streams = []
            for name in ANNOTATIONS:
                row = by_name[name]
                require(set(row) == {"name", "bytes", "md5", "sha256"}, "invented_csv_manifest_fields")
                asset = self.assets[name]
                asset.check_unchanged()
                asset.handle.seek(0)
                streams.append(parse_recorded_grid_csv(asset.handle, self.durations, 31))
                asset.check_unchanged()
            self.annotations = {i: tuple(zip(*(s[i] for s in streams))) for i in INFANTS}
            self._intake_complete = True
            self._original_lineage = canonical(self._current_lineage())
            validate_fixture_lineage(self.lineage())
        except BaseException:
            self.close()
            raise

    def _current_lineage(self):
        return {"manifest_sha256": self.manifest_sha256,
            "assets": {n: a.sha256 for n, a in sorted(self.assets.items())},
            "headers": {str(i): self.headers[i].sha256 for i in INFANTS},
            "durations": {str(i): self.durations[i] for i in INFANTS},
            "profile": fixture_identity(self.manifest_sha256), "support": fixture_support()}

    def lineage(self):
        require(self._intake_complete, "complete_invented_fixture_intake_required")
        for asset in self.assets.values():
            asset.check_unchanged()
        current = self._current_lineage()
        require(canonical(current) == self._original_lineage, "invented_fixture_lineage_mutated")
        return validate_fixture_lineage(current)

    def waveform(self, infant, second):
        require(type(second) is int and second in self.seconds(infant), "fixture_case_outside_support")
        self.assets[f"eeg{infant}.edf"].check_unchanged()
        key = (infant, second)
        if key not in self._window_cache:
            self._window_cache[key] = super().waveform(infant, second)
        return self._window_cache[key]

    def case_data(self, infant, second):
        signal = self.waveform(infant, second)
        key = (infant, second)
        if key not in self._case_cache:
            self._case_cache[key] = (signal, derive_quality_flags(signal))
        return self._case_cache[key]
