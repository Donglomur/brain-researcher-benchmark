"""Operator-only complete Findlay table census. No import-time native dependency.

Inputs are authenticated, privately extracted complete tables. This module does
not download, fit models, select cohorts, or expose contrast checks to an actor.
The caller supplies the exact accepted ledgers and a bounded output/read budget.
"""
from __future__ import annotations

import hashlib
import io
import math
import os
from pathlib import Path
import stat
import struct
import zlib


TABLES = (
    "AeryJones_sgfg_medians_by_epoch_type.pqt", "condition_contrasts.pqt",
    "condition_measures.pqt", "cortical_spindle_condition_measures.pqt",
    "cortical_spindle_state_rates.pqt", "dspk_state_rates.pqt", "firing_rates.pqt",
    "multicortical_condition_contrasts.pqt", "multicortical_condition_measures.pqt",
    "off_durations.pqt", "rec_rem_vs_ewk_tdr.pqt", "ripple_frequency_by_state.pqt",
    "sleep_period_fractional_occupancy.pqt",
)
SMALL = {"condition_measures.pqt", "condition_contrasts.pqt",
         "multicortical_condition_measures.pqt", "multicortical_condition_contrasts.pqt"}
IDENTITIES = {"subject", "experiment", "condition", "state", "region", "acronym",
              "probe", "spw_probe", "cluster_id", "petersen_cell_type", "day",
              "Subject", "Experiment", "ROI", "Epoch.Type"}
HEX = frozenset("0123456789abcdef")


class CensusError(ValueError):
    pass


def _sha(value):
    return isinstance(value, str) and len(value) == 64 and set(value) <= HEX


def _identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _absolute_unlinked(path):
    path = Path(path)
    if not path.is_absolute() or path != path.resolve(strict=True):
        raise CensusError("input path must be absolute, existing, and canonical")
    for part in (path, *path.parents):
        if stat.S_ISLNK(part.lstat().st_mode):
            raise CensusError("linked input path")
    return path


