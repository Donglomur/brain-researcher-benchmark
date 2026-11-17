"""Exact adopted V3 record table and fixed source publication slots.
Old V2 definitions remain in the immutable predecessor. No packet value is authority.
"""
from .backend_native_v3_records import NATIVE_RECORDS as RECORDS, NATIVE_PRIMITIVES as PRIMITIVES
SITES = {'agent_completion': {'kind': 'AgentCompletion', 'path': 'worker/agent_completion_{ordinal}.json'}, 'artifact': {'kind': 'ArtifactObservation', 'path': 'worker/artifact_{role}.json'}, 'base': {'kind': 'BackendAttemptBase', 'path': 'worker/backend_attempt_base.json'}, 'closure': {'kind': 'BackendClosure', 'path': 'worker/backend_closure.json'}, 'environment': {'kind': 'EnvironmentObservation', 'path': 'worker/backend_environment.json'}, 'exchange': {'kind': 'BackendExchangeObservation', 'path': 'worker/backend_exchange_{ordinal}.json'}, 'exit': {'kind': 'ExitObservation', 'path': 'worker/backend_exit.json'}, 'http_completion': {'kind': 'ParsedCompletion', 'path': 'worker/http_completion_{ordinal}_parsed.json'}, 'http_health': {'kind': 'ParsedHealth', 'path': 'worker/http_health_{ordinal}_parsed.json'}, 'http_raw': {'kind': 'RawHttpResponse', 'path': 'worker/http_{endpoint}_{ordinal}_raw.json'}, 'http_rejected': {'kind': 'RejectedResponse', 'path': 'worker/http_{endpoint}_{ordinal}_rejected.json'}, 'http_request': {'kind': 'BackendHttpRequest', 'path': 'worker/http_{endpoint}_{ordinal}_request.json'}, 'http_slots': {'kind': 'ParsedSlots', 'path': 'worker/http_slots_{ordinal}_parsed.json'}, 'initialization': {'kind': 'BackendInitializationObservation', 'path': 'worker/backend_initialization.json'}, 'peer': {'kind': 'PeerCredentialObservation', 'path': 'worker/backend_peer.json'}, 'process': {'kind': 'ProcessObservation', 'path': 'worker/backend_process_{ordinal}.json'}, 'signal': {'kind': 'SignalObservation', 'path': 'worker/backend_signal.json'}, 'snapshot': {'kind': 'BackendAttempt', 'path': 'worker/backend_attempt_snapshot_{ordinal}.json'}, 'socket': {'kind': 'SocketObservation', 'path': 'worker/backend_socket.json'}, 'socket_closure': {'kind': 'SocketClosureObservation', 'path': 'worker/backend_socket_closure.json'}, 'source_initialization': {'kind': 'SourceInitializationProof', 'path': 'worker/backend_source_initialization.json'}, 'streams': {'kind': 'StreamClosureObservation', 'path': 'worker/backend_streams.json'}, 'subtree': {'kind': 'SubtreeObservation', 'path': 'worker/backend_subtree.json'}, 'rendered_template': {'kind': 'RenderedTemplateObservation', 'path': 'worker/rendered_template_{ordinal}.json', 'caller': 'backend_agent_entry.prepare_completion_request_v3', 'phase': 'C18R', 'ordinal': 'same actual PendingAgentStep / backend.requests next ordinal; no reused failed attempt', 'cutoff': 'original G, no renewed clock'}, 'completion_request': {'kind': 'CompletionRequest', 'path': 'worker/completion_request_{ordinal}.json', 'caller': 'backend_agent_entry.prepare_completion_request_v3', 'phase': 'C18R', 'ordinal': 'same actual PendingAgentStep / backend.requests next ordinal; no reused failed attempt', 'cutoff': 'original G, no renewed clock'}}
SITES['agent_input_product']={'kind':'AgentInputProductV1','path':'worker/agent_input_product_{ordinal}.json',
    'caller':'missing_actual_public_product_transcript_step_owner',
    'admission':'unavailable until genuine source-owned producer and H inverse exist'}
# One active immutable roster shared by H, worker and source control plan.
# Derive extents from the selected source schemas; no packet can supply them.
import re
from .common import need
BOOTSTRAP_KINDS = tuple(PRIMITIVES["BootstrapKind"]["values"])
BOOTSTRAP_ROOT_KIND = BOOTSTRAP_KINDS[-1]
BOOTSTRAP_ORDER = BOOTSTRAP_KINDS[:-1]
_ROOT_EXTENT = re.fullmatch(r"Pin\[([0-9]+):([0-9]+)\]",
                           RECORDS["NativeArtifactRootBundleV1"]["fields"]["roots"])
need(_ROOT_EXTENT is not None, "source-defined complete bootstrap root extent")
BOOTSTRAP_ROOT_MIN, BOOTSTRAP_ROOT_MAX = (int(x) for x in _ROOT_EXTENT.groups())
BOOTSTRAP_MIN_OBJECTS = len(BOOTSTRAP_ORDER) + BOOTSTRAP_ROOT_MIN
BOOTSTRAP_MAX_OBJECTS = len(BOOTSTRAP_ORDER) + BOOTSTRAP_ROOT_MAX
need(BOOTSTRAP_ROOT_KIND == "NativeRootObservationV1" and len(BOOTSTRAP_ORDER) == 16 and
     BOOTSTRAP_ROOT_MIN == 1 and BOOTSTRAP_ROOT_MAX == 5,
     "unchanged selected sixteen-kind and one-to-five-root ABI")
need(RECORDS["BootstrapObjectTableV1"]["fields"]["rows"] ==
     f"BootstrapObjectRowV1[{BOOTSTRAP_MIN_OBJECTS}:{BOOTSTRAP_MAX_OBJECTS}]",
     "active table extent equals the complete fixed prefix and root suffix")

def require_bootstrap_roster_v3(rows):
    """Pure metadata shape/order check; this never grants live ownership."""
    need(type(rows) is list and BOOTSTRAP_MIN_OBJECTS <= len(rows) <= BOOTSTRAP_MAX_OBJECTS,
         "complete fixed bootstrap prefix plus exactly one to five roots")
    need(all(type(row) is dict and type(row.get("ordinal")) is int for row in rows) and
         [row["ordinal"] for row in rows] == list(range(len(rows))),
         "exact original complete bootstrap ordinal sequence")
    fixed = len(BOOTSTRAP_ORDER)
    need(tuple(row.get("kind") for row in rows[:fixed]) == BOOTSTRAP_ORDER and
         all(row.get("kind") == BOOTSTRAP_ROOT_KIND for row in rows[fixed:]),
         "every active fixed kind and complete original root suffix")
    return rows
