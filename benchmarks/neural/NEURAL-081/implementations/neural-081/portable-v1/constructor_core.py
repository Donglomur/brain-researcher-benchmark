#!/usr/bin/env python3
"""Source fragment for the one-file, source-only NEURAL081 instance constructor.

This fragment is assembled with the separately authored metadata stages and CLI.
It never starts qualification or a scientific operation.
"""
import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
import types

TASK = 'NEURAL-081'
ALIAS = 'full10_instructed_excerpt_v1'
BODY_CAP = 2 * 2**20
PROFILE_CAP = 512 * 1024
CENTRAL = 'neural081/central'
PARENT = 'neural081/parent'
QREL = CENTRAL + '/runtime-qualification'
RREL = CENTRAL + '/operator-selections'
JREL = 'benchmarks/neuroscience/neural-081/manifest.json'
VREL = 'neural081/registry-generations'
BREL = 'neural081/construction'
LREL = 'neural081/local-selection/SELECTION.json'
PUBLIC_MAP_CANONICAL_SHA = 'e34283ef772e5036108e18d2a06b56085d46368e33145ecf9dda40afa0f216bc'
ORIGINAL_ACTIVE_ROLES = {'neural081/central/n081_dispatch.py': {'bytes': 3214, 'kind': 'public', 'sha256': '71bb75f0dcfa720f7a1eacfaed633a4b2bc72e330ec1c0180f8d847fa9ca5a27', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/central-adapter-v1/n081_dispatch.py'}, 'neural081/central/n081_host.py': {'bytes': 5801, 'kind': 'public', 'sha256': '0f4f03460c8b983739ccd7ba4d393e4aff151efce8d757f9826a5ef9b5967de6', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/central-adapter-v1/n081_host.py'}, 'neural081/central/n081_readback.py': {'bytes': 6038, 'kind': 'public', 'sha256': 'f02529650470b8756e8d8d181ee2ee7d6dac7142c1de29c0fa1ba31b946f9ad6', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/central-adapter-v1/n081_readback.py'}, 'neural081/parent/program/arrays.py': {'bytes': 5046, 'kind': 'public', 'sha256': '40f53e516b6a3cfd523387129a61089c28b3a4d3558e47d260619360b3ed4a8c', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/arrays.py'}, 'neural081/parent/program/authority.py': {'bytes': 7305, 'kind': 'public', 'sha256': '3202f2b873480a2ebe424fcd4ef83baee81bb1e92314577747bedc3fcffc7a7c', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/authority.py'}, 'neural081/parent/program/candidate_runner.py': {'bytes': 13423, 'kind': 'public', 'sha256': '1e804c9bf3f4d0e7d25afe646617194e3fc323e813808bfb9c3bcce9b83dbb8a', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/candidate_runner.py'}, 'neural081/parent/program/channel.py': {'bytes': 3933, 'kind': 'public', 'sha256': '2f9d924826fe82d4ef8813ba98ca94fe6d0826085fc39ad8ab2bc576a76029a5', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/channel.py'}, 'neural081/parent/program/closure.py': {'bytes': 31274, 'kind': 'public', 'sha256': '96c6b556c650f54ab57180c9ec7658e8e65e2a5f9a7ec5fc5720dc04983fb025', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/closure.py'}, 'neural081/parent/program/common.py': {'bytes': 10831, 'kind': 'public', 'sha256': 'f36d21526d3283750e793bbdac7d7236385511532161d3e61a8cef68e22bb836', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/common.py'}, 'neural081/parent/program/controller.py': {'bytes': 19116, 'kind': 'public', 'sha256': '2038ba8c5adf12bea39bc117f5af63f152e4787ee1aba16b1ac9635ea5dbb81d', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/controller.py'}, 'neural081/parent/program/custody.py': {'bytes': 2389, 'kind': 'public', 'sha256': 'c7ddebf321f16bb588de898a36a9feaa85ce05752ac259f342c1e3bde4103998', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/custody.py'}, 'neural081/parent/program/entry_driver.py': {'bytes': 1520, 'kind': 'public', 'sha256': '23665480f9add496ed9dbc1b4fb53e130fe8435eb7ba08bd91838f2a07a86b6b', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/entry_driver.py'}, 'neural081/parent/program/episodes.py': {'bytes': 24492, 'kind': 'public', 'sha256': '21f402bd46ef2a80f847fae19d6a43c7aeddb42f3f4192588eaf505ba24a8c39', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/episodes.py'}, 'neural081/parent/program/fd_protocol.py': {'bytes': 3135, 'kind': 'public', 'sha256': '7e80e639998efc6f31f3268ba2fabb0a42c33b2e01278c68802cc8b641d0916d', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/fd_protocol.py'}, 'neural081/parent/program/grade_driver.py': {'bytes': 4338, 'kind': 'public', 'sha256': 'cdcecd40d8d9d30415f3c6ecfca3b35ab7a04afef83035f5ff1e3d91c08d5984', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/grade_driver.py'}, 'neural081/parent/program/grade_entry.py': {'bytes': 6232, 'kind': 'public', 'sha256': '26d164e07eaa4e2a9711b56735d68f9df64b208050fc7c8199545c7c8a5bba71', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/grade_entry.py'}, 'neural081/parent/program/grading.py': {'bytes': 13867, 'kind': 'public', 'sha256': 'e940d6bb5454e41fb6fb81f77ad9571edf2d764082de6e2d72d5a5d595c3965d', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/grading.py'}, 'neural081/parent/program/host_observation.py': {'bytes': 2458, 'kind': 'public', 'sha256': '0667f8308bca569d302f0054b1b8e931418c0c1a48761325cd0975979b18182e', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/host_observation.py'}, 'neural081/parent/program/issuer_entry.py': {'bytes': 5097, 'kind': 'public', 'sha256': 'a52afac5619ed9e40e47e8de035d216c4aeed378b914a8ddcbe6c513ba4a4268', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/issuer_entry.py'}, 'neural081/parent/program/issuer_sandbox.py': {'bytes': 3642, 'kind': 'public', 'sha256': '55942e56dfa3126774366be64c874e9746ef70a0446ad1c0941ea99db503cfba', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/issuer_sandbox.py'}, 'neural081/parent/program/issuer_worker.py': {'bytes': 3580, 'kind': 'public', 'sha256': '087e73f1d698479f642712e548ed075c7816a5330c8443cbb051d162f56690bf', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/issuer_worker.py'}, 'neural081/parent/program/metrics.py': {'bytes': 4807, 'kind': 'public', 'sha256': '927272a26c5fef6f02d62eb407337eccda93029030cece3eb5f01d4a7face74b', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/metrics.py'}, 'neural081/parent/program/model_io.py': {'bytes': 5308, 'kind': 'public', 'sha256': '7078e45e6dbe3902659fd3fd4f2faecb1f39ebbd6946a0a3ac000652ca577118', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/model_io.py'}, 'neural081/parent/program/numeric_entry.py': {'bytes': 3003, 'kind': 'public', 'sha256': '7476c437cf8198b563c8f3961afad992afccd6492f9b2da61eb693f009ef0d00', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/numeric_entry.py'}, 'neural081/parent/program/numeric_worker.py': {'bytes': 13806, 'kind': 'public', 'sha256': 'd2021f842353ea30ecc58764e65e1256a43af0b81016259c695b650db9d30904', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/numeric_worker.py'}, 'neural081/parent/program/outer.py': {'bytes': 10126, 'kind': 'public', 'sha256': 'd489be4c79632a6bd0a45da92e63d5a01351a404abc53cbde9892d8b69056062', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/outer.py'}, 'neural081/parent/program/outputs.py': {'bytes': 4278, 'kind': 'public', 'sha256': 'ebf8b83664c372e87e8347c1a4b722bb8fe95522f59b35baafb186f0bfe12818', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/outputs.py'}, 'neural081/parent/program/preparation.py': {'bytes': 14559, 'kind': 'public', 'sha256': 'b945aea9276ca10930fda6460c8d6e6af69c7d619fcb21cf89cb9f7648c8c8f5', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/preparation.py'}, 'neural081/parent/program/preparation_driver.py': {'bytes': 8490, 'kind': 'public', 'sha256': 'effe3826930a8800f67126a8db0a67f79bfa5fca326ead1956df7acf55d7dd51', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/preparation_driver.py'}, 'neural081/parent/program/preparation_entry.py': {'bytes': 6306, 'kind': 'public', 'sha256': 'd0527f24410bbd01d58efde79a7519f058947546eb1e0598e4f0e975b3006505', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/preparation_entry.py'}, 'neural081/parent/program/preparation_worker.py': {'bytes': 4191, 'kind': 'public', 'sha256': '48d6e9f580f7662b22682ac8b179490eba4cb731eaeb07135b21a05291e39def', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/preparation_worker.py'}, 'neural081/parent/program/projection_broker.py': {'bytes': 14528, 'kind': 'public', 'sha256': 'e58a707607a5eccdc00f8ad057d2ee5081444f51c067dfd3f1c098a555dd8950', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/projection_broker.py'}, 'neural081/parent/program/projection_engine.py': {'bytes': 8418, 'kind': 'public', 'sha256': '663116a1cd7d048876d66ee5ebf376e696dea878326af05d3221854952ee86d6', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/projection_engine.py'}, 'neural081/parent/program/protocol.py': {'bytes': 7677, 'kind': 'public', 'sha256': '1f1e167427a739dd8ee5b268b50e031ae09b0c69cb1a2a784535c5bea2690c6a', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/protocol.py'}, 'neural081/parent/program/public_projection.py': {'bytes': 20434, 'kind': 'public', 'sha256': '2b166e41f4aa5cb466c729289850f3de201136aec85d9666fd77a50f03d1cf41', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/public_projection.py'}, 'neural081/parent/program/reference_driver.py': {'bytes': 18301, 'kind': 'public', 'sha256': '8545c5dbc4b9640116496b46fda882fc2bd2e93e6342a54c8cc702e59e9130af', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/reference_driver.py'}, 'neural081/parent/program/reference_tools.py': {'bytes': 15700, 'kind': 'public', 'sha256': '338c32798ddacfa5b6014f012d008211cf050b81e1f8e0becd42da8b3a833133', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/reference_tools.py'}, 'neural081/parent/program/runtime.py': {'bytes': 59130, 'kind': 'public', 'sha256': 'c7b86193a4f4b68ba1ae00e9ab8772a3f4171b65a9fc24427954049f56195934', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/runtime.py'}, 'neural081/parent/program/schedule.py': {'bytes': 4272, 'kind': 'public', 'sha256': '79e345e0a6f283cb40a35040d39c904e6df5ea9c1aa4ad21fe2901bff1017e0d', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/schedule.py'}, 'neural081/parent/program/transport/__init__.py': {'bytes': 64, 'kind': 'public', 'sha256': 'e0f6988291adacd48c86d140a93df101d86e52e3331c74da6f319a627ff169f4', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/transport/__init__.py'}, 'neural081/parent/program/transport/common.py': {'bytes': 5532, 'kind': 'public', 'sha256': '56b0ed90b8a81686ea5c4057920a741703e3c4d9655ff31bf0db50be821defea', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/transport/common.py'}, 'neural081/parent/program/transport/process.py': {'bytes': 25853, 'kind': 'public', 'sha256': '4f48e7a90b312a14f2dec54988326d782d4a2666f61f4ce7cc4ef3c4c4bcef58', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/transport/process.py'}, 'neural081/parent/program/transport/provider.py': {'bytes': 13436, 'kind': 'public', 'sha256': '384c5fc38b79a674822225606df80ff223bf700c140247caad82927987dc1cdd', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/transport/provider.py'}, 'neural081/parent/program/worker_bootstrap.py': {'bytes': 8380, 'kind': 'public', 'sha256': '40fd74609bb9feba1663df3e5b95d82edaf77bb50c7a2bef5e6aa76d72159006', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/worker_bootstrap.py'}, 'neural081/parent/references/r1/numeric.py': {'bytes': 38757, 'kind': 'public', 'sha256': '64d74293bde8b6f595ecee37de8592d5c703e969a240cedf3d4a7b10570f3bb5', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/references/r1/numeric.py'}, 'neural081/parent/references/r2/numeric.py': {'bytes': 31964, 'kind': 'public', 'sha256': '6ed980ef8b1fcdb7991b307bb390cb84b29c6cf2669f4b6499a081489b52978e', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/references/r2/numeric.py'}, 'neural081/protocol/CANDIDATE_PROJECTION.md': {'bytes': 9600, 'kind': 'public', 'sha256': '56e879aa581559e9bbb2c9c6afadf6a8952e24b677a5cc5f3359922ef9e5d067', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/correction-v4/CANDIDATE_PROJECTION.md'}, 'neural081/protocol/DESIGN.md': {'bytes': 11179, 'kind': 'public', 'sha256': '38e1e342b4b697a6cdeca771aae77a6590cc6a02e85df00fba324295f362f44a', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/correction-v4/DESIGN.md'}, 'neural081/protocol/EXECUTION_ADMISSION.md': {'bytes': 8487, 'kind': 'public', 'sha256': '8bc809eb56fb5817507bd2346bb60de3d93d620332570abb570d80cc0cf37983', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/correction-v4/EXECUTION_ADMISSION.md'}, 'neural081/protocol/EXPOSURE_AND_WORKLOAD.md': {'bytes': 12981, 'kind': 'public', 'sha256': '056616d3e4b61edf49a9c3b5676a17bea4764be46555c3c372570b2e97ea0da8', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/correction-v4/EXPOSURE_AND_WORKLOAD.md'}, 'neural081/protocol/GRAPH_AND_CUSTODY.md': {'bytes': 15588, 'kind': 'public', 'sha256': '58e6d7c042be555a8fed68259f77fa50745ecdfdebb58265c1757e92cf670e43', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/correction-v4/GRAPH_AND_CUSTODY.md'}, 'neural081/protocol/INTERFACES_AND_REVIEW_GATES.md': {'bytes': 13952, 'kind': 'public', 'sha256': '5c644e8dff9b354c4b98453af7f51187aa80c1c31a7a4b23ce2726a287d58ee8', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/correction-v4/INTERFACES_AND_REVIEW_GATES.md'}, 'neural081/protocol/REFERENCE_MATHEMATICS.md': {'bytes': 18738, 'kind': 'public', 'sha256': '86d63a21112cb6c44bf16dced78ac25c4b3fe79c8b6aeb34e0dac3c6a49b54d1', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/correction-v4/REFERENCE_MATHEMATICS.md'}, 'neural081/protocol/RESOURCE_CONTRACT.md': {'bytes': 14548, 'kind': 'public', 'sha256': '9ef4c544d5eacf66666247ba8459df481eb031215909a7d30d7fc497aab3666d', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/correction-v4/RESOURCE_CONTRACT.md'}, 'neural081/protocol/SOURCE_AND_BOUNDARIES.md': {'bytes': 9862, 'kind': 'public', 'sha256': '70755998ec5139d1f9b2a639bef7f2e24268c64f3a56d224bc16c955acecd790', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/SOURCE_AND_BOUNDARIES.md'}, 'neural081/protocol/SOURCE_BINDINGS.json': {'bytes': 15780, 'kind': 'public', 'sha256': 'bf7e3945158388c3035decc8440d2e49f3923b9160792d9f298d518ffbed7b05', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/SOURCE_BINDINGS.json'}, 'neural081/protocol/SUPPORT_CUSTODY.md': {'bytes': 6450, 'kind': 'public', 'sha256': '3057387610b552f478f48f7ed47b522daa11657bfec4189644fae3036d92f96c', 'source': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/correction-v4/SUPPORT_CUSTODY.md'}, 'tools/neurobench_campaign.py': {'bytes': 26686, 'kind': 'public', 'sha256': 'b17b4317427f83ce28ab7ea5a4fbc42b689870ef2a7144a7e094ecb0bef9e59e', 'source': 'tools/neurobench_campaign.py'}, 'tools/neurobench_campaign_gate.py': {'bytes': 16326, 'kind': 'public', 'sha256': '11723f00691ef58e7c96b29030c810c98969e0be8411ec48b5bbc56a7874f61d', 'source': 'tools/neurobench_campaign_gate.py'}}
VARIANT_ORIGINS = {'neural081/central/entry.py': {'path': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/central-adapter-v1/entry.py', 'bytes': 10092, 'sha256': '87fb1ef2b8cb8e31011cda0507fd1c1f0c9983c034262e35a93eaeff4d65c9e8'}, 'neural081/central/n081_routing.py': {'path': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/central-adapter-v1/n081_routing.py', 'bytes': 5812, 'sha256': '9e7de0f1c643dc5bbdb842df9f79962b8fe5cfbd888b8565ae684fd7f90b0e4e'}, 'neural081/central/n081_selection.py': {'path': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/central-adapter-v1/n081_selection.py', 'bytes': 12592, 'sha256': '391815c0bba259ea27e6a057447a23265f1df14f7f584c6c39762b82806bdf39'}, 'neural081/parent/program/entry.py': {'path': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/entry.py', 'bytes': 6486, 'sha256': '826663ae0b1ba1f4d94769e20cacab772cc00dd1bd7a37071f8478047afc9e48'}}
NEW_ACTIVE_ROLES = ('neural081/central/portable_gate.py', 'neural081/protocol/CANDIDATE_PROTOCOL.txt', 'tools/neural081_instance.py')



class Failure(ValueError):
    pass


def need(test, message):
    # Predicates may return bool or a documented truthy result (e.g. re.Match).
    # Evidence fields still require explicit type/is-True tests at their callers.
    if not test:
        raise Failure(message)


def exact(value, keys):
    need(type(value) is dict and set(value) == set(keys), 'exact keys: ' + ','.join(keys))
    return value


def integer(value, low=0, high=None):
    need(type(value) is int and value >= low and (high is None or value <= high), 'bounded integer')
    return value


def finite(value, low=None):
    need(type(value) in (int, float) and math.isfinite(value) and (low is None or value >= low), 'finite number')
    return value


def same(a, b):
    if type(a) is not type(b):
        return False
    if type(a) is dict:
        return set(a) == set(b) and all(same(a[k], b[k]) for k in a)
    if type(a) in (list, tuple):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if type(a) is float:
        return math.isfinite(a) and math.isfinite(b) and a.hex() == b.hex()
    return a == b


def digest(value):
    need(type(value) is str and len(value) == 64 and all(x in '0123456789abcdef' for x in value), 'SHA256')
    return value


def canonical(path):
    need(type(path) is str and path.startswith('/') and not path.startswith('//') and '\\' not in path and '\0' not in path, 'absolute ordinary path')
    need(all(x not in ('', '.', '..') for x in path.split('/')[1:]), 'canonical path components')
    need(Path(path).as_posix() == path, 'canonical path spelling')
    return Path(path)


def relative(path):
    need(type(path) is str and path and not path.startswith('/') and '\\' not in path and '\0' not in path, 'relative path')
    need(all(x not in ('', '.', '..') for x in path.split('/')) and Path(path).as_posix() == path, 'ordinary relative components')
    return path


def descriptor(value, absolute=True):
    exact(value, ('path', 'bytes', 'sha256'))
    (canonical if absolute else relative)(value['path'])
    integer(value['bytes'], 1, 64 * 2**20)
    digest(value['sha256'])
    return value


def pin(raw):
    need(type(raw) is bytes, 'byte body')
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def _json_shape(value, depth=0, active=None):
    need(depth <= 100, 'bounded JSON nesting')
    active = set() if active is None else active
    if value is None or type(value) is bool:
        return 5
    if type(value) is int:
        need(value.bit_length() <= 256, 'bounded JSON integer')
        return 80
    if type(value) is float:
        finite(value)
        return 32
    if type(value) is str:
        need(len(value) <= 2**20, 'bounded JSON string')
        return 6 * len(value) + 2
    need(type(value) in (list, dict) and len(value) <= 100000, 'bounded JSON container')
    need(id(value) not in active, 'acyclic JSON')
    active.add(id(value))
    if type(value) is list:
        size = 2 + sum(1 + _json_shape(x, depth + 1, active) for x in value)
    else:
        need(all(type(k) is str for k in value), 'string JSON keys')
        size = 2 + sum(2 + _json_shape(k, depth + 1, active) + _json_shape(v, depth + 1, active) for k, v in value.items())
    active.remove(id(value))
    return size


def encode(value):
    _json_shape(value)
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False, ensure_ascii=True) + '\n').encode('utf-8')


