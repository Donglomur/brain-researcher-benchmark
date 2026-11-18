# Saved release metadata census

This operator-only component reconciles the exact declared 13 people × 51 endpoints
against an independently pinned, complete saved NeuroVault collection 6618
metadata snapshot. It does not read neural maps, predict values, select a
scientific population or issue support/custody credentials.

Every declared cell remains in the output. Fixed-effects (`ffx`) records are
candidate maps; AP and PA records are counted separately, with same-session
and same-run counts attached to each FFX candidate. Source run identifiers
(including RSVP-language runs 03/04/05) are preserved. Multiple FFX records stay ambiguous;
the census does not choose the first, average them, or count repeated sessions
as independent people. Missing FFX entries stay missing in this snapshot.
The recorded `is_valid` flag is retained without inferring numerical validity.
A missing exact identifier match is not proof that a differently named
semantic equivalent is absent. There is no heuristic contrast-name recovery.

The twelve explicit task aliases map catalogue spelling to source metadata
spelling. They are a reviewable naming join, not a cognitive-family or
contrast-dependency ontology. Source record names must agree with the separate
person/task fields. An unparseable relevant name fails the census instead of
making the corresponding case look absent.

Use `census.py --help` for the required saved-snapshot root, inventory SHA256,
catalogue SHA256 and fresh output path. The catalogue is parsed as literals;
its code is never executed. Each selected page is extent- and SHA256-checked,
all image IDs must be unique, and the complete source row count must agree.
This verifies identities against the supplied pins. Trust in those pins and
their acquisition remains the operator's independent responsibility.

`test_census.py` contains generated metadata controls. Run it from this
directory with the normal sibling `agent-operator/source/n074/catalogue.py`
present. A private review layout may set `N074_CATALOGUE_PATH` to the exact
read-only catalogue. These tests do not establish genuine map availability,
neural understanding or scientific performance.

The census has no candidate-visible interface. Task names, source filenames,
image IDs and metadata remain operator-only. No current task/registry status
is promoted. Authentic image hashes, geometry, independent spatial support,
task-family/dependency selection and execution qualification remain separate.
