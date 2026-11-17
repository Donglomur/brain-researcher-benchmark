"""Commit complete T15 collection receipts before protected grading.

This source component runs the unchanged predecessor's collection admission and
grading. It neither launches scientific work nor supplies its own authority.
The caller must capture this source, the frozen producer closure and predecessor
adapter, and retain the returned seal pin in independent operator custody.
"""
from pathlib import Path


LEGACY_PIN = {
    "bytes": 12461,
    "sha256": "f95c06a40da332765197b30fb42fb8a7d3c38e21da794ed00bf4d1dd01f4f2f8",
}
SEAL_SCHEMA = "neural014-receipt-bound-collection-v1"
SEAL_CAP = 65536
HERE = Path(__file__).absolute().parent


def _modules(c, bodies, legacy_raw):
    c.need(type(legacy_raw) is bytes and c.pin(legacy_raw) == LEGACY_PIN,
           "exact unchanged completed-grading adapter source")
    legacy = c.module({"grade_completed.py": legacy_raw}, "grade_completed.py",
                      HERE.parent / "completed-collection-grading")
    root = legacy.PRODUCER_ROOT
    science = c.module(bodies, "program/science.py", root, c=c)
    packet = c.module(bodies, "program/packet.py", root, c=c, science=science)
    policy = c.module(bodies, "program/policy.py", root, c=c, packet=packet)
    outputs = c.module(bodies, "program/outputs.py", root, c=c, packet=packet,
                       policy=policy, science=science)
    return legacy, packet, policy, outputs


class _CapturedReads:
    """Record complete bytes already read by the original collection admission."""

    def __init__(self, c, read):
        self.c, self.read, self.pins = c, read, {}

    def __call__(self, path, cap, expected=None):
        key = str(self.c.path(path))
        raw = self.read(path, cap, expected)
        self.c.need(type(raw) is bytes and 0 < len(raw) <= cap,
                    "bounded captured collection bytes")
        actual = self.c.pin(raw)
        if expected is not None:
            self.c.need(actual == self.c.exact_pin(expected), "captured collection pin")
        if key in self.pins:
            self.c.need(self.pins[key] == actual, "collection changed during sealing")
        self.pins[key] = actual
        return raw

    def digest(self):
        # Paths are part of identity, so equal-content files cannot be swapped.
        rows = [dict(path=path, **self.pins[path]) for path in sorted(self.pins)]
        return self.c.pin(self.c.encoded(rows))


def _inspect(selection, external, legacy, packet, policy, outputs, c, bodies, read,
             private_gold=None):
    """Read all receipts/models/outputs; never read a source array or private gold."""
    legacy.descriptor(c, selection, 32768)
    legacy.descriptor(c, external, 8192)
    c.need(external["bytes"] == 8192, "unchanged complete outer observer slot")
    captured = _CapturedReads(c, read)
    if private_gold is not None:
        legacy.descriptor(c, private_gold, packet.JSON_CAP)
        gold_path = c.path(private_gold["path"])
        gold_pin = c.only_pin(private_gold)
        for item in (selection, external):
            c.need(gold_path != c.path(item["path"]) and gold_pin != c.only_pin(item),
                   "private target cannot alias collection metadata")
    s = policy.selection(c.parse(captured(selection["path"], 32768,
                                          c.only_pin(selection))), legacy.PRODUCER)
    root = c.path(s["output"])
    if private_gold is not None:
        c.need(not gold_path.is_relative_to(root)
               and not gold_path.is_relative_to(c.path(s["public_root"]))
               and gold_path != c.path(s["public_manifest"]["path"])
               and gold_pin != c.only_pin(s["public_manifest"]),
               "private target outside all collection reads")
    raw = captured(external["path"], 8192, c.only_pin(external))
    outer = c.parse(raw)
    c.need(outer.get("schema") == "neural014_complete_external_v1"
           and outer.get("status") == "complete_unqualified"
           and outer.get("source") == legacy.PRODUCER
           and outer.get("selection") == c.only_pin(selection)
           and outer.get("attempt") == str(root)
           and outer.get("grading_performed") is False
           and outer.get("scientific_qualified") is False,
           "source-bound unchanged external collection")
    complete_raw = captured(root / "COMPLETE.json", packet.JSON_CAP)
    complete = c.parse(complete_raw)
    worker = dict(schema="neural014-worker-result-v1", status="complete_unqualified",
                  source=legacy.PRODUCER, complete=c.pin(complete_raw),
                  phase_count=complete["phase_count"])
    joined = outputs.admit_collection(s, legacy.PRODUCER, bodies, worker, root, captured)
    c.need(c.encoded(joined) == c.encoded(outer["joined_collection"]),
           "unchanged original complete collection join")
    seal = dict(schema=SEAL_SCHEMA, producer_source=legacy.PRODUCER,
                legacy_adapter_source=LEGACY_PIN, selection=selection, external=external,
                collection_files=len(captured.pins), readset=captured.digest(),
                joined_collection=c.pin(c.encoded(joined)))
    encoded = c.encoded(seal)
    c.need(len(encoded) <= SEAL_CAP, "bounded collection commitment")
    return encoded, captured.pins, root, c.path(s["public_manifest"]["path"])


