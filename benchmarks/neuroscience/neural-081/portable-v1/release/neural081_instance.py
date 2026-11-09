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


# ---- Byte-identical reviewed source fragment ----

"""Concrete metadata-only context, assembled into the single constructor."""

COUNTERS = ('read_bytes', 'write_bytes', 'native_cpu_seconds', 'native_processes',
            'host_processes', 'provider_requests', 'provider_tokens', 'stream_bytes', 'tool_processes')
WORKER_ROLES = {
    'preparation': ('common', 'protocol', 'arrays', 'custody', 'outputs', 'preparation', 'preparation_worker'),
    'reference': ('common', 'protocol', 'arrays', 'custody', 'model_io', 'outputs', 'numeric_worker', 'numeric'),
    'issuer': ('common', 'protocol', 'arrays', 'fd_protocol', 'projection_engine', 'issuer_sandbox', 'issuer_worker'),
    'grader': ('common', 'protocol', 'arrays', 'custody', 'outputs', 'metrics', 'grading', 'closure', 'schedule',
               'runtime', 'host_observation', 'candidate_runner', 'transport', 'transport.common', 'transport.provider',
               'transport.process', 'authority'),
}
WORKER_ENTRIES = {'preparation': 'preparation_entry', 'reference': 'numeric_entry', 'issuer': 'issuer_entry', 'grader': 'grade_entry'}
WRITE_DOMAINS = {
    'select-run': ('P',), 'bind-environment': ('P',), 'bind-channel': ('P',),
    'request-launch': ('P',), 'bind-launch': ('P',), 'bind-route': ('Q', 'V'),
    'activate-route': ('V',), 'request-review': ('R',), 'publish-review': ('R', 'P'),
    'admit-approved-review': ('P',), 'respond': ('P',),
}


class AdmissionBudget:
    """Original run clock and conservative metadata charges, never a new clock.

    This constructor admission ledger does not impersonate the later running
    scientific ledger. Its metadata charges also debit the CLI's own envelope.
    """
    def __init__(self, context, run):
        self.context = context
        self.origin = finite(run['origin'], 0)
        self.end = finite(run['normal_endpoint'], 0)
        self.limits = {k: integer(run['whole_limits'][k]) for k in COUNTERS}
        self.used = dict.fromkeys(COUNTERS, 0)
        self.clock = time.monotonic
        self.check_clock()

    def check_clock(self):
        self.context.budget.check()
        need(self.origin < time.monotonic() < self.end, 'unchanged selected run endpoint')

    def charge(self, key, value):
        integer(value)
        self.check_clock()
        need(key in self.used and self.used[key] + value <= self.limits[key], 'metadata admission within selected run limits')
        self.used[key] += value
        if key in ('read_bytes', 'write_bytes'):
            self.context.budget.charge(key, value)
        else:
            need(value == 0, 'constructor cannot spend operational work')

    def snapshot(self):
        return {'original_origin': self.origin, 'original_deadline': self.end,
                'logical_used': dict(self.used), 'limits': dict(self.limits),
                'construction_metadata_only': True, 'physical_IO_or_RSS_measured': False}