def _pairs(items):
    out = {}
    for key, value in items:
        need(key not in out, 'duplicate JSON key')
        out[key] = value
    return out


def parse(raw):
    need(type(raw) is bytes, 'JSON bytes')
    # Bound structural nesting before the allocating parser. Quotes/escapes are
    # scanned explicitly; this is only a preventive bound, not a second parser.
    depth = 0
    quoted = escaped = False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            need(depth <= 100, 'JSON nesting before parse')
        elif byte in (93, 125):
            depth -= 1
            need(depth >= 0, 'JSON closing delimiter')
    need(depth == 0 and not quoted, 'complete JSON framing')
    out = json.loads(raw, object_pairs_hook=_pairs, parse_constant=lambda _: (_ for _ in ()).throw(Failure('nonfinite JSON')))
    _json_shape(out)
    return out


def managed_size(value, seen=None):
    seen = set() if seen is None else seen
    if id(value) in seen:
        return 0
    seen.add(id(value))
    total = sys.getsizeof(value)
    if type(value) is dict:
        total += sum(managed_size(k, seen) + managed_size(v, seen) for k, v in value.items())
    elif type(value) in (list, tuple):
        total += sum(managed_size(x, seen) for x in value)
    return total


class Budget:
    """Prospective logical I/O and managed-buffer bounds; not physical RSS."""
    def __init__(self, reads, writes, live, deadline):
        self.limits = {'read_bytes': integer(reads, 1), 'write_bytes': integer(writes, 1)}
        self.live_cap = integer(live, 65536)
        self.used = dict.fromkeys(self.limits, 0)
        self.live = self.peak = 0
        self.started = time.monotonic()
        self.end = finite(deadline, 0)
        need(self.started < self.end, 'selected constructor deadline')

    def check(self):
        need(time.monotonic() < self.end, 'constructor original deadline')

    check_clock = check

    def charge(self, name, value):
        self.check()
        integer(value)
        need(name in self.limits, 'constructor logical counter')
        need(self.used[name] + value <= self.limits[name], 'prospective ' + name)
        self.used[name] += value

    def hold(self, value):
        integer(value)
        self.check()
        need(self.live + value <= self.live_cap, 'prospective managed live bytes')
        self.live += value
        self.peak = max(self.peak, self.live)
        return value

    def release(self, value):
        integer(value)
        need(value <= self.live, 'managed buffer accounting')
        self.live -= value

    def snapshot(self):
        return {'limits': dict(self.limits), 'used': dict(self.used), 'managed_peak_bytes': self.peak,
                'managed_live_bytes': self.live, 'deadline': self.end, 'physical_IO_RSS_measured': False}


