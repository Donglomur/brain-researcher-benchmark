# Additive final failure-path repair

This self-contained runtime preserves the frozen successor-v2 and its complete
scientific scope. Only ach_authority.py and ach_data.py differ. Exact original
source, all earlier controls and failures remain in their original paths.

The measurement client now retains each decoded request/reply/raw observation
before validating it. It validates and journals within the owned socket scope,
then closes independently. A close failure cannot erase that exchange. Any
validation failure remains explicitly received_unvalidated. The outer failure
path attaches the exact pending exchange and attempts failure journaling while
preserving the first exception and ordered secondary errors. Authentication
here means the selected peer/source/request join; it does not implement the
missing physical measurement server or qualify its semantics.

MAT source access releases an acquired live reservation on BaseException as
well as ordinary errors, including an interrupted capture before registration
in the reader's live map. The original exception remains primary.

The parent V2 README, API, adaptive-research interpretation, correction history
and disabled deployment document remain the governing unchanged source design.
This revision changes no scientific endpoint, policy, quantity, clock, decoder
format, support, native result, budget ceiling or admission fact. It adds no
provider/model/native/data execution. All 111 native jobs and conditional 160
final bundles / 80,960 reference head fits plus full nulls remain required.

No owner numeric or process controls were rerun: its 24 MiB invented reservation
is exhausted. The sole independent peer will test only this narrow delta.
Source construction and review do not make the deployable benchmark ready.
The external physical measurement implementation, authentic units/clocks/
fields/cohorts/null declarations, competent references and runtime/provider
authority remain absent or independently unadmitted.