class Context:
    def __init__(self, instance_desc, run_desc, stage, budget):
        need(stage in WRITE_DOMAINS, 'finite selected metadata stage')
        self.stage, self.budget = stage, budget
        self.instance_descriptor = descriptor(instance_desc)
        self.instance = capture_json(instance_desc, budget)
        exact(self.instance, ('schema', 'task_id', 'root', 'profile', 'root_roles', 'release', 'public_origin',
                             'construction', 'parent_source', 'central_source', 'source_freeze', 'selection',
                             'registry_initial', 'requirements', 'outputs', 'runtime_authorization',
                             'qualification_created', 'scientific_execution'))
        need(self.instance['schema'] == 'neural081_portable_build_result_v1' and self.instance['task_id'] == TASK,
             'complete portable construction result')
        for name in ('runtime_authorization', 'qualification_created', 'scientific_execution'):
            need(self.instance[name] is False, 'construction grants no operational authority')
        self.root = canonical(self.instance['root'])
        self.here = self.root / CENTRAL
        need(instance_desc['path'] == str(self.root / BREL / 'BUILD_RESULT.json'), 'fixed original build-result path')
        self.profile = capture_json(self.instance['profile'], budget, cap=PROFILE_CAP)
        self.roots = _profile(self.profile, self.root)
        need(same(self.roots, self.instance['root_roles']), 'exact profile domains')
        self.source, self.parent, self.construction = (self.instance[k] for k in ('central_source', 'parent_source', 'construction'))
        self._source_cache = {}
        self._metadata_reads = {}
        self._module_cache = {}
        self.run = self.run_descriptor = self.run_root = self._admission_budget = None
        self._validate_instance()
        if run_desc is not None:
            descriptor(run_desc)
            run = self.read(run_desc, scope='operator')
            expected_root = self._run_path(run)
            need(run_desc['path'] == str(expected_root / 'RUN.json'), 'exact selected run location')
            self.run, self.run_descriptor, self.run_root = run, run_desc, expected_root
            self._admission_budget = AdmissionBudget(self, run)
            self.parent_call('authority.run_allocation', run, self._admission_budget)
        need((stage in ('select-run', 'bind-route', 'activate-route')) or self.run is not None,
             'original run required for this metadata stage')
        self.local_gate = self._load_full(CENTRAL + '/portable_gate.py', '_portable_local_gate')

    def _deny(self, path):
        p = canonical(str(path))
        denied = [canonical(v) for k in ('raw', 'secret', 'protected') for v in self.roots[k]]
        denied.append(canonical(self.roots['output']))
        need(not any(p == q or p.is_relative_to(q) or q.is_relative_to(p) for q in denied),
             'constructor never opens raw, key, protected, model or result domains')
        return p

    def _domain_roots(self, scope):
        if scope in ('operator', 'input'):
            return [canonical(v) for v in self.roots['operator']]
        if scope in ('Q', 'R', 'V'):
            return [self.root / {'Q': QREL, 'R': RREL, 'V': VREL}[scope]]
        if scope == 'construction':
            return [self.root / BREL]
        need(scope == 'source', 'declared metadata read scope')
        return []

    def read(self, desc, *, scope, cap=1048576):
        descriptor(desc)
        p = self._deny(desc['path'])
        if scope == 'source':
            allowed = dict(self.fixed_files)
            for key in ('source_freeze', 'selection', 'registry_initial', 'requirements'):
                d = self.instance[key]
                allowed[d['path']] = d
            if p == self.root / JREL:
                cap = min(cap, 131072)
            else:
                need(p.as_posix() in allowed and same(allowed[p.as_posix()], desc), 'exact immutable source metadata pin')
        else:
            need(any(p.is_relative_to(q) for q in self._domain_roots(scope)), 'selected metadata domain before body access')
        value = capture_json(desc, self.budget, cap=cap)
        self._remember(desc)
        return value

    def _remember(self, desc):
        prior = self._metadata_reads.get(desc['path'])
        need(prior is None or same(prior, desc), 'immutable metadata identity during one stage')
        self._metadata_reads[desc['path']] = dict(desc)

    def _validate_instance(self):
        # Only metadata roles are read here. All source bodies subsequently have
        # a literal role and immutable identity before any compile or operation.
        fixed_locs = {'release': 'neural081/PORTABLE_RELEASE.json', 'public_origin': 'neural081/PUBLIC_ORIGIN_MAP.json',
                      'construction': PARENT + '/CONSTRUCTION.json', 'parent_source': PARENT + '/SOURCE_MANIFEST.json',
                      'central_source': CENTRAL + '/SOURCE_MANIFEST.json', 'source_freeze': CENTRAL + '/QUALIFICATION_SOURCE.json',
                      'selection': LREL, 'registry_initial': JREL, 'requirements': BREL + '/REQUIREMENTS.json'}
        for key, rel in fixed_locs.items():
            descriptor(self.instance[key])
            need(self.instance[key]['path'] == str(self.root / rel), 'fixed generated metadata role')
        release = validate_release(capture_json(self.instance['release'], self.budget))
        self.release = release
        c = capture_json(self.construction, self.budget)
        exact(c, ('schema', 'task_id', 'root', 'release', 'public_origin', 'python_bodies', 'context_bodies',
                  'variants', 'construction_only', 'runtime_authorization'))
        active = {name: {'path': str(self.root / name), 'bytes': row['bytes'], 'sha256': row['sha256']}
                  for name, row in release['active_sources'].items()}
        expected_c = {'schema': 'neural081_portable_construction_v1', 'task_id': TASK, 'root': str(self.root),
                      'release': self.instance['release'], 'public_origin': self.instance['public_origin'],
                      'python_bodies': sorted([v for k, v in active.items() if k.endswith('.py')], key=lambda d: d['path']),
                      'context_bodies': sorted([v for k, v in active.items() if k.startswith('neural081/protocol/')], key=lambda d: d['path']),
                      'variants': [{'target': active[v['target']['path']], 'original': v['original']} for v in release['variants']],
                      'construction_only': True, 'runtime_authorization': False}
        need(same(c, expected_c), 'complete acyclic construction lineage')
        p = capture_json(self.parent, self.budget)
        modules = []
        for name in sorted(active):
            if name.startswith(PARENT + '/program/') and name.endswith('.py') and name != PARENT + '/program/entry.py':
                tail = name.split('/program/', 1)[1]
                module = tail[:-12].replace('/', '.') if tail.endswith('/__init__.py') else tail[:-3].replace('/', '.')
                modules.append({'name': module, 'source': active[name]})
        auxiliary = [{'role': r, 'source': active[PARENT + '/references/' + r + '/numeric.py']} for r in ('r1', 'r2')]
        expected_p = {'schema': 'neural081_portable_parent_source_v1', 'task_id': TASK,
                      'entry': active[PARENT + '/program/entry.py'], 'modules': modules,
                      'auxiliary': auxiliary, 'construction': self.construction}
        need(same(p, expected_p), 'literal full parent manifest, all41 modules and two numerics')
        self.parent_document = p
        self.source_files = [p['entry'], *[r['source'] for r in p['modules']], *[r['source'] for r in p['auxiliary']], self.construction]
        fixed = dict(active)
        for key in ('release', 'public_origin', 'construction', 'parent_source'):
            fixed[fixed_locs[key]] = self.instance[key]
        b_desc = {'path': str(self.here / 'BINDINGS.json')}
        manifest = capture_json(self.source, self.budget)
        exact(manifest, ('schema', 'task_id', 'files'))
        need(manifest['schema'] == 'neural081_portable_central_source_v1' and manifest['task_id'] == TASK,
             'portable central manifest')
        names = ('entry.py', 'n081_dispatch.py', 'n081_host.py', 'n081_readback.py', 'n081_routing.py', 'n081_selection.py', 'portable_gate.py', 'BINDINGS.json')
        exact(manifest['files'], names)
        b_desc.update(manifest['files']['BINDINGS.json'])
        self.bindings = capture_json(b_desc, self.budget)
        prior = sorted([v for k, v in fixed.items() if not k.startswith(CENTRAL + '/')], key=lambda d: d['path'])
        need(len(prior) == 63, '63 earlier acyclic identities')
        expected_b = {'schema': 'neural081_portable_central_bindings_v1', 'task_id': TASK, 'parent_manifest': self.parent,
                      'construction': self.construction, 'source_rows': prior,
                      'tools': {'campaign': active['tools/neurobench_campaign.py'], 'campaign_gate': active['tools/neurobench_campaign_gate.py']}}
        need(same(self.bindings, expected_b), 'exact central acyclic source binding')
        for name in names:
            if name != 'BINDINGS.json':
                need(same(manifest['files'][name], {k: active[CENTRAL + '/' + name][k] for k in ('bytes', 'sha256')}), 'central source body identity')
        fixed[CENTRAL + '/BINDINGS.json'] = b_desc
        fixed[CENTRAL + '/SOURCE_MANIFEST.json'] = self.source
        self.rows = {k: {j: v[j] for j in ('bytes', 'sha256')} for k, v in sorted(fixed.items())}
        need(len(fixed) == 72, 'literal complete72 source closure')
        self.fixed_files = {v['path']: v for v in fixed.values()}
        self.manifest = manifest
        freeze = capture_json(self.instance['source_freeze'], self.budget)
        need(same(freeze, {'schema': 'neural081_portable_qualification_source_v1', 'task_id': TASK, 'files': self.rows}), 'exact complete qualification closure')
        own = active['tools/neural081_instance.py']
        need(canonical(str(Path(__file__).absolute())) == canonical(own['path']), 'stage uses genuine installed constructor')
        for desc in self.fixed_files.values():
            capture_bytes(desc, self.budget)
        origin = capture_json(self.instance['public_origin'], self.budget)
        need(origin.get('schema') == 'neural081_complete_public_original_source_manifest_v1' and
             self.instance['public_origin']['bytes'] == 48901 and self.instance['public_origin']['sha256'] ==
             '32705c641e263ac91c5f0b7f5ed60ac42cac9f9af87c07cd74e30cd1bcfee2f5', 'literal public origin')
        need(same({k: self.instance['public_origin'][k] for k in ('bytes', 'sha256')},
                  {k: release['public_manifest'][k] for k in ('bytes', 'sha256')}), 'original source provenance not rebound')

    def source_text(self, relative_path, cap=65536):
        relative(relative_path)
        path = str(self.root / relative_path)
        need(path in self.fixed_files, 'fixed source role only')
        self.budget.hold(4 * self.fixed_files[path]['bytes'] + 4096)
        return capture_bytes(self.fixed_files[path], self.budget, cap=cap).decode('utf-8')

    def _load_full(self, relative_path, name):
        if name in self._module_cache:
            return self._module_cache[name]
        body = self.source_text(relative_path, cap=BODY_CAP)
        # This is only used for the fixed stdlib common/gate/shared helper
        # bodies. No candidate, numerical, provider or scientific module loads.
        need(relative_path in (PARENT + '/program/common.py', CENTRAL + '/portable_gate.py',
                               'tools/neurobench_campaign.py', 'tools/neurobench_campaign_gate.py'), 'fixed metadata module loader')
        reserve = self.budget.hold(24 * len(body.encode()) + 16384)
        module = types.ModuleType(name)
        module.__file__ = str(self.root / relative_path)
        if relative_path == CENTRAL + '/portable_gate.py':
            dependencies = {'common': self._load_full(PARENT + '/program/common.py', '_portable_parent_common'),
                            'n081_shared_gate': self._load_full('tools/neurobench_campaign_gate.py', '_portable_shared_gate')}
            original_import = __import__
            def captured_import(name, globals=None, locals=None, fromlist=(), level=0):
                if level == 0 and name in dependencies:
                    return dependencies[name]
                return original_import(name, globals, locals, fromlist, level)
            import builtins
            module.__dict__['__builtins__'] = {**vars(builtins), '__import__': captured_import}
        try:
            exec(compile(body, module.__file__, 'exec'), module.__dict__)
        except BaseException:
            self.budget.release(reserve)
            raise
        # Retain the conservative source/code/module reservation for this
        # invocation, rather than count only shallow function objects.
        self._module_cache[name] = module
        return module

    def _metadata_functions(self):
        if 'parent_metadata' in self._module_cache:
            return self._module_cache['parent_metadata']
        c = self._load_full(PARENT + '/program/common.py', '_portable_parent_common')
        # Concrete bounded capture bridge replaces only filesystem I/O, keeping
        # the original exact constructors/admission predicates byte-for-byte AST.
        def captured(desc, budget, roots, *, empty=False):
            descriptor(desc)
            need(not empty, 'nonempty metadata only')
            p = self._deny(desc['path'])
            need(any(p == Path(r) or p.is_relative_to(Path(r)) for r in roots), 'original parent selected metadata root')
            need(any(p.is_relative_to(Path(r)) for r in self.roots['operator']) or
                 p.is_relative_to(self.here / 'operator-selections'), 'parent metadata does not acquire operand access')
            budget.check_clock()
            # capture_bytes charges the constructor; debit only the independent
            # original-clock admission ledger here to avoid duplicate charges.
            n = desc['bytes'] + 1
            need(budget.used['read_bytes'] + n <= budget.limits['read_bytes'], 'original metadata read reserve')
            budget.used['read_bytes'] += n
            raw = capture_bytes(desc, self.budget, cap=BODY_CAP)
            self._remember(desc)
            return raw
        c.capture = captured
        def captured_json(d, b, roots):
            reserve = self.budget.hold(80 * d['bytes'] + 16384)
            try:
                value = parse(captured(d, b, roots))
                retained = managed_size(value)
                need(retained <= reserve, 'bounded actual parent metadata parse')
            finally:
                self.budget.release(reserve)
            self.budget.hold(retained)
            return value
        c.capture_json = captured_json
        def selected(relative_path, names, globals_):
            text = self.source_text(relative_path, cap=BODY_CAP)
            self.budget.hold(32 * len(text.encode()) + 16384)
            tree = ast.parse(text)
            nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.Assign)) and
                     ((isinstance(n, ast.FunctionDef) and n.name in names) or
                      (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets)))]
            got = {n.name if isinstance(n, ast.FunctionDef) else n.targets[0].id for n in nodes}
            need(got == set(names), 'exact captured metadata definitions')
            exec(compile(ast.Module(body=nodes, type_ignores=[]), str(self.root / relative_path), 'exec'), globals_)
        custody = {'c': c, 'Path': Path}
        selected(PARENT + '/program/custody.py', ('disjoint_roots',), custody)
        auth = {'c': c, 'Path': Path, 'disjoint_roots': custody['disjoint_roots']}
        selected(PARENT + '/program/authority.py', ('ROLES', 'PHASES', 'ACTORS', 'run_allocation', 'admit'), auth)
        authority = types.SimpleNamespace(**auth)
        outer = {'c': c, 'Path': Path, 'authority': authority}
        selected(PARENT + '/program/outer.py', ('launch_request', 'admit_launch'), outer)
        result = {**{'authority.' + k: auth[k] for k in ('run_allocation', 'admit')},
                  **{'outer.' + k: outer[k] for k in ('launch_request', 'admit_launch')}}
        self._module_cache['parent_metadata'] = result
        return result

    def parent_call(self, name, *args, **kwargs):
        functions = self._metadata_functions()
        need(name in functions, 'fixed metadata function, no execute dispatch')
        if name == 'authority.run_allocation':
            need(len(args) == 2 and not kwargs, 'metadata-only run allocation excludes numeric index')
        self.budget.check()
        out = functions[name](*args, **kwargs)
        self.budget.check()
        return out

    def stage_budget(self):
        need(self._admission_budget is not None, 'selected original run required')
        self._admission_budget.check_clock()
        return self._admission_budget

    def _run_path(self, run):
        return canonical(self.roots['operator'][0]) / 'portable-runs' / pin(encode(run))['sha256']

    def select_run(self, run):
        need(self.stage == 'select-run' and self.run is None, 'one fresh run selection')
        budget = AdmissionBudget(self, run)
        self.parent_call('authority.run_allocation', run, budget)
        self.run_root = self._run_path(run)
        base = canonical(self.roots['operator'][0])
        ordinary_ancestors(base)
        need(not self.run_root.exists(), 'fresh separately selected run namespace')
        mkdirs(base, self.run_root, self.budget)
        self.run, self._admission_budget = run, budget
        self.run_descriptor = self.write('P', 'RUN.json', run)
        return self.run_descriptor

    def _write_root(self, domain):
        need(domain in WRITE_DOMAINS[self.stage], 'stage-specific writer domain')
        if domain == 'P':
            need(self.run_root is not None, 'run directory before write')
            return self.run_root
        return self.root / {'Q': QREL, 'R': RREL, 'V': VREL}[domain]

    def write(self, domain, relative_name, value):
        relative(relative_name)
        root = self._write_root(domain)
        if domain in ('Q', 'R'):
            need('/' not in relative_name, 'protected fixed metadata direct children')
        if domain == 'V':
            parts = Path(relative_name).parts
            if len(parts) == 2:
                digest(parts[0])
                need(parts[1] in ('GENERATION.json', 'TRANSACTION.json'), 'fixed registry generation artifact')
            else:
                need(len(parts) == 1 and relative_name.endswith('.json') and
                     any(relative_name.startswith(prefix) for prefix in ('intent-', 'result-', 'failure-', 'constructor-failure-')),
                     'fixed direct transaction observation')
        if domain == 'R':
            need(relative_name != 'APPROVAL_REGISTRY.json', 'constructor never issues approval registry')
        return publish_json(root, root / relative_name, value, self.budget)

    def import_record(self, desc, domain, relative_name):
        relative(relative_name)
        if domain == 'V':
            parts = Path(relative_name).parts
            need(len(parts) == 2 and parts[1] == 'PREIMAGE.json' and desc['path'] == str(self.root / JREL), 'fixed original registry preimage import')
            digest(parts[0])
            self.read(desc, scope='source', cap=131072)
        else:
            need(domain in ('Q', 'R') and '/' not in relative_name, 'fixed direct metadata import')
            self.read(desc, scope='operator')
        root = self._write_root(domain)
        raw = capture_bytes(desc, self.budget)
        copied = publish_bytes(root, root / relative_name, raw, self.budget)
        need(same(pin(raw), {k: copied[k] for k in ('bytes', 'sha256')}), 'exact issued bytes, no synthesized qualifier')
        return {'origin': desc, 'copy': copied}

    def channel_directories(self):
        need(self.stage == 'bind-channel' and self.run_root is not None, 'fixed channel writer')
        channel = self.run_root / 'channel'
        need(not channel.exists(), 'fresh current run channel')
        mkdirs(self.run_root, channel, self.budget)
        for name in ('requests', 'responses'):
            mkdirs(self.run_root, channel / name, self.budget)
        return {'request_root': str(channel / 'requests'), 'response_root': str(channel / 'responses')}

    def stage_record(self, relative_name, cap=1048576):
        """Discover only the two source-owned immutable current-run bindings.

        This is a bounded ordinary metadata capture, not an arbitrary operand
        discovery API. Stage predicates additionally join source/run/inputs.
        """
        need(relative_name in ('selection/OPERANDS.json', 'environment/BINDING.json') and
             self.run_root is not None, 'two fixed current-run resolution records')
        integer(cap, 1, 1048576)
        path = self._deny(self.run_root / relative_name)
        ordinary_ancestors(path)
        size = integer(path.lstat().st_size, 1, cap)
        self.budget.charge('read_bytes', size + 1)
        reserve = self.budget.hold(80 * size + 16384)
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        try:
            first = os.fstat(fd)
            need(stat.S_ISREG(first.st_mode) and first.st_nlink == 1 and first.st_size == size,
                 'ordinary exact resolution metadata')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                raw = stream.read(size + 1)
            after, named = os.fstat(fd), path.lstat()
            fields = ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
            need(len(raw) == size and all(getattr(first, k) == getattr(after, k) == getattr(named, k) for k in fields),
                 'complete stable current resolution record')
            desc = {'path': str(path), **pin(raw)}
            value = parse(raw)
            retained = managed_size(value) + managed_size(desc)
            need(retained <= reserve, 'bounded resolution metadata')
        finally:
            os.close(fd)
            self.budget.release(reserve)
        self.budget.hold(retained)
        self.budget.check()
        self._remember(desc)
        return {'descriptor': desc, 'document': value}

    def route(self, condition):
        return route_template(self.root, self.source, self.manifest['files']['entry.py']['sha256'], condition)

    def gate_context(self, review=None, invocation_operands=None):
        ctx = {'repo': self.root, 'here': self.here, 'source': self.source, 'parent_source': self.parent,
               'construction': self.construction, 'rows': self.rows, 'manifest': self.manifest, 'budget': self.budget}
        if review is not None:
            ctx['review'] = review
        if invocation_operands is not None:
            ctx['invocation_operands'] = invocation_operands
        return ctx

    def actual_argv(self, condition, program, output, review, other, *, python):
        for p in (program, output, review):
            canonical(p)
        integer(other)
        python = str(canonical(python))
        command = self.route(condition)['argv'][:]
        values = {'{python}': python, '{program}': program, '{output}': output,
                  '{review}': review, '{other_reserve_bytes}': str(other)}
        command = [values.get(v, v) for v in command]
        command[6] = str(self.here / 'entry.py')
        return command

    def generic_qualification(self, registry_doc):
        need(registry_doc.get('id') == TASK, 'one portable task qualification')
        conditions = exact(registry_doc['program_conditions'], (ALIAS,))
        campaign = self._load_full('tools/neurobench_campaign.py', '_portable_original_campaign')
        for condition, meta in (('default', registry_doc['program_execution']), (ALIAS, conditions[ALIAS])):
            need(same(meta['entrypoint'], self.route(condition)) and
                 same(meta['source_freeze'], rel_desc(self.root, self.instance['source_freeze'])), 'actual full task source/route qualification')
            verification = meta.get('verification', {})
            need(verification.get('status') == 'passed', 'actual independently supplied qualification required')
            # Bound every path and parse all three records before the unchanged
            # generic helper can follow a supplied locator. No WORK dependency.
            record_sizes = []
            for role in ('receipt', 'qualification', 'source_binding'):
                rel = relative(verification[role + '_path'])
                path = self.root / rel
                need(path.parent == self.root / QREL, 'fixed protected qualification namespace')
                ordinary_ancestors(path)
                size = integer(path.lstat().st_size, 1, BODY_CAP)
                d = {'path': str(path), 'bytes': size, 'sha256': digest(verification[role + '_sha256'])}
                self.read(d, scope='Q')
                record_sizes.append(size)
            # Conservative logical allowance includes actual helper rereads,
            # one possible maximum failing read and detection bytes. Reserving
            # is retained even if the original helper refuses.
            closure = sum(d['bytes'] + 1 for d in self.fixed_files.values())
            reserve = closure + sum(n + 1 for n in record_sizes) + self.instance['source_freeze']['bytes'] + 1
            reserve += 2 * (self.fixed_files[str(self.root / 'tools/neurobench_campaign_gate.py')]['bytes'] + 1)
            reserve += 2 * (self.manifest['files']['entry.py']['bytes'] + 1) + 16 * 2**20 + 1
            self.budget.charge('read_bytes', reserve)
            transient = self.budget.hold(16 * 2**20 + sum(80 * n for n in record_sizes) + 65536)
            try:
                selected = {**registry_doc, 'program_execution': meta}
                need(campaign.verified_program_runtime(self.root / JREL, selected, self.root) is True,
                     'real unchanged generic qualification predicate')
            finally:
                self.budget.release(transient)
            self.budget.check()
        return True

    def worker_manifest(self, kind, qualification_desc, installed_versions, numeric_source=None):
        need(kind in WORKER_ROLES, 'literal trusted worker kind')
        modules = {row['name']: row['source'] for row in self.parent_document['modules']}
        if kind == 'reference':
            need(numeric_source in [r['source'] for r in self.parent_document['auxiliary']], 'one exact full numerical source')
            modules['numeric'] = numeric_source
        else:
            need(numeric_source is None, 'numeric source only in reference role')
        rows = [{'name': n, 'source': modules[n]} for n in WORKER_ROLES[kind]]
        manifest = {'schema': 'neural081_' + kind + '_source_manifest_v1',
                    'entry': modules[WORKER_ENTRIES[kind]], 'bootstrap': modules['worker_bootstrap'], 'modules': rows,
                    'dependency_qualification': descriptor(qualification_desc), 'installed_versions': installed_versions}
        q = self.read(qualification_desc, scope='operator')
        fields = {
            'preparation': ('schema', 'status', 'source', 'installed_versions', 'image_identity', 'independent_issuer', 'physical_io_enforcement', 'memory_enforcement', 'annotation_authority'),
            'reference': ('schema', 'status', 'numeric_source', 'installed_versions', 'image_identity', 'independent_issuer', 'physical_io_enforcement', 'memory_enforcement'),
            'issuer': ('schema', 'status', 'source', 'source_members', 'installed_versions', 'physical_namespace', 'scm_rights', 'independent_issuer'),
            'grader': ('schema', 'status', 'source', 'source_members', 'installed_versions', 'image_identity', 'independent_issuer', 'protected_custody'),
        }
        exact(q, fields[kind])
        schemas = {'preparation': 'neural081_preparation_environment_qualification_v1', 'reference': 'neural081_numerical_environment_qualification_v1',
                   'issuer': 'neural081_projection_issuer_qualification_v1', 'grader': 'neural081_grader_environment_qualification_v1'}
        # Original reference request.source is the separately selected complete
        # numerical source; other trusted roles bind the parent source.
        need(q['schema'] == schemas[kind] and q['status'] == 'qualified' and
             same(q['numeric_source' if kind == 'reference' else 'source'], numeric_source if kind == 'reference' else self.parent) and
             same(q['installed_versions'], installed_versions), 'actual exact worker environment record')
        if kind == 'preparation':
            binding = self.stage_record('selection/OPERANDS.json')['document']
            need(same(binding['source'], self.parent) and same(binding['run'], self.run_descriptor), 'same input qualification run/source')
            inputs = self.read(binding['input'], scope='operator')
            need(same(q['annotation_authority'], inputs['preparation']['annotation_authority']), 'same actual annotation qualification as original G0 request')
        if kind in ('issuer', 'grader'):
            need(same(q['source_members'], [manifest['entry'], manifest['bootstrap'], *[r['source'] for r in rows]]), 'complete exact worker source roster')
        package_keys = {'preparation': ('numpy', 'mne'), 'reference': ('numpy', 'scipy', 'sklearn'), 'issuer': ('numpy',), 'grader': ('python',)}
        exact(installed_versions, package_keys[kind])
        for value in installed_versions.values():
            need(type(value) is str and value, 'actual selected dependency version')
        if kind == 'reference':
            need(same(installed_versions, {'numpy': '2.2.6', 'scipy': '1.15.3', 'sklearn': '1.6.1'}), 'literal historical dependency versions')
        for name in fields[kind]:
            if name not in ('schema', 'status', 'source', 'numeric_source', 'source_members', 'installed_versions'):
                descriptor(q[name])
        return manifest

    def recheck(self):
        self.budget.check()
        capture_bytes(self.instance_descriptor, self.budget)
        capture_bytes(self.instance['profile'], self.budget)
        for desc in self.fixed_files.values():
            capture_bytes(desc, self.budget)
        for key in ('source_freeze', 'selection'):
            capture_bytes(self.instance[key], self.budget)
        for desc in list(self._metadata_reads.values()):
            capture_bytes(desc, self.budget)
        if self.run_descriptor is not None:
            need(same(self.read(self.run_descriptor, scope='operator'), self.run), 'unchanged original run on completion')
            self.stage_budget().check_clock()
        self.budget.check()

    def activate_registry(self, plan):
        need(self.stage == 'activate-route', 'one-path selected activation stage')
        exact(plan, ('schema', 'task_id', 'construction', 'source', 'registry_path', 'preimage', 'preimage_archive', 'generation', 'record_copies'))
        need(plan['schema'] == 'neural081_portable_registry_transaction_v1' and plan['task_id'] == TASK and
             same(plan['construction'], self.construction) and same(plan['source'], self.source) and
             plan['registry_path'] == str(self.root / JREL), 'exact one-task registry transaction')
        old = descriptor(plan['preimage'])
        need(old['path'] == str(self.root / JREL), 'exact current J preimage')
        need(same(self._metadata_reads.get(old['path']), old),
             'selected J is the exact remembered preimage')
        archived = self.read(plan['preimage_archive'], scope='V')
        previous_raw = capture_bytes(old, self.budget)
        need(same(parse(previous_raw), archived) and same(pin(previous_raw), {k: plan['preimage_archive'][k] for k in ('bytes', 'sha256')}), 'exact archived preimage')
        generation = self.read(plan['generation'], scope='V')
        self.generic_qualification(generation)
        expected = parse(previous_raw)
        for name in ('program_execution',):
            expected[name]['verification'] = generation[name]['verification']
        expected['program_conditions'][ALIAS]['verification'] = generation['program_conditions'][ALIAS]['verification']
        need(same(expected, generation), 'only two explicit verification fields change')
        need(type(plan['record_copies']) is list and len(plan['record_copies']) == 3, 'three separately issued qualification copies')
        for row, role in zip(plan['record_copies'], ('receipt', 'qualification', 'source_binding')):
            exact(row, ('role', 'origin', 'copy'))
            need(row['role'] == role, 'ordered exact qualification roles')
            self.read(row['origin'], scope='operator')
            self.read(row['copy'], scope='Q')
            need(same({k: row['origin'][k] for k in ('bytes', 'sha256')}, {k: row['copy'][k] for k in ('bytes', 'sha256')}), 'unchanged independently issued bytes')
        token = pin(encode(plan))['sha256']
        target, transaction_root = self.root / JREL, self.root / VREL
        ordinary_ancestors(transaction_root)
        ordinary_ancestors(target.parent)
        vfd = os.open(transaction_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        tfd = None

        def close_directory(fd):
            original_error = sys.exc_info()[0] is not None
            try:
                os.close(fd)
            except BaseException:
                if not original_error:
                    raise

        try:
            tfd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            v_identity, t_identity = os.fstat(vfd), os.fstat(tfd)
            need(v_identity.st_dev == t_identity.st_dev, 'same filesystem for atomic V to J replacement')

            def check_directories():
                for path, fd, identity in ((transaction_root, vfd, v_identity),
                                           (target.parent, tfd, t_identity)):
                    ordinary_ancestors(path)
                    named, held = path.lstat(), os.fstat(fd)
                    need(stat.S_ISDIR(named.st_mode) and stat.S_ISDIR(held.st_mode) and
                         (named.st_dev, named.st_ino) == (identity.st_dev, identity.st_ino) ==
                         (held.st_dev, held.st_ino), 'unchanged held transaction directories')

            check_directories()
            intent = self.write('V', 'intent-' + token + '.json',
                                {'schema': 'neural081_portable_registry_intent_v1',
                                 'plan': plan, 'automatic_retry': False})
            temporary = transaction_root / ('.portable-' + token + '.json')
            raw = capture_bytes(plan['generation'], self.budget)
            # All lock/staging/observation bodies are inside V. Only the exact
            # selected J replacement mutates a namespace outside V.
            lock = transaction_root / '.portable-registry.lock'
            check_directories()
            fd = os.open(lock.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=vfd)
            lock_identity = os.fstat(fd)
            os.close(fd)
            changed = False
            try:
                os.fsync(vfd)
                self.budget.check()
                check_directories()
                publish_bytes(transaction_root, temporary, raw, self.budget)
                need(capture_bytes(old, self.budget) == previous_raw,
                     'original preimage immediately before replacement')
                need(same(self._metadata_reads.get(old['path']), old),
                     'only selected remembered J may transition')
                check_directories()
                self.budget.check()
                os.replace(temporary.name, target.name, src_dir_fd=vfd, dst_dir_fd=tfd)
                changed = True
                # Cross-directory rename requires both namespace flushes.
                os.fsync(vfd)
                os.fsync(tfd)
                check_directories()
                self.budget.check()
                current = {'path': str(target), **pin(raw)}
                need(capture_bytes(current, self.budget) == raw, 'exact durable new registry')
                # The original J is retained in the immutable plan/archive.
                # No other remembered read changes; both final rechecks now
                # authenticate this one explicitly selected current identity.
                need(same(self._metadata_reads.get(old['path']), old),
                     'unchanged selected remembered J until durable transition')
                self._metadata_reads[old['path']] = dict(current)
                result = self.write('V', 'result-' + token + '.json',
                                    {'schema': 'neural081_portable_registry_result_v1',
                                     'intent': intent, 'preimage': old, 'postimage': current,
                                     'runtime_executed': False})
                self.budget.check()
                return result
            except BaseException:
                # Keep original intent, temporary and current J as found. Any
                # failed sync/readback/record leaves an unknown result; no retry.
                try:
                    self.write('V', 'failure-' + token + '.json',
                               {'schema': 'neural081_portable_registry_failure_v1',
                                'intent': intent, 'replacement_returned': changed,
                                'final_state_requires_independent_inspection': True,
                                'automatic_retry': False})
                except BaseException:
                    pass
                raise
            finally:
                original_error = sys.exc_info()[0] is not None
                try:
                    check_directories()
                    info = os.stat(lock.name, dir_fd=vfd, follow_symlinks=False)
                    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size == 0 and
                         (info.st_dev, info.st_ino) == (lock_identity.st_dev, lock_identity.st_ino),
                         'exact owned transaction lock at close')
                    os.unlink(lock.name, dir_fd=vfd)
                    os.fsync(vfd)
                    self.budget.check()
                except BaseException:
                    if not original_error:
                        raise
        finally:
            try:
                if tfd is not None:
                    close_directory(tfd)
            finally:
                close_directory(vfd)