class AccountedFile(io.RawIOBase):
    """Stable regular-file reads; every requested existing byte is charged.

    A short read on the immutable regular file is an integrity failure. Seeking
    is free; repeated footer/native reads are charged again. No mmap is exposed.
    """
    def __init__(self, path, expected_bytes, budget):
        super().__init__()
        self.path = _absolute_unlinked(path)
        self.budget = budget
        self.budget.check()
        fd = os.open(self.path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        self._file = os.fdopen(fd, "rb", buffering=0)
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_size != expected_bytes:
            self._file.close()
            raise CensusError("input is not the exact single-link regular member")
        self.initial = _identity(st)
        self.size = st.st_size
        self.read_bytes = 0

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self._file.tell()
    def seek(self, offset, whence=os.SEEK_SET):
        self.budget.check()
        return self._file.seek(offset, whence)

    def read(self, size=-1):
        self.budget.check()
        remaining = max(0, self.size - self.tell())
        amount = remaining if size is None or size < 0 else min(size, remaining)
        if amount:
            self.budget.charge_read(amount)
        body = self._file.read(amount)
        self.read_bytes += amount
        if len(body) != amount:
            raise CensusError("short immutable input read")
        return body

    def readinto(self, buffer):
        data = self.read(len(buffer))
        buffer[:len(data)] = data
        return len(data)

    def verify_stable(self):
        if _identity(os.fstat(self._file.fileno())) != self.initial:
            raise CensusError("input changed during census")
        if _identity(self.path.stat()) != self.initial:
            raise CensusError("input path replaced during census")

    def close(self):
        if not self.closed:
            try:
                self.verify_stable()
            finally:
                self._file.close()
                super().close()


def authenticate(reader, member):
    digest = hashlib.sha256()
    crc = 0
    while reader.tell() < reader.size:
        chunk = reader.read(min(65536, reader.size - reader.tell()))
        digest.update(chunk)
        crc = zlib.crc32(chunk, crc)
    if digest.hexdigest() != member["sha256"]:
        raise CensusError("extracted member SHA-256 mismatch")
    if f"{crc:08x}" != member["zip_crc32"]:
        raise CensusError("extracted member ZIP CRC mismatch")
    if reader.size < 12:
        raise CensusError("short Parquet member")
    reader.seek(0)
    if reader.read(4) != b"PAR1":
        raise CensusError("Parquet header mismatch")
    reader.seek(-8, os.SEEK_END)
    trailer = reader.read(8)
    length = struct.unpack("<I", trailer[:4])[0]
    if trailer[4:] != b"PAR1" or not 0 < length <= min(262144, reader.size - 12):
        raise CensusError("invalid or oversized Parquet footer")
    reader.seek(-(8 + length), os.SEEK_END)
    footer = reader.read(length)
    if hashlib.sha256(footer).hexdigest() != member["footer_sha256"]:
        raise CensusError("Parquet footer mismatch")
    reader.seek(0)
    return {"bytes": reader.size, "sha256": digest.hexdigest(),
            "zip_crc32": f"{crc:08x}", "footer_bytes": length,
            "footer_sha256": member["footer_sha256"]}


def _key(value):
    if value is None: return ("null", "")
    if isinstance(value, bool): return ("bool", str(value))
    if isinstance(value, int): return ("integer", str(value))
    if isinstance(value, float):
        if math.isnan(value): return ("nan", "")
        if math.isinf(value): return ("infinity", str(value))
        return ("float", value.hex())
    if isinstance(value, str):
        if len(value.encode("utf-8")) > 65536:
            raise CensusError("identity/category value exceeds explicit bound")
        return ("string", value)
    return ("unsupported", type(value).__name__)


class Column:
    def __init__(self):
        self.counts = dict(null=0, nan=0, positive_infinity=0, negative_infinity=0,
                           finite_numeric=0, zero=0, negative=0, boolean=0, string=0,
                           unsupported=0)
        self.minimum = None
        self.maximum = None
        self.categories = {}
        self.unsupported_types = {}

    def observe(self, value):
        c = self.counts
        if value is None: c["null"] += 1
        elif isinstance(value, bool):
            c["boolean"] += 1
            self._category(_key(value))
        elif isinstance(value, (int, float)):
            if isinstance(value, float) and not math.isfinite(value):
                c["nan" if math.isnan(value) else
                  "positive_infinity" if value > 0 else "negative_infinity"] += 1
            else:
                c["finite_numeric"] += 1
                c["zero"] += value == 0
                c["negative"] += value < 0
                self.minimum = value if self.minimum is None else min(self.minimum, value)
                self.maximum = value if self.maximum is None else max(self.maximum, value)
        elif isinstance(value, str):
            c["string"] += 1
            self._category(_key(value))
        else:
            c["unsupported"] += 1
            name = type(value).__name__
            self.unsupported_types[name] = self.unsupported_types.get(name, 0) + 1

    def _category(self, key):
        if key not in self.categories and len(self.categories) >= 100000:
            raise CensusError("complete category census exceeds explicit bound")
        self.categories[key] = self.categories.get(key, 0) + 1

    def finish(self):
        return {**self.counts, "finite_min": self.minimum, "finite_max": self.maximum,
                "categories": [{"type": k[0], "value": k[1], "rows": n}
                               for k, n in sorted(self.categories.items())],
                "unsupported_types": self.unsupported_types}


def _default_parquet(reader):
    import pyarrow as pa
    import pyarrow.parquet as pq
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    return pq.ParquetFile(reader, memory_map=False, buffer_size=0, pre_buffer=False,
                          arrow_extensions_enabled=False, page_checksum_verification=True,
                          thrift_string_size_limit=1048576, thrift_container_size_limit=100000)


def _table_census(root, member, budget, factory, accumulators):
    name = member["path"]
    gates = []
    retained = []
    with AccountedFile(root / name, member["bytes"], budget) as reader:
        auth = authenticate(reader, member)
        parquet = factory(reader)
        schema = parquet.schema_arrow
        names = list(schema.names)
        if len(set(names)) != len(names):
            raise CensusError("duplicate schema columns cannot be censused losslessly")
        if names != member["columns"]:
            raise CensusError("decoded column order differs from pinned schema")
        meta = parquet.metadata
        if meta.num_rows != member["footer_advertised_rows"]:
            raise CensusError("decoded metadata row count differs from pinned footer")
        if meta.num_row_groups != member["row_groups"]:
            raise CensusError("decoded metadata row-group count differs from pinned footer")
        columns = {n: Column() for n in names}
        identity_names = [n for n in names if n in IDENTITIES]
        groups = {}
        subjects = set()
        sessions = set()
        nrows = 0
        for batch in parquet.iter_batches(batch_size=4096, use_threads=False):
            budget.check()
            if not 0 <= batch.num_rows <= 4096:
                raise CensusError("batch bound violated")
            rows = batch.to_pylist()
            if len(rows) != batch.num_rows:
                raise CensusError("batch conversion row count mismatch")
            for row in rows:
                if nrows % 1024 == 0: budget.check()
                if set(row) != set(names):
                    raise CensusError("row/schema keys mismatch")
                for n, value in row.items(): columns[n].observe(value)
                subject = row.get("subject", row.get("Subject"))
                experiment = row.get("experiment", row.get("Experiment"))
                if subject is not None: subjects.add(_key(subject))
                if subject is not None and experiment is not None:
                    sessions.add((_key(subject), _key(experiment)))
                key = tuple(_key(row[n]) for n in identity_names)
                if key not in groups and len(groups) >= 100000:
                    raise CensusError("complete group census exceeds explicit bound")
                groups[key] = groups.get(key, 0) + 1
                for acc in accumulators: acc.observe(name, row, row_index=nrows)
                if name in SMALL:
                    if len(retained) >= 4096:
                        raise CensusError("small-table reconstruction bound exceeded")
                    retained.append(dict(row))
                nrows += 1
        if nrows != meta.num_rows or nrows != member["footer_advertised_rows"]:
            raise CensusError("decoded stream row count differs from pinned footer")
        stats = {n: c.finish() for n, c in columns.items()}
        if any(c["unsupported"] for c in stats.values()):
            gates.append("unsupported_decoded_column_values")
        reader.verify_stable()
        report = {"table": name, "authentication": auth,
                  "rows": nrows, "row_groups": meta.num_row_groups,
                  "schema": [{"name": field.name, "type": str(field.type),
                              "nullable": field.nullable} for field in schema],
                  "columns": stats, "identity_columns": identity_names,
                  "groups": [[list(key), count] for key, count in sorted(groups.items())],
                  "group_encoding": "[ordered [[type,value],...], row_count]; identity_columns gives order",
                  "subjects": sorted(subjects), "sessions": sorted(sessions),
                  "group_rows_total": sum(groups.values()),
                  "managed_read_bytes": reader.read_bytes,
                  "readiness_gates": gates, "all_decoded_rows_accounted": True}
    return report, retained


def reconcile_contrasts(measures, contrasts, keys, definitions):
    """Exact, no-fit difference reconciliation; no rounding tolerance is invented.

    definitions maps exported column to (source measure, minuend, subtrahend).
    Duplicate keys and nonfinite/missing values remain explicit unmatched cells.
    A nonzero difference is reported, never silently rounded into agreement.
    """
    source = {}
    target_keys = {}
    invalid_source_rows = []
    def valid_identity(row):
        # Source exporter _is_spw_probe creates a Boolean flag, not a probe ID.
        return all((type(row.get(k)) is bool if k == "spw_probe" else
                    ((isinstance(row.get(k), str) and bool(row[k])) or
                     (type(row.get(k)) in (int, float) and math.isfinite(row[k]))))
                   for k in keys)
    for i, row in enumerate(measures):
        if not valid_identity(row):
            invalid_source_rows.append(i)
            continue
        key = tuple(_key(row.get(k)) for k in keys) + (_key(row.get("condition")),)
        source.setdefault(key, []).append((i, row))
    for i, row in enumerate(contrasts):
        key = tuple(_key(row.get(k)) for k in keys)
        target_keys.setdefault(key, []).append(i)
    cells = []
    for i, row in enumerate(contrasts):
        base = tuple(_key(row.get(k)) for k in keys)
        for column in row:
            if column in keys: continue
            result = {"target_row": i, "column": column}
            if not valid_identity(row):
                result["status"] = "missing_or_invalid_target_identity"
            elif column not in definitions:
                result["status"] = "unresolved_source_definition"
            elif len(target_keys[base]) != 1:
                result["status"] = "duplicate_target_key"
            else:
                measure, plus, minus = definitions[column]
                a = source.get(base + (_key(plus),), [])
                b = source.get(base + (_key(minus),), [])
                result["source_rows"] = {"minuend": [n for n, _ in a],
                                         "subtrahend": [n for n, _ in b]}
                if len(a) != 1 or len(b) != 1:
                    result["status"] = "missing_or_duplicate_source_condition"
                else:
                    values = (a[0][1].get(measure), b[0][1].get(measure), row[column])
                    if not all(type(v) in (int, float) and math.isfinite(v) for v in values):
                        result["status"] = "missing_or_nonfinite_value"
                    else:
                        computed = values[0] - values[1]
                        if not math.isfinite(computed):
                            result["status"] = "nonfinite_difference"
                        else:
                            delta = computed - values[2]
                            result.update(reconstructed=computed, stored=values[2],
                                          absolute_difference=abs(delta) if math.isfinite(delta) else None,
                                          status="exact_match" if computed == values[2] else "numeric_mismatch")
            cells.append(result)
    statuses = {}
    for cell in cells: statuses[cell["status"]] = statuses.get(cell["status"], 0) + 1
    return {"keys": list(keys), "source_rows": len(measures), "target_rows": len(contrasts),
            "definitions": {k: list(v) for k, v in sorted(definitions.items())},
            "comparison": "exact finite stored-value difference; no fit or tolerance search",
            "source_duplicate_keys": sum(len(v) > 1 for v in source.values()),
            "invalid_source_identity_rows": invalid_source_rows,
            "target_duplicate_keys": sum(len(v) > 1 for v in target_keys.values()),
            "cells": cells, "status_counts": statuses,
            "all_target_cells_reconciled": bool(cells) and not invalid_source_rows and set(statuses) == {"exact_match"}}


def census(root_path, input_ledger, family_ledger, budget, *, parquet_factory=None,
           rules_module=None):
    """Write complete private receipts and return their small manifest.

    The parent must pass the exact accepted ledger objects, with measured SHA-256
    values joined from its authenticated extraction receipt. No body is accepted
    with the original not-yet-measured null hash. Explicit gates are not readiness.
    """
    budget.check()
    root = _absolute_unlinked(root_path)
    if not root.is_dir(): raise CensusError("input root is not a directory")
    members = [m for m in input_ledger["members"] if m["path"].endswith(".pqt")]
    if len(members) != 13 or {m["path"] for m in members} != set(TABLES):
        raise CensusError("complete exact 13-table ledger required")
    for m in members:
        if not _sha(m.get("sha256")) or not _sha(m.get("footer_sha256")):
            raise CensusError("complete measured member/footer SHA-256 required")
        if type(m.get("bytes")) is not int or not 12 <= m["bytes"] <= 3000000:
            raise CensusError("invalid bounded member size")
    if rules_module is None:
        from . import family_rules as rules_module
    book = rules_module.build_rules(family_ledger, input_ledger)
    if len(book.ids) != 98 or len(set(book.ids)) != 98:
        raise CensusError("complete unique 98-family rule book required")
    accumulators = {id_: book.new_accumulator(id_) for id_ in book.ids}
    table_accumulators = {table: [accumulators[id_] for id_ in book.ids
                                 if table in book.tables_for(id_)] for table in TABLES}
    tables = []
    retained = {}
    gates = []
    total_rows = 0
    expected_sessions = {(r["subject"], p) for r in input_ledger["static_source_roster"]
                         for p in r["protocols"]}
    protocol_aliases = {"NOD": "NOD", "Novelty": "NOD", "COW": "COW",
                        "Locomotion": "COW", "CTN": "CTN", "Dual": "CTN"}
    for member in sorted(members, key=lambda m: m["path"]):
        report, rows = _table_census(root, member, budget, parquet_factory or _default_parquet,
                                     table_accumulators[member["path"]])
        observed = {(s[1], protocol_aliases.get(p[1], p[1])) for s, p in report["sessions"]
                    if s[0] == p[0] == "string"}
        report["static_roster_comparison"] = {
            "protocol_aliases": protocol_aliases,
            "expected_sessions": len(expected_sessions), "observed_sessions": len(observed),
            "missing_from_this_table": sorted(expected_sessions - observed),
            "unexpected_in_this_table": sorted(observed - expected_sessions),
            "interpretation": "Complete table-specific difference; no universal exclusion or fabricated experiment for tables without it"}
        groups = report.pop("groups")
        report["group_parts"] = [budget.write_json(
            "groups-" + member["path"] + f"-{i // 2048:03d}.private.json",
            {"table": member["path"], "first_group": i, "groups": groups[i:i + 2048]})
            for i in range(0, len(groups), 2048)]
        report["group_count"] = len(groups)
        tables.append(budget.write_json("table-" + member["path"] + ".private.json", report))
        total_rows += report["rows"]
        gates.extend({"scope": member["path"], "gate": gate} for gate in report["readiness_gates"])
        if member["path"] in SMALL: retained[member["path"]] = rows
    family_reports = []
    for id_ in book.ids:
        budget.check()
        family_reports.append({"id": id_, "schema_assessment": book.assess_schema(id_),
                               "support": accumulators[id_].finish()})
    families = budget.write_json("family-support-98.private.json", {
        "families": family_reports, "families_accounted": 98,
        "scope": "Complete eligibility/support census, no statistical fits or inferential results"})
    # The inspected exporter linkage is unresolved. Empty definitions preserve
    # every cell as unresolved; neither an R sign nor a Python token is guessed.
    definitions = getattr(rules_module, "EXPORTED_CONTRAST_DEFINITIONS", {})
    contrast_reports = []
    for prefix, keys in (("condition", ("subject", "experiment")),
                         ("multicortical_condition", ("subject", "experiment", "acronym", "spw_probe", "region"))):
        result = reconcile_contrasts(retained[prefix + "_measures.pqt"],
                                     retained[prefix + "_contrasts.pqt"], keys,
                                     definitions.get(prefix, {}))
        contrast_reports.append(budget.write_json(prefix + "-reconstruction.private.json", result))
        if not result["all_target_cells_reconciled"]:
            gates.append({"scope": prefix, "gate": "contrast_reconstruction_not_fully_reconciled"})
    # These are semantic/source limits, not a prediction of actual data defects.
    gates.extend({"scope": "published_support", "gate": gate} for gate in (
        "29_static_sessions_vs_endpoint_specific_23_28_requires_actual_family_join",
        "68_regional_contrast_rows_vs_64_caption_requires_actual_family_join",
        "SGFG_factor_alias_design_matrix_reconciliation_before_fit",
        "stored_normalized_measure_scale_not_assumed_percent"))
    result = {"schema": "findlay-complete-intake-census/v1",
              "status": "COMPLETE_INTAKE_CENSUS_WITH_GATES",
              "table_count": 13, "family_count": 98, "decoded_rows": total_rows,
              "table_reports": tables, "family_report": families,
              "contrast_reports": contrast_reports, "readiness_gates": gates,
              "scientific_ready": False, "models_fitted": 0,
              "all_tables_and_families_accounted": True,
              "numeric_and_identity_outputs": "operator-only; not candidate input"}
    return result
