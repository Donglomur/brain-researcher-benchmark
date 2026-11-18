# NEURAL-039 Movie10 Stage A metadata operator

This component verifies five fixed metadata identities: the organizer README and
the four 137-byte Git-annex pointers at commit
`96750e7017b30cb02f011c11561a3df897695853`. It never fetches an HDF5 payload.
The pointers declare four original objects totaling 368,950,005 bytes.

The documented DataLad repository/path/annex-key route is a logical route.
Neither the README nor these pointers specifies a usable physical payload URL.
Even a successful run therefore returns
`metadata_verified_physical_transport_unresolved`, with
`physical_payload_transport_ready=false` and `b_c_admitted=false`.
No guessed mirror, README link traversal, DataLad execution or recursive search
is permitted. Redirects, retries and substitute endpoints are refused.

`REQUEST_POLICY.json` must equal the operator's exact typed policy. The CLI does
not expose the internal generated-test transport/request seam. Authentication
means comparison with retained source SHA256 and Git-blob identities; it does
not establish a payload SHA256, payload availability, data quality or a benchmark
result. The root-selected admission record is an operator control record, not a
cryptographic authorization system.

The production command requires Linux and a separately qualified outer
300-second SIGKILL supervisor. Before input reads, the operator installs and
reads back RLIMIT_AS=512 MiB and RLIMIT_FSIZE=64 KiB, then installs a 300-second
SIGALRM with the OS default fatal action. The outer supervisor must cover Python
startup through connection cleanup, output fsync and process exit. Its executable
identity and qualification are mandatory future admission inputs; they have not
been exercised by the generated controls. No actual metadata HTTP is admitted by
this package.

The byte counter measures received decrypted HTTP headers, framing and body.
Its 16 MiB bound excludes DNS, TLS records and link traffic. This is not a claim
of a measured whole-network byte ceiling. Each request also has an expected-body
extent plus one overflow byte and a 64 KiB header/framing allowance. Reads receive
the remaining absolute deadline; attempted requests and received bytes remain
charged on failure. TLS uses the Python default verified context. The transport
ignores HTTP proxy environment variables and supplies no authentication headers.

Output creation is exclusive, ordinary-file only, with no symlinked ancestor;
the result body is capped at 64 KiB. Failure does not retry or overwrite output.
A hard stop, write error or fsync error can leave an absent or incomplete result.
The outer controller must retain its termination receipt and account for that
attempt; an absent/partial JSON file is never metadata success. A trustworthy
operation directory must not be concurrently renamed or modified by another
writer; this is not an OS sandbox against a hostile local account.

These metadata checks preserve all four original subjects, all 1,000 native
parcel columns, repeated runs and the complete original key inventory. They do
not open or qualify those arrays. The 16-case Movie10 strict_v2 development panel
uses per-run [8,N-5), TR 1.49. It remains distinct from the full audiovisual task
and the organizer's hidden six-film OOD evaluation. No participant inference,
native neural understanding, scientific score or readiness promotion follows.

Generated controls run with `python3 -I -S -B test_stage_a.py`; stdlib only.
They use mocked transports, in-memory generated metadata and a single 8-byte
temporary ordinary-file fixture. The optional `NEURAL039_STAGEA_TEST_TMP` selects
an existing temporary directory for accounting; otherwise the resolved standard
temporary directory is used. Public CI needs no private evidence directory.
Run controls through the repository's admitted shared two-slot test pool.