# ---- Byte-identical reviewed source fragment ----

"""Finite portable metadata construction; no scientific or qualification execution.

This exact fragment is assembled into the one-file constructor. Context methods
are concrete owner machinery, not caller supplied plugins. Independently issued
records are only captured/checked/copied. No credential or private operand body
is read, and no passing issuer verdict is constructed here.
"""
import re
import ipaddress

_STAGE_TASK = 'NEURAL-081'
_STAGE_PHASES = ('G0', 'G1', 'G2', 'G3', 'G5')
_STAGE_ROLES = ('input', 'access', 'native', 'physical_custody', 'provider', 'resources', 'observer')
_STAGE_ACTORS = ('controller', 'outer', 'preparer', 'reference', 'author', 'issuer', 'candidate', 'grader')
_STAGE_COUNTS = ('read_bytes', 'write_bytes', 'native_cpu_seconds', 'native_processes', 'host_processes', 'provider_requests', 'provider_tokens', 'stream_bytes', 'tool_processes')
_STAGE_CONDITIONS = ('default', 'full10_instructed_excerpt_v1')
_STAGE_PEOPLE = ('P01', 'P04', 'P05', 'P06', 'P07', 'P09', 'P11', 'P12', 'P13', 'P14')
_STAGE_CONTROLLER_KEYS = ('schema', 'source', 'run', 'channel', 'output_root', 'protected_roots', 'native_config', 'preparation', 'preparation_manifest', 'reference_manifest', 'issuer_manifest', 'issuer_worker_limits', 'issuer_sandbox', 'host_python', 'host_environment', 'provider_config', 'replication_seeds', 'public_protocol', 'tool_source', 'candidate_runner', 'numeric_source', 'grade_manifest', 'grade_worker_io', 'host_metadata_capacity_bytes')
_STAGE_REVIEW_KEYS = ('schema', 'task_id', 'condition', 'central_source', 'parent_source', 'construction', 'registry', 'program', 'run', 'local_declaration', 'origin', 'normal_endpoint', 'central_limits', 'total_limits', 'external_limits', 'memory', 'roots', 'launch')
_STAGE_CAPABILITIES = {'physical_root_disjointness': True, 'operator_namespace_immutable': True, 'single_credential_boundary': True, 'actual_linux_procfs_observer': True, 'parent_and_central_interpreters': True, 'complete_graph_readback_resources': True, 'inherited_address_space_limit': True, 'independent_central_exit_observer_required': True, 'statistical_semantic_reviewer': False}