def seal_collection(selection, external, legacy_raw, c, bodies, read):
    """Return new seal bytes after a complete original collection readback.

    The independently trusted caller stores the bytes and their SHA-256 pin at
    closure time. Creating a seal later cannot prove the earlier receipt state.
    Sealing supplies neither grading permission nor authentic-runtime evidence.
    """
    legacy, packet, policy, outputs = _modules(c, bodies, legacy_raw)
    raw, _, _, _ = _inspect(selection, external, legacy, packet, policy, outputs,
                            c, bodies, read)
    return raw


def evaluate(request, seal_raw, seal_pin, legacy_raw, c, bodies, read):
    """Verify the trusted seal, then run the original protected grader unchanged.

    Every collection read in the grading pass is pinned to the verified state;
    a change between verification and grading therefore fails before gold. The
    same caller-owned reader charges both passes to one resource allowance.
    """
    c.need(type(seal_raw) is bytes and 0 < len(seal_raw) <= SEAL_CAP
           and c.pin(seal_raw) == c.exact_pin(seal_pin),
           "independently captured collection seal identity")
    legacy, packet, policy, outputs = _modules(c, bodies, legacy_raw)
    c.need(type(request) is dict and "private_gold" in request,
           "unchanged protected grading request required")
    actual, pins, root, public = _inspect(
        request["selection"], request["external"], legacy, packet, policy, outputs,
        c, bodies, read, private_gold=request["private_gold"])
    c.need(actual == seal_raw, "complete receipt commitment changed before grading")
    gold_path = c.path(request["private_gold"]["path"])
    gold_reads = 0

    def bound_read(path, cap, expected=None):
        nonlocal gold_reads
        key = str(c.path(path))
        protected = c.path(path).is_relative_to(root) or c.path(path) == public
        c.need(not protected or key in pins, "new unsealed collection read")
        frozen = pins.get(key)
        if frozen is not None:
            c.need(expected is None or expected == frozen, "replay selected an unsealed receipt")
        raw = read(path, cap, frozen if frozen is not None else expected)
        if frozen is not None:
            c.need(type(raw) is bytes and c.pin(raw) == frozen,
                   "collection changed during grading replay")
        if c.path(path) == gold_path:
            gold_reads += 1
        return raw

    result = legacy.evaluate(request, LEGACY_PIN, c, bodies, bound_read)
    c.need(gold_reads == 1, "one unchanged protected target capture")
    return dict(schema="neural014-receipt-bound-grade-v1", collection_seal=seal_pin,
                collection_files=len(pins), grade=result)