def ordinary_ancestors(path, *, leaf_exists=True):
    path = canonical(str(path))
    for entry in [*reversed(path.parents), *([path] if leaf_exists else [])]:
        info = entry.lstat()
        need(not stat.S_ISLNK(info.st_mode), 'no symlink path component')
        if entry != path:
            need(stat.S_ISDIR(info.st_mode), 'ordinary parent directory')
    return path


def disjoint(paths):
    values = [canonical(str(p)) for p in paths]
    for i, a in enumerate(values):
        for b in values[i + 1:]:
            need(a != b and not a.is_relative_to(b) and not b.is_relative_to(a), 'disjoint selected roots')
    return values


def capture_bytes(desc, budget, *, cap=BODY_CAP):
    descriptor(desc)
    need(desc['bytes'] <= cap, 'capture extent before open')
    path = ordinary_ancestors(desc['path'])
    budget.charge('read_bytes', desc['bytes'] + 1)
    reserved = budget.hold(desc['bytes'] + 1)
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and a.st_size == desc['bytes'], 'ordinary exact capture')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(desc['bytes'] + 1)
        b, c = os.fstat(fd), path.lstat()
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
        need(len(raw) == desc['bytes'] and all(getattr(a, k) == getattr(b, k) == getattr(c, k) for k in fields), 'stable complete capture')
        need(same(pin(raw), {k: desc[k] for k in ('bytes', 'sha256')}), 'captured SHA/extent')
        budget.check()
        return raw
    finally:
        if fd is not None:
            os.close(fd)
        budget.release(reserved)


