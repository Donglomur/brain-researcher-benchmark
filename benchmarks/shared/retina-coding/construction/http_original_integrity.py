"""Join independently observed HTTP-original fingerprints to a complete receipt.

This pure helper reads no files and does not authenticate a supplied receipt.
A separate reviewer must hash each complete private header original and establish
receipt provenance before calling it. Matching allowlisted headers is insufficient.
"""
import re


def verify_http_original_bindings(receipt_rows, observed_headers, archive_names):
    """Bind every persisted HTTP record to the acquisition receipt, not only its allowlist."""
    if type(archive_names) not in (list, tuple) or len(archive_names) != 18 or len(set(archive_names)) != 18:
        raise ValueError("header_original_scope")
    names = set(archive_names)
    expected_names = {name + ".http.json" for name in names}
    if type(receipt_rows) is not list or type(observed_headers) is not list \
            or len(receipt_rows) != 18 or len(observed_headers) != 18:
        raise ValueError("header_original_missing_or_duplicate")
    observed = {}
    def valid_pin(pin):
        return type(pin) is dict and set(pin) == {"name", "bytes", "sha256"} \
            and type(pin["name"]) is str and pin["name"] in expected_names \
            and type(pin["bytes"]) is int and 0 < pin["bytes"] <= 262144 \
            and type(pin["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", pin["sha256"]) is not None
    for pin in observed_headers:
        if not valid_pin(pin) or pin["name"] in observed:
            raise ValueError("header_original_missing_or_duplicate")
        observed[pin["name"]] = pin
    seen = set()
    for row in receipt_rows:
        if type(row) is not dict or row.get("name") not in names or row["name"] in seen:
            raise ValueError("header_original_missing_or_duplicate")
        seen.add(row["name"])
        pin = row.get("http_original")
        if not valid_pin(pin) or pin["name"] != row["name"] + ".http.json" \
                or observed.get(pin["name"]) != pin:
            raise ValueError("header_original_binding")
    if seen != names or set(observed) != expected_names:
        raise ValueError("header_original_missing_or_duplicate")
    return True