def _stage_object(value, schema, keys):
    exact(value, keys)
    need(value['schema'] == schema and value.get('task_id', _STAGE_TASK) == _STAGE_TASK, 'exact portable metadata schema/task')
    return value


def _stage_descriptor(value):
    descriptor(value)
    integer(value['bytes'], 1)
    return value


def _stage_path_descriptor(value, path):
    _stage_descriptor(value)
    need(value['path'] == str(path), 'source-owned exact metadata path')
    return value


def _stage_fixed(ctx, relative_name):
    path = str(ctx.root / relative_name)
    need(path in ctx.fixed_files, 'exact selected fixed source role')
    return _stage_path_descriptor(ctx.fixed_files[path], path)


def _stage_bound_run(ctx):
    need(ctx.run is not None and ctx.run_root is not None, 'original selected run required for immutable operand resolution')
    captured = ctx.stage_record('selection/OPERANDS.json')
    exact(captured, ('descriptor', 'document'))
    _stage_path_descriptor(captured['descriptor'], ctx.run_root/'selection/OPERANDS.json')
    row = captured['document']
    _stage_object(row, 'neural081_portable_run_operands_v1', ('schema', 'task_id', 'construction', 'source', 'run', 'input', 'execution_selection'))
    for key, expected in (('construction', ctx.construction), ('source', ctx.parent), ('run', ctx.run_descriptor)):
        need(same(row[key], expected), 'immutable source/run operand binding ' + key)
    _stage_descriptor(row['input']); _stage_descriptor(row['execution_selection'])
    return row


def _stage_profile(ctx, field, supplied=None):
    need(field in ('input_records', 'execution_selection', 'environment_records'), 'finite profile operand roles')
    original = ctx.profile[field]
    unresolved = same(original, {'disposition': 'not_supplied'})
    if not unresolved:
        _stage_descriptor(original)
    if supplied is not None:
        selected = _stage_descriptor(supplied)
    elif ctx.run is None:
        need(not unresolved, 'unresolved operand requires an explicit selected stage input')
        selected = original
    else:
        bound = _stage_bound_run(ctx)
        if field != 'environment_records':
            selected = bound['input' if field == 'input_records' else 'execution_selection']
        else:
            captured = ctx.stage_record('environment/BINDING.json')
            exact(captured, ('descriptor', 'document'))
            _stage_path_descriptor(captured['descriptor'], ctx.run_root/'environment/BINDING.json')
            row = captured['document']
            _stage_object(row, 'neural081_portable_environment_binding_v1', ('schema', 'task_id', 'source', 'central_source', 'run', 'input', 'execution_selection', 'environment_records', 'artifacts', 'numeric_source'))
            for key, expected in (('source', ctx.parent), ('central_source', ctx.source), ('run', ctx.run_descriptor), ('input', bound['input']), ('execution_selection', bound['execution_selection'])):
                need(same(row[key], expected), 'immutable complete environment lineage ' + key)
            selected = _stage_descriptor(row['environment_records'])
    need(unresolved or same(original, selected), 'an initially pinned profile operand cannot change')
    return ctx.read(selected, scope='input'), selected


def _stage_roots(ctx, name):
    value = ctx.profile['root_roles'][name]
    rows = value if type(value) is list else [value]
    need(type(rows) is list and 0 < len(rows) <= 32, 'bounded complete root list')
    for path in rows:
        canonical(path)
    need(len(set(rows)) == len(rows), 'unique selected root list')
    return rows


def _stage_within(path, roots):
    p = canonical(path)
    need(any(p == canonical(r) or p.is_relative_to(canonical(r)) for r in roots), 'descriptor belongs to selected physical role')
    return p


def _stage_io(value):
    exact(value, ('read_bytes', 'write_bytes'))
    for v in value.values():
        integer(v, 1)
    return value


def _stage_limits(value, seconds):
    exact(value, ('seconds', *_STAGE_COUNTS))
    need(type(value['seconds']) in (int, float) and finite(value['seconds'], 0) == seconds, 'unchanged original interval')
    for key in _STAGE_COUNTS:
        integer(value[key])
    return value


def _stage_input(ctx, supplied=None):
    row, desc = _stage_profile(ctx, 'input_records', supplied)
    _stage_object(row, 'neural081_portable_input_record_v1', ('schema', 'task_id', 'preparation', 'N', 'census_evidence', 'physical_input_evidence'))
    integer(row['N'], 120, 100000)
    for name in ('census_evidence', 'physical_input_evidence'):
        _stage_descriptor(row[name])
    p = row['preparation']
    exact(p, ('inventory', 'release_root', 'raw_files', 'key', 'protocol_source', 'annotation_authority', 'worker_io', 'protected_roots'))
    for name in ('inventory', 'key', 'protocol_source', 'annotation_authority'):
        _stage_descriptor(p[name])
    need(p['key']['bytes'] == 32, 'exact key extent; body never opened')
    _stage_within(p['key']['path'], _stage_roots(ctx, 'secret'))
    release = _stage_within(p['release_root'], _stage_roots(ctx, 'raw'))
    need(type(p['raw_files']) is list and len(p['raw_files']) == 11, 'all eleven original release descriptors')
    expected = [name + '-raw.fif' for name in _STAGE_PEOPLE] + ['README.md']
    for d, name in zip(p['raw_files'], expected):
        _stage_path_descriptor(d, release / name)
    need(type(p['worker_io']) is list and len(p['worker_io']) == 10, 'ten complete worker reservations')
    for io in p['worker_io']:
        _stage_io(io)
    need(same(p['protected_roots'], _stage_roots(ctx, 'protected')), 'exact complete protected roots')
    return row, desc