def capture_json(desc, budget, *, cap=BODY_CAP):
    descriptor(desc)
    need(desc['bytes'] <= cap, 'metadata extent before parse')
    # At most one parser transient reservation; actual retained Python object
    # cost remains charged for the invocation. This is not an OS RSS claim.
    transient = budget.hold(80 * desc['bytes'] + 16384)
    try:
        value = parse(capture_bytes(desc, budget, cap=cap))
        actual = managed_size(value)
        need(actual <= transient, 'retained metadata within preventive parse reservation')
    finally:
        budget.release(transient)
    budget.hold(actual)
    return value


def sync_directory(path, budget):
    budget.check()
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    budget.check()


def mkdirs(root, target, budget):
    root, target = canonical(str(root)), canonical(str(target))
    need(target == root or target.is_relative_to(root), 'owned directory domain')
    ordinary_ancestors(root)
    current = root
    for part in target.relative_to(root).parts:
        current = current / part
        try:
            current.mkdir(mode=0o700)
        except FileExistsError:
            info = current.lstat()
            need(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode), 'ordinary selected directory')
        else:
            sync_directory(current, budget)
            sync_directory(current.parent, budget)
    return target


def publish_bytes(root, path, raw, budget):
    need(type(raw) is bytes and 0 < len(raw) <= BODY_CAP, 'bounded publication bytes')
    root, path = canonical(str(root)), canonical(str(path))
    need(path.is_relative_to(root), 'exact publication domain')
    mkdirs(root, path.parent, budget)
    budget.charge('write_bytes', len(raw))
    # Account the caller's still-live publication body through its readback.
    publication_live = budget.hold(len(raw) + 64)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(raw)
            stream.flush()
        os.fsync(fd)
    finally:
        os.close(fd)
    sync_directory(path.parent, budget)
    d = {'path': str(path), **pin(raw)}
    need(capture_bytes(d, budget) == raw, 'durable published readback')
    budget.check()
    budget.release(publication_live)
    return d


def publish_json(root, path, value, budget):
    scratch = budget.hold(2 * _json_shape(value) + 4096)
    try:
        return publish_bytes(root, path, encode(value), budget)
    finally:
        budget.release(scratch)


def route_template(root, source, entry_sha, condition):
    need(condition in ('default', ALIAS), 'complete selected route')
    return {'argv': ['{python}', '-I', '-S', '-B', '-X',
                    'pycache_prefix=' + str(root / CENTRAL / 'fresh-central-pycache'),
                    CENTRAL + '/entry.py', '--condition', condition,
                    '--program', '{program}', '--output', '{output}', '--review', '{review}',
                    '--other-reserve-bytes', '{other_reserve_bytes}', '--source-bytes', str(source['bytes']),
                    '--source-sha256', source['sha256']],
            'working_directory': '.', 'sha256': digest(entry_sha)}


def rel_desc(root, desc):
    descriptor(desc)
    p = canonical(desc['path'])
    need(p.is_relative_to(root), 'source-relative descriptor')
    return {'path': p.relative_to(root).as_posix(), 'bytes': desc['bytes'], 'sha256': desc['sha256']}


def _profile(profile, root):
    exact(profile, ('schema', 'task_id', 'root_roles', 'input_records', 'environment_records', 'execution_selection'))
    need(profile['schema'] == 'neural081_portable_profile_v1' and profile['task_id'] == TASK, 'portable input profile')
    roles = exact(profile['root_roles'], ('source', 'operator', 'raw', 'secret', 'protected', 'output'))
    need(roles['source'] == str(root), 'exact chosen source root')
    paths = [root]
    for kind in ('operator', 'raw', 'secret', 'protected'):
        need(type(roles[kind]) is list and 1 <= len(roles[kind]) <= 32, 'bounded external roots')
        paths.extend(canonical(p) for p in roles[kind])
    paths.append(canonical(roles['output']))
    disjoint(paths)
    for key in ('input_records', 'environment_records', 'execution_selection'):
        value = profile[key]
        if type(value) is dict and set(value) == {'disposition'}:
            need(value['disposition'] == 'not_supplied', 'explicit unmet profile slot')
        else:
            descriptor(value)
    return roles