def _stage_selection(ctx, supplied=None, input_row=None):
    s, desc = _stage_profile(ctx, 'execution_selection', supplied)
    _stage_object(s, 'neural081_portable_execution_selection_v1', ('schema', 'task_id', 'condition', 'origin', 'whole_limits', 'phase_limits', 'outer_limits', 'issuer_limits', 'request_caps', 'artifact_caps', 'central_limits', 'external_limits', 'total_limits', 'memory', 'worker_io', 'replication_seeds', 'channel', 'outputs', 'bootstrap_read_cap'))
    need(s['condition'] in _STAGE_CONDITIONS and type(s['origin']) is float, 'literal complete condition and original float origin')
    finite(s['origin'], 0)
    if input_row is None:
        input_row, _ = _stage_input(ctx)
    n = input_row['N']
    seconds = 10*3600 + 3680*7200 + 3680*900 + 20*300 + 12*n*480 + 3600 + 120*(54*n+27) + 24*60 + 86400 + 60*(7391+54*n+24)
    for name in ('whole_limits', 'outer_limits', 'issuer_limits', 'central_limits', 'external_limits', 'total_limits'):
        _stage_limits(s[name], seconds)
    exact(s['phase_limits'], _STAGE_PHASES)
    exact(s['request_caps'], _STAGE_PHASES)
    exact(s['artifact_caps'], _STAGE_PHASES)
    for phase in _STAGE_PHASES:
        _stage_limits(s['phase_limits'][phase], seconds)
        integer(s['request_caps'][phase], 1)
        integer(s['artifact_caps'][phase], 1)
    for key in _STAGE_COUNTS:
        need(sum(v[key] for v in [*s['phase_limits'].values(), s['outer_limits'], s['issuer_limits']]) <= s['whole_limits'][key], 'all parent shares fit original whole')
        need(s['total_limits'][key] >= s['whole_limits'][key] + s['central_limits'][key] + s['external_limits'][key], 'full parent/central/external allocation')
    need(s['whole_limits']['host_processes'] >= 3 and s['issuer_limits']['host_processes'] >= 1, 'complete original parent hosts')
    need(s['central_limits']['host_processes'] == 1 and all(s['central_limits'][k] == 0 for k in ('native_cpu_seconds', 'native_processes', 'provider_requests', 'provider_tokens', 'tool_processes')), 'central adds one host and no scientific operations')
    need(s['total_limits']['host_processes'] >= 4 + s['external_limits']['host_processes'], 'four task hosts plus external observation')
    m = s['memory']
    exact(m, ('address_space_bytes', 'readback_live_bytes', 'metadata_cap_bytes', 'other_reserve_bytes'))
    integer(m['address_space_bytes'], 512*2**20, 256*2**30)
    integer(m['readback_live_bytes'], 64*2**20, m['address_space_bytes'])
    integer(m['metadata_cap_bytes'], 32768, m['readback_live_bytes']//8)
    integer(m['other_reserve_bytes'])
    need(m['readback_live_bytes'] + m['other_reserve_bytes'] + 512*2**20 <= m['address_space_bytes'], 'separate live memory envelopes')
    exact(s['worker_io'], ('preparation', 'grade', 'host_metadata_capacity_bytes'))
    need(same(s['worker_io']['preparation'], input_row['preparation']['worker_io']), 'same actual ten preparation shares')
    _stage_io(s['worker_io']['grade'])
    integer(s['worker_io']['host_metadata_capacity_bytes'], 12*n*16384 + 7380*8192 + 64*2**20)
    exact(s['replication_seeds'], ('r0', 'r1', 'r2'))
    for seed in s['replication_seeds'].values():
        need(seed is None or type(seed) is int and 0 <= seed < 2**31, 'selected seed or explicit unknown determinism')
    exact(s['channel'], ('maximum_response_bytes', 'poll_seconds'))
    integer(s['channel']['maximum_response_bytes'], 1, 2**20)
    need(.001 <= finite(s['channel']['poll_seconds']) <= 1, 'original bounded channel polling')
    exact(s['outputs'], ('output',))
    _stage_within(s['outputs']['output'], _stage_roots(ctx, 'output'))
    integer(s['bootstrap_read_cap'], 1, 64*2**20)
    run = {'schema': 'neural081_complete_run_v1', 'origin': s['origin'], 'normal_endpoint': s['origin'] + seconds, 'whole_limits': s['whole_limits'], 'phase_limits': s['phase_limits'], 'outer_limits': s['outer_limits'], 'issuer_limits': s['issuer_limits'], 'N': n, 'request_caps': s['request_caps'], 'artifact_caps': s['artifact_caps'], 'status': 'selected_not_qualified_by_this_record'}
    if ctx.run is not None:
        need(same(run, ctx.run), 'profile and captured original run agree')
    return s, desc, run


def _stage_host(value, memory):
    exact(value, ('central_python', 'parent_python', 'host_environment', 'address_space_bytes', 'inherited_address_space_bytes', 'qualification'))
    canonical(value['central_python']); canonical(value['parent_python'])
    env = value['host_environment']
    exact(env, ('PATH', 'PYTHONDONTWRITEBYTECODE'))
    need(type(env['PATH']) is str and env['PATH'] and '\0' not in env['PATH'] and env['PYTHONDONTWRITEBYTECODE'] == '1', 'clean selected environment without credential value')
    need(same(value['address_space_bytes'], memory['address_space_bytes']) and same(value['inherited_address_space_bytes'], memory['address_space_bytes']), 'exact selected/inherited address space')
    _stage_descriptor(value['qualification'])


def _stage_native(v):
    exact(v, ('engine_socket', 'engine_api_version', 'image_digest', 'python', 'user', 'pids_limit', 'cpus', 'tmpfs_bytes', 'stream_cap_bytes', 'workspace_cap_bytes', 'workspace_entry_cap', 'cleanup_seconds', 'poll_seconds', 'engine_response_cap_bytes', 'engine_control_seconds', 'qualification'))
    exact(v['engine_socket'], ('path', 'device', 'inode', 'owner_uid'))
    canonical(v['engine_socket']['path'])
    for key in ('device', 'inode', 'owner_uid'):
        integer(v['engine_socket'][key])
    need(type(v['engine_api_version']) is str and re.fullmatch(r'v1\.\d{2}', v['engine_api_version']), 'exact engine API')
    need(type(v['image_digest']) is str and re.fullmatch('sha256:[0-9a-f]{64}', v['image_digest']), 'immutable installed image')
    canonical(v['python'])
    need(type(v['user']) is str and re.fullmatch(r'[1-9]\d*:\d+', v['user']), 'explicit nonroot UID:GID')
    for key, expected in (('pids_limit', 1), ('cpus', 1), ('stream_cap_bytes', 262144), ('cleanup_seconds', 120)):
        need(type(v[key]) is int and v[key] == expected, 'original fixed native ' + key)
    for key in ('tmpfs_bytes', 'workspace_cap_bytes', 'workspace_entry_cap', 'engine_response_cap_bytes'):
        integer(v[key], 1)
    need(v['engine_response_cap_bytes'] <= 2**21, 'bounded engine response')
    for key in ('poll_seconds', 'engine_control_seconds'):
        need(0 < finite(v[key]) <= 30, 'bounded engine control interval')
    exact(v['qualification'], ('engine', 'clock', 'namespace', 'physical_io'))
    for d in v['qualification'].values():
        _stage_descriptor(d)


def _stage_provider(v):
    exact(v, ('resolved_ip', 'endpoint', 'model', 'api_key_env', 'max_completion_tokens', 'prompt_token_reservation', 'request_cap_bytes', 'response_cap_bytes', 'request_timeout_seconds', 'seed', 'tokenizer_contract', 'transcript_cap_bytes'))
    need(v['endpoint'] == 'https://api.openai.com/v1/chat/completions', 'original literal provider endpoint')
    need(type(v['resolved_ip']) is str and str(ipaddress.ip_address(v['resolved_ip'])) == v['resolved_ip'], 'canonical independently selected literal IP')
    need(type(v['model']) is str and v['model'] and type(v['api_key_env']) is str and re.fullmatch('[A-Z][A-Z0-9_]{1,127}', v['api_key_env']), 'model and single credential NAME only')
    for key in ('max_completion_tokens', 'prompt_token_reservation', 'request_cap_bytes', 'response_cap_bytes', 'transcript_cap_bytes'):
        integer(v[key], 1)
    need(v['max_completion_tokens'] <= 4096 and v['prompt_token_reservation'] == 32768 and v['response_cap_bytes'] <= 2**21 and v['transcript_cap_bytes'] <= 2**24, 'original token/HTTP/transcript caps')
    need(0 < finite(v['request_timeout_seconds']) <= 120, 'original provider timeout')
    need(v['seed'] is None or type(v['seed']) is int and 0 <= v['seed'] < 2**31, 'selected provider seed')
    t = v['tokenizer_contract']
    exact(t, ('schema', 'model', 'package_version', 'encoding_name', 'pattern', 'vocabulary', 'special_tokens', 'request_prefix_tokens', 'per_message_tokens', 'assistant_prefix_tokens', 'qualification'))
    need(t['schema'] == 'neural081_plain_chat_tokenizer_contract_v1' and t['model'] == v['model'], 'exact source tokenizer contract/model')
    for key in ('package_version', 'encoding_name', 'pattern'):
        need(type(t[key]) is str and t[key], 'literal tokenizer metadata')
    for key in ('vocabulary', 'qualification'):
        _stage_descriptor(t[key])
    need(type(t['special_tokens']) is dict and all(type(k) is str and type(x) is int and x >= 0 for k, x in t['special_tokens'].items()), 'typed token table, never body loaded')
    for key in ('request_prefix_tokens', 'per_message_tokens', 'assistant_prefix_tokens'):
        integer(t[key])


def _stage_environment_records(ctx, supplied=None):
    e, desc = _stage_profile(ctx, 'environment_records', supplied)
    _stage_object(e, 'neural081_portable_environment_records_v1', ('schema', 'task_id', 'host', 'worker_environments', 'native', 'provider', 'issuer', 'external_observer'))
    s, _, _ = _stage_selection(ctx)
    _stage_host(e['host'], s['memory'])
    _stage_native(e['native']); _stage_provider(e['provider'])
    need(e['provider']['api_key_env'] not in e['host']['host_environment'], 'credential absent from stored environment')
    exact(e['worker_environments'], ('preparation', 'reference', 'issuer', 'grader'))
    for kind, row in e['worker_environments'].items():
        exact(row, ('qualification', 'installed_versions', 'numeric_role') if kind == 'reference' else ('qualification', 'installed_versions'))
        _stage_descriptor(row['qualification'])
        need(type(row['installed_versions']) is dict and all(type(k) is str and type(v) is str and v for k, v in row['installed_versions'].items()), 'literal independently supplied installed versions')
    need(e['worker_environments']['reference']['numeric_role'] in ('r1', 'r2'), 'one fixed numerical implementation')
    need(same(e['worker_environments']['reference']['installed_versions'], {'numpy': '2.2.6', 'scipy': '1.15.3', 'sklearn': '1.6.1'}), 'original numerical package contract')
    exact(e['issuer'], ('worker_limits', 'sandbox'))
    _stage_limits(e['issuer']['worker_limits'], s['whole_limits']['seconds'])
    for key in _STAGE_COUNTS:
        need(e['issuer']['worker_limits'][key] <= s['issuer_limits'][key], 'issuer worker fits its independent share')
    sandbox = e['issuer']['sandbox']
    exact(sandbox, ('platform', 'machine', 'minimum_landlock_abi', 'memory_bytes', 'cpu_seconds', 'max_open_files'))
    need(sandbox['platform'] == 'Linux' and sandbox['machine'] in ('x86_64', 'aarch64'), 'supported concrete issuer ABI')
    for key in ('minimum_landlock_abi', 'memory_bytes', 'cpu_seconds', 'max_open_files'):
        integer(sandbox[key], 1)
    need(sandbox['minimum_landlock_abi'] >= 3, 'Landlock truncate/right coverage')
    _stage_descriptor(e['external_observer'])
    return e, desc


def stage_select_run(ctx, payload):
    exact(payload, ('input', 'selection'))
    need(ctx.run is None, 'select-run cannot reset a selected run')
    inputs, input_desc = _stage_input(ctx, payload['input'])
    selected, selection_desc, run = _stage_selection(ctx, payload['selection'], inputs)
    ctx.recheck()
    run_desc = ctx.select_run(run)
    operands = ctx.write('P', 'selection/OPERANDS.json', {'schema': 'neural081_portable_run_operands_v1', 'task_id': _STAGE_TASK, 'construction': ctx.construction, 'source': ctx.parent, 'run': run_desc, 'input': input_desc, 'execution_selection': selection_desc})
    requests = {'schema': 'neural081_portable_role_requests_v1', 'task_id': _STAGE_TASK, 'source': ctx.parent, 'source_files': ctx.source_files, 'run': run_desc, 'input': input_desc, 'execution_selection': selection_desc, 'roles': list(_STAGE_ROLES), 'request_binding': 'later-independent-exact-request-v1', 'qualification_emitted': False}
    result = ctx.write('P', 'selection/ROLE_REQUESTS.json', requests)
    ctx.recheck()
    return {'run': run_desc, 'operands': operands, 'role_requests': result, 'qualified': False}


def stage_bind_environment(ctx, payload):
    exact(payload, ('records',))
    need(ctx.run is not None, 'selected original run required')
    e, origin = _stage_environment_records(ctx, payload['records'])
    inputs, input_desc = _stage_input(ctx)
    s, selection_desc, _ = _stage_selection(ctx, input_row=inputs)
    numeric = _stage_fixed(ctx, 'neural081/parent/references/' + e['worker_environments']['reference']['numeric_role'] + '/numeric.py')
    manifests = {}
    # All external qualifications are checked before publishing any bundle.
    for kind in ('preparation', 'reference', 'issuer', 'grader'):
        row = e['worker_environments'][kind]
        manifests[kind] = ctx.worker_manifest(kind, row['qualification'], row['installed_versions'], numeric_source=numeric if kind == 'reference' else None)
    ctx.recheck()
    published = {('preparation_source' if kind == 'preparation' else kind): ctx.write('P', 'environment/' + kind.upper() + '-SOURCE.json', value) for kind, value in manifests.items()}
    for kind, value in (('native_config', e['native']), ('provider_config', e['provider']), ('preparation', inputs['preparation'])):
        published[kind] = ctx.write('P', 'environment/' + kind.upper() + '.json', value)
    bundle = {'schema': 'neural081_portable_environment_binding_v1', 'task_id': _STAGE_TASK, 'source': ctx.parent, 'central_source': ctx.source, 'run': ctx.run_descriptor, 'input': input_desc, 'execution_selection': selection_desc, 'environment_records': origin, 'artifacts': published, 'numeric_source': numeric}
    output = ctx.write('P', 'environment/BINDING.json', bundle)
    ctx.recheck()
    return {'environment': output, 'artifacts': published, 'qualification_generated': False}


def _stage_environment(ctx, desc):
    _stage_path_descriptor(desc, ctx.run_root / 'environment/BINDING.json')
    bundle = ctx.read(desc, scope='operator')
    _stage_object(bundle, 'neural081_portable_environment_binding_v1', ('schema', 'task_id', 'source', 'central_source', 'run', 'input', 'execution_selection', 'environment_records', 'artifacts', 'numeric_source'))
    bound = _stage_bound_run(ctx)
    for key, expected in (('source', ctx.parent), ('central_source', ctx.source), ('run', ctx.run_descriptor), ('input', bound['input']), ('execution_selection', bound['execution_selection'])):
        need(same(bundle[key], expected), 'exact environment binding ' + key)
    e, environment_desc = _stage_environment_records(ctx)
    need(same(bundle['environment_records'], environment_desc), 'same immutable selected environment record')
    inputs, _ = _stage_input(ctx)
    numeric = _stage_fixed(ctx, 'neural081/parent/references/' + e['worker_environments']['reference']['numeric_role'] + '/numeric.py')
    need(same(bundle['numeric_source'], numeric), 'same fixed numerical source')
    a = bundle['artifacts']
    exact(a, ('preparation_source', 'preparation', 'reference', 'issuer', 'grader', 'native_config', 'provider_config'))
    # Reconstruct every role from earlier exact records; a descriptor in the
    # bundle cannot silently substitute another generated configuration.
    expected = {'preparation': inputs['preparation'], 'native_config': e['native'], 'provider_config': e['provider']}
    names = {'preparation': 'PREPARATION.json', 'native_config': 'NATIVE_CONFIG.json', 'provider_config': 'PROVIDER_CONFIG.json'}
    for kind in ('preparation', 'reference', 'issuer', 'grader'):
        row = e['worker_environments'][kind]
        name = 'preparation_source' if kind == 'preparation' else kind
        expected[name] = ctx.worker_manifest(kind, row['qualification'], row['installed_versions'], numeric_source=numeric if kind == 'reference' else None)
        names[name] = kind.upper() + '-SOURCE.json'
    for name in expected:
        _stage_path_descriptor(a[name], ctx.run_root/'environment'/names[name])
        need(same(ctx.read(a[name], scope='operator'), expected[name]), 'complete exact environment artifact ' + name)
    return bundle, e, inputs


def _stage_registry_templates(ctx, desc):
    path = canonical(desc['path'])
    need(path.is_relative_to(ctx.run_root / 'authority'), 'selected run authority namespace')
    r = ctx.read(_stage_descriptor(desc), scope='operator')
    exact(r, ('schema', 'source', 'run', 'templates', 'issuers', 'selected_actual'))
    need(r['schema'] == 'neural081_qualification_registry_v1' and r['selected_actual'] is True and same(r['source'], ctx.parent) and same(r['run'], ctx.run_descriptor), 'actual separately issued source/run registry')
    exact(r['templates'], _STAGE_ROLES); exact(r['issuers'], _STAGE_ROLES)
    templates = {}
    for role in _STAGE_ROLES:
        td = _stage_descriptor(r['templates'][role])
        need(canonical(td['path']).is_relative_to(ctx.run_root / 'authority'), 'only protected selected role metadata')
        t = ctx.read(td, scope='operator')
        exact(t, ('schema', 'role', 'source', 'run', 'issuer', 'status', 'phases', 'actors', 'request_binding', 'conditions'))
        need(t['schema'] == 'neural081_qualification_template_v1' and t['role'] == role and t['status'] == 'qualified' and same(t['source'], ctx.parent) and same(t['run'], ctx.run_descriptor), 'actual template source/run/role')
        need(type(r['issuers'][role]) is list and t['issuer'] in r['issuers'][role], 'externally admitted role issuer')
        need(type(t['phases']) is list and len(set(t['phases'])) == len(t['phases']) and set(t['phases']) == set(_STAGE_PHASES), 'complete phase coverage')
        need(type(t['actors']) is list and len(set(t['actors'])) == len(t['actors']) and set(t['actors']) <= set(_STAGE_ACTORS) and {'controller', 'outer'} <= set(t['actors']), 'actual whole-program actor coverage')
        need(t['request_binding'] == 'later-independent-exact-request-v1' and type(t['conditions']) is dict and t['conditions'], 'acyclic nonempty independent conditions')
        templates[role] = t['conditions']
    need(templates['access'].get('policy') == 'single_query_transductive_v4' and templates['access'].get('statistical_semantic_reviewer') is None, 'matched query adaptation without hidden reviewer')
    return r, templates


def _stage_join(conditions, role, key, value):
    need(same(conditions[role].get(key), value), 'independent ' + role + '/' + key + ' join')


def stage_bind_channel(ctx, payload):
    exact(payload, ('environment', 'registry'))
    bundle, e, inputs = _stage_environment(ctx, payload['environment'])
    _, q = _stage_registry_templates(ctx, payload['registry'])
    a = bundle['artifacts']
    s, _, _ = _stage_selection(ctx, input_row=inputs)
    _stage_join(q, 'input', 'preparation_selection', a['preparation'])
    _stage_join(q, 'native', 'configuration', a['native_config'])
    _stage_join(q, 'native', 'preparation_manifest', a['preparation_source'])
    _stage_join(q, 'native', 'reference_manifest', a['reference'])
    _stage_join(q, 'native', 'grade_manifest', a['grader'])
    _stage_join(q, 'access', 'operative_numeric_source', bundle['numeric_source'])
    _stage_join(q, 'physical_custody', 'issuer_manifest', a['issuer'])
    _stage_join(q, 'physical_custody', 'issuer_sandbox', e['issuer']['sandbox'])
    for key in ('ordinary_controller_descriptor_only', 'one_persistent_current_fd_issuer', 'candidate_namespace_qualified'):
        need(q['physical_custody'].get(key) is True, 'actual physical qualification: ' + key)
    for role in ('observer', 'physical_custody'):
        _stage_join(q, role, 'host_python', e['host']['parent_python'])
        _stage_join(q, role, 'host_environment', e['host']['host_environment'])
    _stage_join(q, 'observer', 'entry', ctx.parent_document['entry'])
    _stage_join(q, 'provider', 'configuration', a['provider_config'])
    _stage_join(q, 'provider', 'launch_credential_name', e['provider']['api_key_env'])
    _stage_join(q, 'provider', 'resolved_ip', e['provider']['resolved_ip'])
    _stage_join(q, 'provider', 'tokenizer_qualification', e['provider']['tokenizer_contract']['qualification'])
    need(q['provider'].get('exact_plain_chat_framing') is True, 'real tokenizer/framing qualification')
    # Grade manifest/native and all later exact request receipts are checked by
    # the unchanged G5/runtime path as well; no future receipt is manufactured.
    ctx.recheck()
    dirs = ctx.channel_directories()
    exact(dirs, ('request_root', 'response_root'))
    need(dirs == {'request_root': str(ctx.run_root/'channel/requests'), 'response_root': str(ctx.run_root/'channel/responses')}, 'exact source-owned channel directories')
    channel = {**dirs, **s['channel'], 'registry': payload['registry'], 'source': ctx.parent, 'run': ctx.run_descriptor}
    controller = {'schema': 'neural081_complete_controller_v1', 'source': ctx.parent, 'run': ctx.run_descriptor, 'channel': channel, 'output_root': str(Path(s['outputs']['output'])/'parent-controller'), 'protected_roots': inputs['preparation']['protected_roots'], 'native_config': a['native_config'], 'preparation': a['preparation'], 'preparation_manifest': a['preparation_source'], 'reference_manifest': a['reference'], 'issuer_manifest': a['issuer'], 'issuer_worker_limits': e['issuer']['worker_limits'], 'issuer_sandbox': e['issuer']['sandbox'], 'host_python': e['host']['parent_python'], 'host_environment': e['host']['host_environment'], 'provider_config': a['provider_config'], 'replication_seeds': s['replication_seeds'], 'public_protocol': ctx.source_text('neural081/protocol/CANDIDATE_PROTOCOL.txt'), 'tool_source': _stage_fixed(ctx, 'neural081/parent/program/reference_tools.py'), 'candidate_runner': _stage_fixed(ctx, 'neural081/parent/program/candidate_runner.py'), 'numeric_source': bundle['numeric_source'], 'grade_manifest': a['grader'], 'grade_worker_io': s['worker_io']['grade'], 'host_metadata_capacity_bytes': s['worker_io']['host_metadata_capacity_bytes']}
    exact(controller, _STAGE_CONTROLLER_KEYS)
    out = ctx.write('P', 'controller/CONTROLLER.json', controller)
    ctx.recheck()
    return {'controller': out, 'channel': channel, 'future_receipts_required': True}


def _stage_controller_body(ctx, c):
    """Reconstruct every controller field from independently selected inputs.

    Metadata custody does not excuse a free-form translated controller. These
    checks precede the original request constructor and all later admissions.
    """
    exact(c, _STAGE_CONTROLLER_KEYS)
    inputs, _ = _stage_input(ctx)
    s, _, _ = _stage_selection(ctx, input_row=inputs)
    e, _ = _stage_environment_records(ctx)
    numeric = _stage_fixed(ctx, 'neural081/parent/references/' + e['worker_environments']['reference']['numeric_role'] + '/numeric.py')
    values = {'preparation': inputs['preparation'], 'native_config': e['native'], 'provider_config': e['provider']}
    names = {'preparation': 'PREPARATION.json', 'native_config': 'NATIVE_CONFIG.json', 'provider_config': 'PROVIDER_CONFIG.json'}
    for kind in ('preparation', 'reference', 'issuer', 'grader'):
        row = e['worker_environments'][kind]
        name = {'preparation': 'preparation_manifest', 'reference': 'reference_manifest', 'issuer': 'issuer_manifest', 'grader': 'grade_manifest'}[kind]
        values[name] = ctx.worker_manifest(kind, row['qualification'], row['installed_versions'], numeric_source=numeric if kind == 'reference' else None)
        names[name] = kind.upper() + '-SOURCE.json'
    artifacts = {name: {'path': str(ctx.run_root/'environment'/names[name]), **pin(encode(value))} for name, value in values.items()}
    for name, value in values.items():
        need(same(c[name], artifacts[name]), 'exact translated artifact identity ' + name)
        need(same(ctx.read(c[name], scope='operator'), value), 'actual translated artifact body ' + name)
    channel = c['channel']
    exact(channel, ('request_root', 'response_root', 'maximum_response_bytes', 'poll_seconds', 'registry', 'source', 'run'))
    _stage_registry_templates(ctx, channel['registry'])
    expected_channel = {'request_root': str(ctx.run_root/'channel/requests'), 'response_root': str(ctx.run_root/'channel/responses'), **s['channel'], 'registry': channel['registry'], 'source': ctx.parent, 'run': ctx.run_descriptor}
    expected = {'schema': 'neural081_complete_controller_v1', 'source': ctx.parent, 'run': ctx.run_descriptor, 'channel': expected_channel, 'output_root': str(Path(s['outputs']['output'])/'parent-controller'), 'protected_roots': inputs['preparation']['protected_roots'], **artifacts, 'issuer_worker_limits': e['issuer']['worker_limits'], 'issuer_sandbox': e['issuer']['sandbox'], 'host_python': e['host']['parent_python'], 'host_environment': e['host']['host_environment'], 'replication_seeds': s['replication_seeds'], 'public_protocol': ctx.source_text('neural081/protocol/CANDIDATE_PROTOCOL.txt'), 'tool_source': _stage_fixed(ctx, 'neural081/parent/program/reference_tools.py'), 'candidate_runner': _stage_fixed(ctx, 'neural081/parent/program/candidate_runner.py'), 'numeric_source': numeric, 'grade_worker_io': s['worker_io']['grade'], 'host_metadata_capacity_bytes': s['worker_io']['host_metadata_capacity_bytes']}
    need(same(c, expected), 'complete literal controller translation, no free-form substitutions')
    return s


def _stage_controller(ctx, desc):
    _stage_path_descriptor(desc, ctx.run_root/'controller/CONTROLLER.json')
    c = ctx.read(desc, scope='operator')
    s = _stage_controller_body(ctx, c)
    return c, s


def stage_request_launch(ctx, payload):
    exact(payload, ('controller',))
    c, s = _stage_controller(ctx, payload['controller'])
    request = ctx.parent_call('outer.launch_request', ctx.parent, c, str(Path(s['outputs']['output'])/'parent-outer'), ctx.parent_document['entry'], s['bootstrap_read_cap'], ctx.run)
    ctx.recheck()
    d = ctx.write('P', 'launch/REQUEST.json', request)
    ctx.recheck()
    return {'request': d, 'authority_required': True, 'envelope_not_yet_issued': True}


def _stage_envelope_from_request(ctx, request_desc, authority_desc):
    _stage_path_descriptor(request_desc, ctx.run_root/'launch/REQUEST.json')
    request = ctx.read(request_desc, scope='operator')
    exact(request, ('schema', 'source_manifest', 'controller', 'outer_output', 'controller_entry', 'bootstrap_read_cap', 'run', 'original_origin', 'normal_endpoint'))
    _stage_controller_body(ctx, request['controller'])
    expected = ctx.parent_call('outer.launch_request', ctx.parent, request['controller'], request['outer_output'], ctx.parent_document['entry'], request['bootstrap_read_cap'], ctx.run)
    need(same(request, expected) and same(request['run'], ctx.run_descriptor), 'complete unchanged independently materializable request')
    s, _, _ = _stage_selection(ctx)
    need(request['outer_output'] == str(Path(s['outputs']['output'])/'parent-outer') and request['controller']['output_root'] == str(Path(s['outputs']['output'])/'parent-controller') and request['bootstrap_read_cap'] == s['bootstrap_read_cap'], 'selected output and bootstrap geometry')
    _stage_descriptor(authority_desc)
    need(canonical(authority_desc['path']).is_relative_to(ctx.run_root/'authority'), 'independently issued selected authority namespace')
    return {'schema': 'neural081_selected_execution_envelope_v2', 'source_manifest': ctx.parent, 'controller': request['controller'], 'launch_request': request_desc, 'outer_authority': authority_desc, 'outer_output': request['outer_output'], 'controller_entry': ctx.parent_document['entry'], 'bootstrap_read_cap': request['bootstrap_read_cap']}


def _stage_admit_envelope(ctx, envelope, desc):
    _stage_controller_body(ctx, envelope['controller'])
    selected, q = ctx.parent_call('outer.admit_launch', envelope, desc, ctx.parent, ctx.source_files, ctx.run, ctx.stage_budget())
    c = envelope['controller']
    _stage_join(q, 'observer', 'entry', ctx.parent_document['entry'])
    _stage_join(q, 'observer', 'host_python', c['host_python'])
    _stage_join(q, 'observer', 'host_environment', c['host_environment'])
    _stage_join(q, 'provider', 'configuration', c['provider_config'])
    provider = ctx.read(c['provider_config'], scope='operator')
    _stage_provider(provider)
    _stage_join(q, 'provider', 'launch_credential_name', provider['api_key_env'])
    need(provider['api_key_env'] not in c['host_environment'], 'no credential value in stored environment')
    return selected, q, provider


def stage_bind_launch(ctx, payload):
    exact(payload, ('request', 'authority'))
    envelope = _stage_envelope_from_request(ctx, payload['request'], payload['authority'])
    preview = {'path': str(ctx.run_root/'launch/ENVELOPE.json'), **pin(encode(envelope))}
    _stage_admit_envelope(ctx, envelope, preview)
    ctx.recheck()
    d = ctx.write('P', 'launch/ENVELOPE.json', envelope)
    need(same(d, preview), 'actual final envelope bytes equal admitted payload')
    ctx.recheck()
    return {'envelope': d, 'runtime_executed': False}


def _stage_registry(ctx, desc, require_qualified=True):
    _stage_path_descriptor(desc, ctx.root/'benchmarks/neuroscience/neural-081/manifest.json')
    doc = ctx.read(desc, scope='source', cap=2**20)
    need(type(doc) is dict and doc.get('id') == _STAGE_TASK, 'single current task registry')
    need(type(doc.get('program_execution')) is dict and type(doc.get('program_conditions')) is dict, 'complete program registrations')
    exact(doc['program_conditions'], ('full10_instructed_excerpt_v1',))
    freeze = ctx.instance['source_freeze']
    expected_freeze = {**freeze, 'path': str(Path(freeze['path']).relative_to(ctx.root))}
    for condition in _STAGE_CONDITIONS:
        record = doc['program_execution'] if condition == 'default' else doc['program_conditions'][condition]
        need(type(record) is dict and same(record.get('entrypoint'), ctx.route(condition)), 'exact literal source-owned route')
        need(same(record.get('source_freeze'), expected_freeze), 'exact complete72 source freeze')
    if require_qualified:
        need(ctx.generic_qualification(doc) is True, 'actual generic qualification before operands')
    return {'descriptor': desc, 'document': doc}


def stage_bind_route(ctx, payload):
    exact(payload, ('current_registry', 'records'))
    registry = _stage_registry(ctx, payload['current_registry'], False)
    exact(payload['records'], ('receipt', 'qualification', 'source_binding'))
    originals = {}
    # All three source operands are captured before any publication. References
    # inside them are checked by the real generic helper, never rewritten.
    for role, d in payload['records'].items():
        originals[role] = ctx.read(_stage_descriptor(d), scope='operator', cap=2**21)
    ctx.recheck()
    copies = []
    for role in ('receipt', 'qualification', 'source_binding'):
        d = payload['records'][role]
        copied = ctx.import_record(d, 'Q', role + '-' + d['sha256'] + '.json')
        exact(copied, ('origin', 'copy'))
        need(same(copied['origin'], d) and copied['copy']['bytes'] == d['bytes'] and copied['copy']['sha256'] == d['sha256'], 'exact byte-preserving qualification import')
        copies.append({'role': role, **copied})
    verification = {'status': 'passed'}
    for row in copies:
        verification[row['role'] + '_path'] = str(Path(row['copy']['path']).relative_to(ctx.root))
        verification[row['role'] + '_sha256'] = row['copy']['sha256']
    new = json.loads(encode(registry['document']))
    new['program_execution']['verification'] = verification
    new['program_conditions']['full10_instructed_excerpt_v1']['verification'] = verification
    need(ctx.generic_qualification(new) is True, 'real exact72 source/control/terminal joins')
    generation_hash = pin(encode(new))['sha256']
    preimage = ctx.import_record(payload['current_registry'], 'V', generation_hash + '/PREIMAGE.json')
    exact(preimage, ('origin', 'copy'))
    need(same(preimage['origin'], payload['current_registry']) and preimage['copy']['bytes'] == preimage['origin']['bytes'] and preimage['copy']['sha256'] == preimage['origin']['sha256'], 'byte-identical registry preimage archive')
    generation = ctx.write('V', generation_hash + '/GENERATION.json', new)
    plan = {'schema': 'neural081_portable_registry_transaction_v1', 'task_id': _STAGE_TASK, 'construction': ctx.construction, 'source': ctx.source, 'registry_path': str(ctx.root/'benchmarks/neuroscience/neural-081/manifest.json'), 'preimage': payload['current_registry'], 'preimage_archive': preimage['copy'], 'generation': generation, 'record_copies': copies}
    transaction = ctx.write('V', generation_hash + '/TRANSACTION.json', plan)
    ctx.recheck()
    return {'transaction': transaction, 'generation': generation, 'registry_activated': False}


def _stage_transaction(ctx, desc):
    _stage_descriptor(desc)
    vroot = ctx.root/'neural081/registry-generations'
    need(canonical(desc['path']).is_relative_to(vroot), 'only designated local registry transaction')
    plan = ctx.read(desc, scope='V')
    _stage_object(plan, 'neural081_portable_registry_transaction_v1', ('schema', 'task_id', 'construction', 'source', 'registry_path', 'preimage', 'preimage_archive', 'generation', 'record_copies'))
    need(same(plan['construction'], ctx.construction) and same(plan['source'], ctx.source), 'exact selected immutable source transaction')
    need(plan['registry_path'] == str(ctx.root/'benchmarks/neuroscience/neural-081/manifest.json'), 'one source-owned mutable registry path')
    _stage_path_descriptor(plan['preimage'], plan['registry_path'])
    for key in ('preimage_archive', 'generation'):
        _stage_descriptor(plan[key]); need(canonical(plan[key]['path']).is_relative_to(vroot), 'immutable V record')
    need(plan['preimage_archive']['bytes'] == plan['preimage']['bytes'] and plan['preimage_archive']['sha256'] == plan['preimage']['sha256'], 'exact preimage identity retained')
    old = ctx.read(plan['preimage'], scope='source')
    archive = ctx.read(plan['preimage_archive'], scope='V')
    new = ctx.read(plan['generation'], scope='V')
    need(same(old, archive), 'current preimage exact archived body')
    need(type(plan['record_copies']) is list and [x.get('role') for x in plan['record_copies']] == ['receipt', 'qualification', 'source_binding'], 'exact three imported records')
    verification = {'status': 'passed'}
    for row in plan['record_copies']:
        exact(row, ('role', 'origin', 'copy'))
        for key in ('origin', 'copy'):
            _stage_descriptor(row[key])
        need(row['origin']['bytes'] == row['copy']['bytes'] and row['origin']['sha256'] == row['copy']['sha256'], 'unchanged issuer bytes')
        need(canonical(row['copy']['path']).parent == ctx.here/'runtime-qualification', 'fixed Q import')
        ctx.read(row['copy'], scope='Q', cap=2**21)
        verification[row['role']+'_path'] = str(Path(row['copy']['path']).relative_to(ctx.root))
        verification[row['role']+'_sha256'] = row['copy']['sha256']
    expected = json.loads(encode(old))
    expected['program_execution']['verification'] = verification
    expected['program_conditions']['full10_instructed_excerpt_v1']['verification'] = verification
    need(same(expected, new), 'only real verification fields may change')
    need(ctx.generic_qualification(new) is True, 'actual unchanged source and generic qualification at activation')
    ctx.recheck()
    return plan


def stage_activate_route(ctx, payload):
    exact(payload, ('transaction',))
    plan = _stage_transaction(ctx, payload['transaction'])
    # This future explicitly selected operation is not exercised successfully by
    # construction controls. The concrete owner CAS retains uncertain failures.
    result = ctx.activate_registry(plan)
    ctx.recheck()
    return result


def _stage_gate_admit(ctx, condition, declaration, registry, review=None, operands=None):
    selection = _stage_descriptor(ctx.instance['selection'])
    need(type(review) is dict and type(operands) is dict, 'actual gate receives review metadata and four literal operands')
    gate_ctx = ctx.gate_context(review=review, invocation_operands=operands)
    return ctx.local_gate.admit(gate_ctx, condition, declaration, selection, registry)


def _stage_review_core(ctx, review, registry, program):
    _stage_object(review, 'neural081_portable_central_review_v1', _STAGE_REVIEW_KEYS)
    s, _, _ = _stage_selection(ctx)
    e, _ = _stage_environment_records(ctx)
    roots = {key: _stage_roots(ctx, key) for key in ('operator', 'protected', 'secret', 'raw')}
    expected = {'condition': s['condition'], 'central_source': ctx.source, 'parent_source': ctx.parent, 'construction': ctx.construction, 'registry': registry['descriptor'], 'program': program, 'run': ctx.run_descriptor, 'origin': ctx.run['origin'], 'normal_endpoint': ctx.run['normal_endpoint'], 'central_limits': s['central_limits'], 'total_limits': s['total_limits'], 'external_limits': s['external_limits'], 'memory': s['memory'], 'roots': roots, 'launch': {'python': e['host']['parent_python'], 'parent_entry': ctx.parent_document['entry'], 'cwd': '/', 'host_environment': e['host']['host_environment'], 'credential_name': e['provider']['api_key_env'], 'inherited_address_space_bytes': s['memory']['address_space_bytes']}}
    for key, value in expected.items():
        need(same(review[key], value), 'complete selected review ' + key)
    exact(review['local_declaration'], ('request', 'selection'))
    need(same(review['local_declaration']['selection'], ctx.instance['selection']), 'exact local source selection')
    _stage_descriptor(review['local_declaration']['request'])
    _stage_path_descriptor(program, ctx.run_root/'launch/ENVELOPE.json')
    envelope = ctx.read(program, scope='operator')
    _, q, provider = _stage_admit_envelope(ctx, envelope, program)
    need(envelope['outer_output'] == str(Path(s['outputs']['output'])/'parent-outer') and envelope['controller']['output_root'] == str(Path(s['outputs']['output'])/'parent-controller'), 'full selected output geometry')
    need(same(envelope['controller']['host_environment'], review['launch']['host_environment']) and envelope['controller']['host_python'] == review['launch']['python'] and provider['api_key_env'] == review['launch']['credential_name'], 'original outer/central clean credential boundary')
    return s, e


def stage_request_review(ctx, payload):
    exact(payload, ('envelope', 'registry', 'declaration'))
    registry = _stage_registry(ctx, payload['registry'])  # before any envelope
    s, _, _ = _stage_selection(ctx)
    e, _ = _stage_environment_records(ctx)
    review = {'schema': 'neural081_portable_central_review_v1', 'task_id': _STAGE_TASK, 'condition': s['condition'], 'central_source': ctx.source, 'parent_source': ctx.parent, 'construction': ctx.construction, 'registry': payload['registry'], 'program': payload['envelope'], 'run': ctx.run_descriptor, 'local_declaration': {'request': payload['declaration'], 'selection': ctx.instance['selection']}, 'origin': ctx.run['origin'], 'normal_endpoint': ctx.run['normal_endpoint'], 'central_limits': s['central_limits'], 'total_limits': s['total_limits'], 'external_limits': s['external_limits'], 'memory': s['memory'], 'roots': {key: _stage_roots(ctx, key) for key in ('operator', 'protected', 'secret', 'raw')}, 'launch': {'python': e['host']['parent_python'], 'parent_entry': ctx.parent_document['entry'], 'cwd': '/', 'host_environment': e['host']['host_environment'], 'credential_name': e['provider']['api_key_env'], 'inherited_address_space_bytes': s['memory']['address_space_bytes']}}
    # Actual gate admission needs the complete declaration/roots/program view
    # and all four operands. At this prequalification stage the review operand
    # identifies the forthcoming immutable payload, not an approved invocation.
    token = pin(encode(review))['sha256']
    operands = {'program': payload['envelope']['path'], 'output': s['outputs']['output'], 'review': str(ctx.here/'operator-selections'/('review-payload-' + token + '.json')), 'other_reserve_bytes': str(integer(s['memory']['other_reserve_bytes']))}
    _stage_gate_admit(ctx, s['condition'], payload['declaration'], registry, review, operands)
    _stage_review_core(ctx, review, registry, payload['envelope'])
    ctx.recheck()
    token = pin(encode(review))['sha256']
    d = ctx.write('R', 'review-payload-' + token + '.json', review)
    request = ctx.write('R', 'qualification-request-' + token + '.json', {'schema': 'neural081_portable_capability_request_v1', 'task_id': _STAGE_TASK, 'payload': d, 'source': ctx.source, 'run': ctx.run_descriptor, 'required_capability_names': sorted(_STAGE_CAPABILITIES), 'qualification_generated': False})
    ctx.recheck()
    return {'payload': d, 'qualification_request': request, 'qualified': False}


def _stage_qualification(ctx, desc, review):
    _stage_descriptor(desc)
    need(canonical(desc['path']).parent == ctx.here/'operator-selections' and desc['bytes'] <= 65536 and Path(desc['path']).name != 'APPROVAL_REGISTRY.json', 'exact source-local central qualification')
    q = ctx.read(desc, scope='R', cap=65536)
    exact(q, ('schema', 'status', 'selected_actual', 'issuer', 'binding', 'capabilities'))
    need(q['schema'] == 'neural081_central_launch_qualification_v1' and q['status'] == 'qualified' and q['selected_actual'] is True and same(q['binding'], review) and same(q['capabilities'], _STAGE_CAPABILITIES), 'actual independently issued exact capability record')
    need(type(q['issuer']) is str and q['issuer'], 'literal independent issuer identity')
    return q


def stage_publish_review(ctx, payload):
    exact(payload, ('payload', 'qualification'))
    _stage_descriptor(payload['payload'])
    need(canonical(payload['payload']['path']).parent == ctx.here/'operator-selections', 'fixed direct-child review payload')
    review = ctx.read(payload['payload'], scope='R', cap=32768)
    _stage_object(review, 'neural081_portable_central_review_v1', _STAGE_REVIEW_KEYS)
    registry = _stage_registry(ctx, review['registry'])
    s, _, _ = _stage_selection(ctx)
    operands = {'program': review['program']['path'], 'output': s['outputs']['output'], 'review': payload['payload']['path'], 'other_reserve_bytes': str(integer(review['memory']['other_reserve_bytes']))}
    _stage_gate_admit(ctx, review['condition'], review['local_declaration']['request'], registry, review, operands)
    _stage_review_core(ctx, review, registry, review['program'])
    _stage_qualification(ctx, payload['qualification'], review)
    final = {**review, 'qualification': payload['qualification']}
    need(len(encode(final)) <= 32768, 'original bounded final review')
    token = pin(encode(final))['sha256']
    ctx.recheck()
    d = ctx.write('R', 'review-' + token + '.json', final)
    request = ctx.write('P', 'commands/approval-request-' + token + '.json', {'schema': 'neural081_portable_approval_request_v1', 'task_id': _STAGE_TASK, 'review': d, 'qualification': payload['qualification'], 'approval_registry_path': str(ctx.here/'operator-selections/APPROVAL_REGISTRY.json'), 'approval_generated': False})
    ctx.recheck()
    return {'review': d, 'approval_request': request, 'approved': False}


def stage_admit_approved_review(ctx, payload):
    exact(payload, ('review', 'approval'))
    _stage_descriptor(payload['review'])
    need(canonical(payload['review']['path']).parent == ctx.here/'operator-selections' and Path(payload['review']['path']).name != 'APPROVAL_REGISTRY.json', 'fixed direct-child final review')
    review = ctx.read(payload['review'], scope='R', cap=32768)
    exact(review, (*_STAGE_REVIEW_KEYS, 'qualification'))
    base = {key: value for key, value in review.items() if key != 'qualification'}
    registry = _stage_registry(ctx, review['registry'])
    s, _ = _stage_review_core(ctx, base, registry, review['program'])
    q = _stage_qualification(ctx, review['qualification'], base)
    _stage_path_descriptor(payload['approval'], ctx.here/'operator-selections/APPROVAL_REGISTRY.json')
    approval = ctx.read(payload['approval'], scope='R', cap=131072)
    exact(approval, ('schema', 'selected_actual', 'allowed_issuers', 'reviews'))
    need(approval['schema'] == 'neural081_protected_central_approvals_v1' and approval['selected_actual'] is True and type(approval['allowed_issuers']) is list and q['issuer'] in approval['allowed_issuers'], 'actual independent protected approval issuer')
    need(type(approval['reviews']) is dict and same(approval['reviews'].get(payload['review']['sha256']), {'review': payload['review'], 'qualification': review['qualification']}), 'exact final review/qualification approved')
    other = integer(review['memory']['other_reserve_bytes'])
    operands = {'program': review['program']['path'], 'output': s['outputs']['output'], 'review': payload['review']['path'], 'other_reserve_bytes': str(other)}
    first = _stage_gate_admit(ctx, review['condition'], review['local_declaration']['request'], registry, review, operands)
    environment, _ = _stage_environment_records(ctx)
    argv = ctx.actual_argv(review['condition'], operands['program'], operands['output'], operands['review'], other, python=environment['host']['central_python'])
    ctx.recheck()
    registry2 = _stage_registry(ctx, review['registry'])
    second = _stage_gate_admit(ctx, review['condition'], review['local_declaration']['request'], registry2, review, operands)
    environment, _ = _stage_environment_records(ctx)
    planned = ctx.local_gate.plan(first, second, argv, str(ctx.root), environment['host']['central_python'])
    need(planned.get('actual_invocation_observed') is False, 'planned command is not an observed invocation')
    command = {'schema': 'neural081_portable_invocation_v1', 'task_id': _STAGE_TASK, 'review': payload['review'], 'approval': payload['approval'], 'registry': review['registry'], 'source': ctx.source, 'condition': review['condition'], 'template': ctx.route(review['condition']), 'argv': argv, 'cwd': str(ctx.root), 'other_condition_requires_its_own_review': True, 'command_emitted_only': True, 'process_invoked': False, 'natural_exit_observed': False, 'independent_original_outer_observation_required': True}
    d = ctx.write('P', 'commands/invocation-' + payload['review']['sha256'] + '.json', command)
    ctx.recheck()
    return {'invocation': d, 'runtime_executed': False}


def stage_respond(ctx, payload):
    exact(payload, ('intent', 'authority'))
    intent = ctx.read(_stage_descriptor(payload['intent']), scope='operator')
    exact(intent, ('schema', 'sequence', 'source', 'source_files', 'run', 'request', 'phase', 'actor', 'registry', 'statistical_semantic_verdict_requested'))
    need(intent['schema'] == 'neural081_operator_metadata_request_v1' and intent['statistical_semantic_verdict_requested'] is False, 'actual source-owned channel intent, no statistical verdict')
    sequence = integer(intent['sequence'], 0, 4)
    need(intent['phase'] == _STAGE_PHASES[sequence] and intent['actor'] == 'controller', 'literal five controller requests in source order')
    need(same(intent['source'], ctx.parent) and same(intent['source_files'], ctx.source_files) and same(intent['run'], ctx.run_descriptor), 'complete exact source/run channel identity')
    name = '%06d-%s-%s.json' % (sequence, intent['phase'], intent['actor'])
    _stage_path_descriptor(payload['intent'], ctx.run_root/'channel/requests'/name)
    _stage_registry_templates(ctx, intent['registry'])
    selected = ctx.read(_stage_descriptor(payload['authority']), scope='operator')
    need(canonical(payload['authority']['path']).is_relative_to(ctx.run_root/'authority'), 'already issued protected authority only')
    need(same(selected.get('registry'), intent['registry']) and same(selected.get('run'), ctx.run_descriptor), 'same independent registry and run')
    ctx.parent_call('authority.admit', selected, ctx.parent, intent['request'], intent['phase'], intent['actor'], ctx.stage_budget(), ctx.source_files, protected_roots=_stage_roots(ctx, 'protected'))
    response = {'schema': 'neural081_operator_metadata_response_v1', 'sequence': sequence, 'intent': payload['intent'], 'authority': selected}
    s, _, _ = _stage_selection(ctx)
    need(len(encode(response)) <= s['channel']['maximum_response_bytes'], 'exact original response cap')
    ctx.recheck()
    d = ctx.write('P', 'channel/responses/' + name, response)
    ctx.recheck()
    return {'response': d, 'authority_issued_by_constructor': False}


STAGES = {'select-run': stage_select_run, 'bind-environment': stage_bind_environment, 'bind-channel': stage_bind_channel, 'request-launch': stage_request_launch, 'bind-launch': stage_bind_launch, 'bind-route': stage_bind_route, 'activate-route': stage_activate_route, 'request-review': stage_request_review, 'publish-review': stage_publish_review, 'admit-approved-review': stage_admit_approved_review, 'respond': stage_respond}


# ---- Byte-identical reviewed source fragment ----

"""Literal isolated source-constructor and metadata-stage command interface."""

def main(argv=None):
    parser = argparse.ArgumentParser(description='Construct exact NEURAL081 source and bind separately issued metadata; never run science.')
    parser.add_argument('stage', choices=('build', *WRITE_DOMAINS))
    for name in ('read-cap', 'write-cap', 'live-cap'):
        parser.add_argument('--' + name, required=True, type=int)
    parser.add_argument('--deadline', required=True, type=float)
    for name in ('release', 'release-sha256', 'public-root', 'root', 'profile', 'profile-sha256', 'input', 'input-sha256'):
        parser.add_argument('--' + name)
    for name in ('release-bytes', 'profile-bytes', 'input-bytes'):
        parser.add_argument('--' + name, type=int)
    args = parser.parse_args(argv)
    budget = Budget(args.read_cap, args.write_cap, args.live_cap, args.deadline)
    # Explicit source demand is separate from subsequent content authentication.
    own = ordinary_ancestors(str(Path(__file__).absolute()))
    info = own.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'ordinary constructor entry')
    budget.charge('read_bytes', info.st_size)
    context = None
    root_ownership = CreatedRoot()
    try:
        if args.stage == 'build':
            need(all(getattr(args, k) is None for k in ('input', 'input_bytes', 'input_sha256')), 'build has no stage-input alias')
            need(all(getattr(args, k) is not None for k in ('release', 'release_bytes', 'release_sha256', 'public_root', 'root', 'profile', 'profile_bytes', 'profile_sha256')), 'explicit complete build arguments')
            release = descriptor({'path': args.release, 'bytes': args.release_bytes, 'sha256': args.release_sha256})
            profile = descriptor({'path': args.profile, 'bytes': args.profile_bytes, 'sha256': args.profile_sha256})
            result = build_instance(release, args.public_root, args.root, profile, budget,
                                    root_ownership=root_ownership)
        else:
            need(all(getattr(args, k) is None for k in ('release', 'release_bytes', 'release_sha256', 'public_root', 'root', 'profile', 'profile_bytes', 'profile_sha256')), 'metadata stage has only pinned input')
            document = descriptor({'path': args.input, 'bytes': args.input_bytes, 'sha256': args.input_sha256})
            inp = capture_json(document, budget)
            exact(inp, ('schema', 'stage', 'instance', 'run', 'payload'))
            need(inp['schema'] == 'neural081_portable_stage_input_v1' and inp['stage'] == args.stage, 'exact stage dispatch')
            context = Context(inp['instance'], inp['run'], args.stage, budget)
            # The single initially supplied control record is metadata, but must
            # also lie in the selected operator namespace before its payload is
            # admitted. No nested pointer has been followed at this boundary.
            context._deny(document['path'])
            need(any(canonical(document['path']).is_relative_to(canonical(p)) for p in context.roots['operator']), 'stage control record in protected operator domain')
            context._remember(document)
            result = STAGES[args.stage](context, inp['payload'])
            context.recheck()
            result = {'schema': 'neural081_portable_metadata_stage_result_v1', 'stage': args.stage,
                      'input': document, 'instance': inp['instance'], 'result': result,
                      'scientific_execution': False, 'original_runtime_exit_observed': False,
                      'budget': budget.snapshot()}
        raw = encode(result)
        need(len(raw) <= 65536, 'bounded constructor terminal report')
        budget.charge('write_bytes', len(raw))
        budget.check()
        sys.stdout.buffer.write(raw)
        sys.stdout.buffer.flush()
        budget.check()
        return 0
    except BaseException as error:
        failure = {'schema': 'neural081_portable_construction_failure_v1', 'stage': args.stage,
                   'exception_type': type(error).__name__, 'automatic_retry': False,
                   'published_prefix_may_remain': True, 'completion_not_established': True,
                   'scientific_execution': False, 'budget': budget.snapshot()}
        # Preserve a new independent failure record when the selected budget and
        # exact writer domain still permit it; never overwrite or roll back.
        try:
            if context is not None:
                domain = 'P' if context.run_root is not None and 'P' in WRITE_DOMAINS[args.stage] else (
                    'V' if 'V' in WRITE_DOMAINS[args.stage] else 'R')
                token = pin(encode(failure))['sha256']
                context.write(domain, 'constructor-failure-' + token + '.json', failure)
            elif root_ownership.fd is not None:
                root_ownership.publish_failure(failure, budget)
        except BaseException:
            pass
        # Original error remains the propagated cause; no success or operating
        # qualification is synthesized by an attempted failure publication.
        raise
    finally:
        original_error = sys.exc_info()[0] is not None
        try:
            root_ownership.close()
        except BaseException:
            if not original_error:
                raise


if __name__ == '__main__':
    raise SystemExit(main())