def validate_release(release):
    exact(release, ('schema', 'task_id', 'public_files', 'public_manifest', 'active_sources', 'variants'))
    need(release['schema'] == 'neural081_portable_release_v1' and release['task_id'] == TASK, 'portable release schema')
    rows = release['public_files']
    need(type(rows) is list and len(rows) == 105, 'all105 public originals and derivatives')
    for d in rows:
        descriptor(d, absolute=False)
    need([d['path'] for d in rows] == sorted({d['path'] for d in rows}), 'unique sorted public map')
    descriptor(release['public_manifest'], absolute=False)
    need(release['public_manifest'] in rows and release['public_manifest']['bytes'] == 48901 and release['public_manifest']['sha256'] == '32705c641e263ac91c5f0b7f5ed60ac42cac9f9af87c07cd74e30cd1bcfee2f5', 'actual original public manifest')
    need(pin(encode(rows))['sha256'] == PUBLIC_MAP_CANONICAL_SHA, 'literal complete original105 identities')
    active = release['active_sources']
    need(type(active) is dict and set(active) == set(ORIGINAL_ACTIVE_ROLES) | set(VARIANT_ORIGINS) | set(NEW_ACTIVE_ROLES), 'literal all66 active role paths')
    for name, expected in ORIGINAL_ACTIVE_ROLES.items():
        need(same(active[name], expected), 'unchanged original scientific/source role')
    for name in set(VARIANT_ORIGINS) | set(NEW_ACTIVE_ROLES):
        need(active[name]['kind'] == 'release', 'explicit newly authored source role')
    for target, row in active.items():
        relative(target)
        exact(row, ('kind', 'source', 'bytes', 'sha256'))
        relative(row['source'])
        integer(row['bytes'], 1, BODY_CAP)
        digest(row['sha256'])
        need(row['kind'] in ('public', 'release'), 'explicit source provenance class')
        if row['kind'] == 'public':
            need({'path': row['source'], 'bytes': row['bytes'], 'sha256': row['sha256']} in rows, 'exact original active source')
    need(sum(p.endswith('.py') for p in active) == 54, '54 active Python bodies')
    need(sum(p.startswith('neural081/protocol/') for p in active) == 12, 'all12 protocol/context bodies')
    variants = release['variants']
    need(type(variants) is list and len(variants) == 4, 'exact four declared source variants')
    expected = {PARENT + '/program/entry.py', CENTRAL + '/entry.py', CENTRAL + '/n081_routing.py', CENTRAL + '/n081_selection.py'}
    seen = set()
    for row in variants:
        exact(row, ('target', 'original'))
        descriptor(row['target'], absolute=False)
        descriptor(row['original'], absolute=False)
        target = row['target']['path']
        need(target in expected and target not in seen and row['original'] in rows and same(row['original'], VARIANT_ORIGINS[target]), 'one literal declared variant original')
        need(target in active and active[target]['kind'] == 'release' and same({k: active[target][k] for k in ('bytes', 'sha256')}, {k: row['target'][k] for k in ('bytes', 'sha256')}), 'variant source map join')
        seen.add(target)
    need(seen == expected and [r['target']['path'] for r in variants] == sorted(seen), 'all four variants only, canonical order')
    return release


class CreatedRoot:
    """A held inode acquired only after this invocation's exclusive mkdir.

    The parent namespace must still be under qualified exclusive custody. A
    named-path check alone is never permission to write a failure record.
    """
    def __init__(self):
        self.root = None
        self.fd = None
        self.identity = None

    def create(self, root):
        need(self.fd is None and self.root is None, 'single fresh root ownership')
        root = canonical(str(root))
        ordinary_ancestors(root.parent)
        root.mkdir(mode=0o700)  # Existing roots raise before ownership exists.
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            info = os.fstat(fd)
            named = root.lstat()
            need(stat.S_ISDIR(info.st_mode) and stat.S_ISDIR(named.st_mode) and
                 (info.st_dev, info.st_ino) == (named.st_dev, named.st_ino),
                 'exclusive created root inode acquisition')
            self.root, self.fd = root, fd
            self.identity = (info.st_dev, info.st_ino)
        except BaseException:
            os.close(fd)
            raise

    def check(self):
        need(self.fd is not None and self.identity is not None, 'created root ownership required')
        ordinary_ancestors(self.root)
        info, named = os.fstat(self.fd), self.root.lstat()
        need(stat.S_ISDIR(info.st_mode) and stat.S_ISDIR(named.st_mode) and
             (info.st_dev, info.st_ino) == self.identity == (named.st_dev, named.st_ino),
             'unchanged exclusively created root inode')

    def publish_failure(self, value, budget):
        self.check()
        scratch = budget.hold(2 * _json_shape(value) + 4096)
        fd = None
        try:
            raw = encode(value)
            need(0 < len(raw) <= BODY_CAP, 'bounded failure metadata')
            budget.charge('write_bytes', len(raw))
            budget.charge('read_bytes', len(raw) + 1)
            self.check()
            # dir_fd anchors this exclusive write even if a named ancestor is
            # concurrently replaced; it cannot write into the replacement.
            fd = os.open('CONSTRUCTION_FAILURE.json', os.O_RDWR | os.O_CREAT |
                         os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=self.fd)
            with os.fdopen(fd, 'w+b', closefd=False) as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(fd)
                stream.seek(0)
                need(stream.read(len(raw) + 1) == raw, 'exact owned failure readback and EOF')
            info = os.fstat(fd)
            named = os.stat('CONSTRUCTION_FAILURE.json', dir_fd=self.fd, follow_symlinks=False)
            need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                 (info.st_dev, info.st_ino) == (named.st_dev, named.st_ino),
                 'owned failure file identity')
            os.fsync(self.fd)
            self.check()
            budget.check()
        finally:
            if fd is not None:
                os.close(fd)
            budget.release(scratch)

    def close(self):
        fd, self.fd = self.fd, None
        if fd is not None:
            os.close(fd)


def build_instance(release_desc, public_root, root, profile_desc, budget, *, root_ownership=None):
    """Materialize only source/text metadata; no operation or operand is opened."""
    need(root_ownership is None or type(root_ownership) is CreatedRoot, 'explicit root ownership carrier')
    public_root, root = canonical(public_root), canonical(root)
    release_dir = canonical(release_desc['path']).parent
    disjoint([public_root, root])
    need(root != release_dir and not release_dir.is_relative_to(root), 'release outside generated instance')
    ordinary_ancestors(root.parent)
    need(not root.exists(), 'fresh instance root')
    release = validate_release(capture_json(release_desc, budget))
    profile = capture_json(profile_desc, budget, cap=PROFILE_CAP)
    roles = _profile(profile, root)
    own = release['active_sources'].get('tools/neural081_instance.py')
    need(type(own) is dict and own['kind'] == 'release', 'shipped constructor belongs to release')
    need(canonical(str(Path(__file__).absolute())) == release_dir / own['source'], 'genuine released constructor path')
    # Authenticate every original before creating ROOT. Never recursively list a
    # checkout and never follow any of the original documents' operand pointers.
    for d in release['public_files']:
        capture_bytes({**d, 'path': str(public_root / d['path'])}, budget)
    for row in release['active_sources'].values():
        base = public_root if row['kind'] == 'public' else release_dir
        capture_bytes({'path': str(base / row['source']), 'bytes': row['bytes'], 'sha256': row['sha256']}, budget)
    if root_ownership is None:
        root.mkdir(mode=0o700)
    else:
        root_ownership.create(root)
    sync_directory(root, budget)
    sync_directory(root.parent, budget)
    outputs = []
    for d in release['public_files']:
        raw = capture_bytes({**d, 'path': str(public_root / d['path'])}, budget)
        outputs.append(publish_bytes(root, root / 'origin' / d['path'], raw, budget))
        del raw
    active = {}
    for name, row in sorted(release['active_sources'].items()):
        base = public_root if row['kind'] == 'public' else release_dir
        raw = capture_bytes({'path': str(base / row['source']), 'bytes': row['bytes'], 'sha256': row['sha256']}, budget)
        active[name] = publish_bytes(root, root / name, raw, budget)
        outputs.append(active[name])
        del raw
    rel = publish_bytes(root, root / 'neural081/PORTABLE_RELEASE.json', capture_bytes(release_desc, budget), budget)
    public_manifest = release['public_manifest']
    origin = publish_bytes(root, root / 'neural081/PUBLIC_ORIGIN_MAP.json', capture_bytes({**public_manifest, 'path': str(public_root / public_manifest['path'])}, budget), budget)
    py = [d for n, d in sorted(active.items()) if n.endswith('.py')]
    contexts = [d for n, d in sorted(active.items()) if n.startswith('neural081/protocol/')]
    variants = [{'target': active[v['target']['path']], 'original': v['original']} for v in sorted(release['variants'], key=lambda x: x['target']['path'])]
    construction = publish_json(root, root / PARENT / 'CONSTRUCTION.json', {'schema': 'neural081_portable_construction_v1', 'task_id': TASK, 'root': str(root), 'release': rel, 'public_origin': origin, 'python_bodies': py, 'context_bodies': contexts, 'variants': variants, 'construction_only': True, 'runtime_authorization': False}, budget)
    names = []
    for name, d in sorted(active.items()):
        if name.startswith(PARENT + '/program/') and name != PARENT + '/program/entry.py':
            part = name[len(PARENT + '/program/'):]
            need(part.endswith('.py'), 'parent module suffix')
            module = 'transport' if part == 'transport/__init__.py' else part[:-3].replace('/', '.')
            names.append({'name': module, 'source': d})
    need(len(names) == 41 and len({r['name'] for r in names}) == 41, 'fixed41 parent modules')
    parent_doc = {'schema': 'neural081_portable_parent_source_v1', 'task_id': TASK, 'entry': active[PARENT + '/program/entry.py'], 'modules': names, 'auxiliary': [{'role': role, 'source': active[PARENT + '/references/' + role + '/numeric.py']} for role in ('r1', 'r2')], 'construction': construction}
    parent = publish_json(root, root / PARENT / 'SOURCE_MANIFEST.json', parent_doc, budget)
    fixed = {**active, 'neural081/PORTABLE_RELEASE.json': rel, 'neural081/PUBLIC_ORIGIN_MAP.json': origin, PARENT + '/CONSTRUCTION.json': construction, PARENT + '/SOURCE_MANIFEST.json': parent}
    central_names = {'entry.py', 'n081_routing.py', 'n081_selection.py', 'n081_host.py', 'n081_readback.py', 'n081_dispatch.py', 'portable_gate.py'}
    need({n[len(CENTRAL) + 1:] for n in active if n.startswith(CENTRAL + '/')} == central_names, 'exact seven central sources')
    prior = [d for n, d in sorted(fixed.items()) if not n.startswith(CENTRAL + '/')]
    need(len(prior) == 63, 'exact prior63 identities, no forward edge')
    bindings_doc = {'schema': 'neural081_portable_central_bindings_v1', 'task_id': TASK, 'parent_manifest': parent, 'construction': construction, 'source_rows': prior, 'tools': {'campaign': active['tools/neurobench_campaign.py'], 'campaign_gate': active['tools/neurobench_campaign_gate.py']}}
    bindings = publish_json(root, root / CENTRAL / 'BINDINGS.json', bindings_doc, budget)
    fixed[CENTRAL + '/BINDINGS.json'] = bindings
    central_doc = {'schema': 'neural081_portable_central_source_v1', 'task_id': TASK, 'files': {n: {k: fixed[CENTRAL + '/' + n][k] for k in ('bytes', 'sha256')} for n in sorted(central_names | {'BINDINGS.json'})}}
    central = publish_json(root, root / CENTRAL / 'SOURCE_MANIFEST.json', central_doc, budget)
    fixed[CENTRAL + '/SOURCE_MANIFEST.json'] = central
    need(len(fixed) == 72, 'complete new72 fixed identity map')
    freeze = publish_json(root, root / CENTRAL / 'QUALIFICATION_SOURCE.json', {'schema': 'neural081_portable_qualification_source_v1', 'task_id': TASK, 'files': {n: {k: d[k] for k in ('bytes', 'sha256')} for n, d in sorted(fixed.items())}}, budget)
    routes = {name: route_template(root, central, active[CENTRAL + '/entry.py']['sha256'], name) for name in ('default', ALIAS)}
    selection = publish_json(root, root / LREL, {'schema': 'neural081_local_source_selection_v1', 'task_id': TASK, 'construction': construction, 'parent_source': parent, 'central_source': central, 'source_freeze': freeze, 'routes': routes, 'selection_scope': 'local_instance', 'runtime_authorization': False}, budget)
    def registration(condition):
        return {'entrypoint': routes[condition], 'full_programme': True, 'preferred_source_interface': {'path': CENTRAL, 'source': rel_desc(root, central)}, 'source_freeze': rel_desc(root, freeze), 'verification': {'status': 'not_run', 'reason': 'Source construction does not create qualification.'}}
    registry = publish_json(root, root / JREL, {'schema_version': 1, 'id': TASK, 'track': 'neural', 'status': 'source_constructed_not_qualified', 'program_execution': registration('default'), 'program_conditions': {ALIAS: registration(ALIAS)}, 'admission': {'runnable': False, 'research_qualified': False}, 'generic_score_alias': False, 'external_central_original_natural_exit_required': True, 'parent_source': parent}, budget)
    for directory in (QREL, RREL, VREL, BREL):
        mkdirs(root, root / directory, budget)
    requirements = publish_json(root, root / BREL / 'REQUIREMENTS.json', {'schema': 'neural081_portable_requirements_v1', 'task_id': TASK, 'runtime_authorization': False, 'qualification_created': False, 'scientific_execution': False, 'unmet': ['actual input/support qualification', 'actual numerical/native/physical environment qualification', 'actual provider/framing qualification', 'independent seven-role templates and request-bound receipts', 'independent central qualification and protected approvals', 'original external central completion'], 'profile': profile_desc}, budget)
    outputs.extend([rel, origin, construction, parent, bindings, central, freeze, selection, registry, requirements])
    result = {'schema': 'neural081_portable_build_result_v1', 'task_id': TASK, 'root': str(root), 'profile': profile_desc, 'root_roles': roles, 'release': rel, 'public_origin': origin, 'construction': construction, 'parent_source': parent, 'central_source': central, 'source_freeze': freeze, 'selection': selection, 'registry_initial': registry, 'requirements': requirements, 'outputs': sorted(outputs, key=lambda d: d['path']), 'runtime_authorization': False, 'qualification_created': False, 'scientific_execution': False}
    result_desc = publish_json(root, root / BREL / 'BUILD_RESULT.json', result, budget)
    budget.check()
    return {'status': 'constructed_not_qualified', 'instance': result_desc, 'source': central, 'runtime_authorization': False, 'qualification_created': False, 'scientific_execution': False, 'budget': budget.snapshot()}
