"""Materialize the fixed public source into a fresh owned tree, then inspect.

The reviewed commit authenticates this executable; this helper does not certify
itself. Only the fixed 130-body transport is admitted. No study input, model,
scientific module, native provider or acquisition endpoint is opened.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import selectors
import stat
import subprocess
import sys
import time

if sys.version_info < (3, 11):
    raise RuntimeError('Source materialization requires Python 3.11 or newer')

# Parent injects exactly one final reviewed 130-row literal before publication.
TRANSPORT_MANIFEST = [
  {
    "bytes": 3829,
    "path": "postscore_system_v2/NOTICES.md",
    "runtime_mode": "0o644",
    "sha256": "8950df9647e2b0501f1302c4b455e19b62e89359b66a1840e0d595f7b44d0f37",
    "transport_mode": "0o644"
  },
  {
    "bytes": 13885,
    "path": "postscore_system_v2/README.md",
    "runtime_mode": "0o644",
    "sha256": "2a7ea09cb114f20d3cad03e209b9f366db842c2e1908285b3be2c881ac00da75",
    "transport_mode": "0o644"
  },
  {
    "bytes": 30217,
    "path": "postscore_system_v2/SOURCE_DISCOVERY_MANIFEST.json",
    "runtime_mode": "0o644",
    "sha256": "d3ec37aeadf0cbcfd3fe74558558b8202aca8a34d22b0095df6b054b3aaba988",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5244,
    "path": "postscore_system_v2/complete_study/FEATURE_PREPARATION.md",
    "runtime_mode": "0o644",
    "sha256": "bcc7ede6fbe0bbee007685fdf1396b4cbe15f610777bca396602369cc58862b3",
    "transport_mode": "0o644"
  },
  {
    "bytes": 2796,
    "path": "postscore_system_v2/complete_study/LEGACY_ROLES.json",
    "runtime_mode": "0o644",
    "sha256": "6a6f9e06444ce8ef866672a0923d9fad00e3f56a5b27793a7b17f681cae9c136",
    "transport_mode": "0o644"
  },
  {
    "bytes": 15355,
    "path": "postscore_system_v2/complete_study/OPERATING_CONTRACT_V3.md",
    "runtime_mode": "0o644",
    "sha256": "90909f424996769aeacddf74414ce0a757ab3df7ac1b284a6e297abddf444921",
    "transport_mode": "0o644"
  },
  {
    "bytes": 18592,
    "path": "postscore_system_v2/complete_study/RUNTIME_SOURCE_MANIFEST.json",
    "runtime_mode": "0o644",
    "sha256": "583ae551b6a4f185675b3f44eeed720dbb185b11ada7d61f1b3b86bcfdbd10e8",
    "transport_mode": "0o644"
  },
  {
    "bytes": 2195,
    "path": "postscore_system_v2/complete_study/broker_client.py",
    "runtime_mode": "0o644",
    "sha256": "55a27f5c199400012f852206f2754872a3dc73013c5dbd859261a5b190f3badf",
    "transport_mode": "0o644"
  },
  {
    "bytes": 8013,
    "path": "postscore_system_v2/complete_study/capture_entry.py",
    "runtime_mode": "0o644",
    "sha256": "f6a171d1b1f4511f1ca7f848cf7d7002672825a5ec8b1da7fa955fa9108f61b7",
    "transport_mode": "0o644"
  },
  {
    "bytes": 7671,
    "path": "postscore_system_v2/complete_study/central_entry.py",
    "runtime_mode": "0o644",
    "sha256": "b662f740f12426fbd9d972a53f494381c43ac6da7c5bc721a241e77f137a9b3a",
    "transport_mode": "0o644"
  },
  {
    "bytes": 7938,
    "path": "postscore_system_v2/complete_study/contracts/CONTRASTS.json",
    "runtime_mode": "0o644",
    "sha256": "b5b24650a8288272cd4642bb76bb68ffead79b1c116a5f7c43062874925d2411",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5317,
    "path": "postscore_system_v2/complete_study/contracts/ISOLATION_CONTRACT.json",
    "runtime_mode": "0o644",
    "sha256": "5551fa10d35517f158786714ace8cdb1f88bf7a55443fc649f1e44182f17d347",
    "transport_mode": "0o644"
  },
  {
    "bytes": 4510,
    "path": "postscore_system_v2/complete_study/contracts/MODE_PERMISSIONS.json",
    "runtime_mode": "0o644",
    "sha256": "43e935217e43926337b740d76ca198116ba2b0864dd80bbd1c6f31aea849dee1",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5535,
    "path": "postscore_system_v2/complete_study/contracts/POSTSCORE_CONTRACT.md",
    "runtime_mode": "0o644",
    "sha256": "08eb9ca53d1d49cc133c5a9d5d86b96b0b774ed5b33f754ec14a74d60821b1d0",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1795,
    "path": "postscore_system_v2/complete_study/contracts/POSTSCORE_RESOURCE_V2.json",
    "runtime_mode": "0o644",
    "sha256": "13ac24117a982981e29674ad06e2c18c0adad03f685ae3ef0b160160aca9fe99",
    "transport_mode": "0o644"
  },
  {
    "bytes": 9765,
    "path": "postscore_system_v2/complete_study/contracts/REPORT_HIERARCHY.json",
    "runtime_mode": "0o644",
    "sha256": "649784fcf8f3a128466ee06704e66ee4648fbd50d6fbbca191c8750a22339ffb",
    "transport_mode": "0o644"
  },
  {
    "bytes": 13469,
    "path": "postscore_system_v2/complete_study/contracts/RESOURCE_DEFINITION.md",
    "runtime_mode": "0o644",
    "sha256": "c63d5db851c8e0e8460119ec8922a0e77119cd25095cb57acfdc17fe37cc8542",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5340,
    "path": "postscore_system_v2/complete_study/contracts/RESOURCE_POLICY_V1.json",
    "runtime_mode": "0o644",
    "sha256": "b896b8e175cd401c70ed37584e9aa797407c89dd6d5e1c0e31b1ac286b79711a",
    "transport_mode": "0o644"
  },
  {
    "bytes": 10161,
    "path": "postscore_system_v2/complete_study/contracts/TRUSTED_BROKER_CONTRACT_V3.json",
    "runtime_mode": "0o644",
    "sha256": "e9ed25f996651ba88032b1119d66eec08a096ebfa2a52292823e57bc034e8e9e",
    "transport_mode": "0o644"
  },
  {
    "bytes": 16199,
    "path": "postscore_system_v2/complete_study/legacy/015/packet.py",
    "runtime_mode": "0o644",
    "sha256": "a08ab5725aa95c3603a37c588d52b19a5a0cb50f42af6c0a2d3d9eee007d80f5",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5554,
    "path": "postscore_system_v2/complete_study/legacy/020/grade.py",
    "runtime_mode": "0o444",
    "sha256": "3a7581455fed1de2c164bacc1db6b1838f5ef0b883e3213d98749026e43a780d",
    "transport_mode": "0o644"
  },
  {
    "bytes": 10420,
    "path": "postscore_system_v2/complete_study/legacy/022/build_case.py",
    "runtime_mode": "0o444",
    "sha256": "1cf45a94db6b2d6b359b9d56672f9dccc3226af2def501240655b84f12ddec15",
    "transport_mode": "0o644"
  },
  {
    "bytes": 2940,
    "path": "postscore_system_v2/complete_study/legacy/023/build_panel.py",
    "runtime_mode": "0o444",
    "sha256": "8bdf8afd76ef356fd3b5c0c3c672edfac061b17cbae5b8d94effa7464b19824f",
    "transport_mode": "0o644"
  },
  {
    "bytes": 6949,
    "path": "postscore_system_v2/complete_study/legacy/024/metadata_core.py",
    "runtime_mode": "0o444",
    "sha256": "45fe4b4ad92b8fc5e1fc2e883d4a61e2285630513d20321e8584aab1542fec95",
    "transport_mode": "0o644"
  },
  {
    "bytes": 3892,
    "path": "postscore_system_v2/complete_study/legacy/025/source_io.py",
    "runtime_mode": "0o444",
    "sha256": "a3947a17b05bd0a3c63962ecb69643ee1a54b461be21f053a057aea3d3fd9bea",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5315,
    "path": "postscore_system_v2/complete_study/legacy/026/stage_source.py",
    "runtime_mode": "0o444",
    "sha256": "2d5cb7b7c75d8f139208c6546dc89391cf4d04d21fd01643aff9bcdacd768a93",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5541,
    "path": "postscore_system_v2/complete_study/legacy/027/reference_core.py",
    "runtime_mode": "0o444",
    "sha256": "6955d03232b545a4df0694669cb41338aa77bb24e23e9a8f7b838dd4085c09dd",
    "transport_mode": "0o644"
  },
  {
    "bytes": 7789,
    "path": "postscore_system_v2/complete_study/legacy/028/scorer.py",
    "runtime_mode": "0o444",
    "sha256": "32d523db849cf8f32120e44d2f5cdb47b46bd8d9657d8e3f05310d1c28f264f8",
    "transport_mode": "0o644"
  },
  {
    "bytes": 2415,
    "path": "postscore_system_v2/complete_study/legacy/029/POLICY.json",
    "runtime_mode": "0o444",
    "sha256": "e07436584593fe62e830e76ad8d75e14e2877edc90b711933f05c09beaa7c7c6",
    "transport_mode": "0o644"
  },
  {
    "bytes": 6764,
    "path": "postscore_system_v2/complete_study/legacy/030/TASK.md",
    "runtime_mode": "0o444",
    "sha256": "e5311daa10d45d63e61c04aab9b06e194ae1abb1ac0af700f1a9287368e683b5",
    "transport_mode": "0o644"
  },
  {
    "bytes": 3914,
    "path": "postscore_system_v2/complete_study/legacy/031/interface.py",
    "runtime_mode": "0o444",
    "sha256": "ccabe30238b084b19422c920877332232d730caca712f3679b73e6c28fcb3e0c",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1058,
    "path": "postscore_system_v2/complete_study/legacy/036/CASE_SCHEMA.json",
    "runtime_mode": "0o644",
    "sha256": "bfaca28e448bcecc4a521efd5eb597724d19ce41995358159546f2c54da7130e",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1854,
    "path": "postscore_system_v2/complete_study/legacy/037/PREDICTION_SCHEMA.json",
    "runtime_mode": "0o644",
    "sha256": "a5abbb135e3ccf396fbac4c017f974dc9c27086969901924fa5cea8b822aca31",
    "transport_mode": "0o644"
  },
  {
    "bytes": 4022,
    "path": "postscore_system_v2/complete_study/model_provider_entry.py",
    "runtime_mode": "0o644",
    "sha256": "6e16253e83a1981eb63fac72f9d170c3587a3ec19095892c5662b0591c85b67f",
    "transport_mode": "0o644"
  },
  {
    "bytes": 135,
    "path": "postscore_system_v2/complete_study/n055/__init__.py",
    "runtime_mode": "0o644",
    "sha256": "44ecb3ff12c2e72ea315fade04fd2062de0bdad868b3ff259cb862904d04fe30",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1680,
    "path": "postscore_system_v2/complete_study/n055/assignment.py",
    "runtime_mode": "0o644",
    "sha256": "7298f00e81c3ac13db9ac00e4e01ff14e0782d6ba4c8e5a20e9d35d903657861",
    "transport_mode": "0o644"
  },
  {
    "bytes": 2634,
    "path": "postscore_system_v2/complete_study/n055/authority.py",
    "runtime_mode": "0o644",
    "sha256": "adfed10ceeaaf2b02c75f943c25d73cc47ec7392b6786ee914e545f121089bc9",
    "transport_mode": "0o644"
  },
  {
    "bytes": 12096,
    "path": "postscore_system_v2/complete_study/n055/banks.py",
    "runtime_mode": "0o644",
    "sha256": "f46590ddd8f71ac163ad9cdef358560e0653cb6a03a27f50286b832ec3a9c0ea",
    "transport_mode": "0o644"
  },
  {
    "bytes": 19392,
    "path": "postscore_system_v2/complete_study/n055/broker.py",
    "runtime_mode": "0o644",
    "sha256": "9d0ec39e1e8cc86bd21fdfb606561d2c69a7ae3558dd19987351333ad93eeec9",
    "transport_mode": "0o644"
  },
  {
    "bytes": 18526,
    "path": "postscore_system_v2/complete_study/n055/budget.py",
    "runtime_mode": "0o644",
    "sha256": "94633906a77d527e40dcff653c15752890a27368effbc0477887918a2fdb5c6e",
    "transport_mode": "0o644"
  },
  {
    "bytes": 15014,
    "path": "postscore_system_v2/complete_study/n055/campaign.py",
    "runtime_mode": "0o644",
    "sha256": "7abcb46d1ad886373450724e2c1f83ad2ff614c86635a5c0bccc369fb87b8f8c",
    "transport_mode": "0o644"
  },
  {
    "bytes": 7540,
    "path": "postscore_system_v2/complete_study/n055/central.py",
    "runtime_mode": "0o644",
    "sha256": "3ce2be49e19033e5f8acc8ccc832812f9e007479b72eecdcf671333a77b8675e",
    "transport_mode": "0o644"
  },
  {
    "bytes": 7404,
    "path": "postscore_system_v2/complete_study/n055/cgroup.py",
    "runtime_mode": "0o644",
    "sha256": "75c14a2afcb73fd5052c22a89d7df175e72950faa32f0197ce47bfa4c0f6e539",
    "transport_mode": "0o644"
  },
  {
    "bytes": 9861,
    "path": "postscore_system_v2/complete_study/n055/collector.py",
    "runtime_mode": "0o644",
    "sha256": "95d553e96c1cec3820cf873abe02a0bd6c70410693491fd4f1c00509aaec6ffd",
    "transport_mode": "0o644"
  },
  {
    "bytes": 9590,
    "path": "postscore_system_v2/complete_study/n055/common.py",
    "runtime_mode": "0o644",
    "sha256": "8593b6ae72247e72f7dc98015168cd43fd635defc6a004129b078a2cff5ddda9",
    "transport_mode": "0o644"
  },
  {
    "bytes": 19589,
    "path": "postscore_system_v2/complete_study/n055/features.py",
    "runtime_mode": "0o644",
    "sha256": "5e828b2aaa283e98a5dc28f59e89298d0ad4476c25ccccbb2de8b77e15cf2bd6",
    "transport_mode": "0o644"
  },
  {
    "bytes": 4476,
    "path": "postscore_system_v2/complete_study/n055/inputs.py",
    "runtime_mode": "0o644",
    "sha256": "ad3b4f78574ecc4991d15841e7569b81c6031fc8dc9ce70dad01477d048b1183",
    "transport_mode": "0o644"
  },
  {
    "bytes": 26819,
    "path": "postscore_system_v2/complete_study/n055/interpretation.py",
    "runtime_mode": "0o644",
    "sha256": "1648bbb6f312056c7de99aca3acbf84f86e3d373e8daa04bd5b68f6ba1c5865a",
    "transport_mode": "0o644"
  },
  {
    "bytes": 6448,
    "path": "postscore_system_v2/complete_study/n055/journal.py",
    "runtime_mode": "0o644",
    "sha256": "9846cba35f63a69823e57c6cb00b34f65d8f08a33fc04267bfad3169115b3738",
    "transport_mode": "0o644"
  },
  {
    "bytes": 18104,
    "path": "postscore_system_v2/complete_study/n055/learning.py",
    "runtime_mode": "0o644",
    "sha256": "01737a462f4625f8845bf747af349242d5cb141d95b46901e7fa4b7b315594fc",
    "transport_mode": "0o644"
  },
  {
    "bytes": 35669,
    "path": "postscore_system_v2/complete_study/n055/native.py",
    "runtime_mode": "0o644",
    "sha256": "2c8a86128b41d69a0e137876d63ddff90ffe0e0be86a6e47f31c2ec9952517ef",
    "transport_mode": "0o644"
  },
  {
    "bytes": 6932,
    "path": "postscore_system_v2/complete_study/n055/native_providers.py",
    "runtime_mode": "0o644",
    "sha256": "1c2560962a3fa15df2f1361f14778444af8ad3cc1a3cb58b3b04a7d4fb51cda0",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5541,
    "path": "postscore_system_v2/complete_study/n055/original_r1.py",
    "runtime_mode": "0o444",
    "sha256": "6955d03232b545a4df0694669cb41338aa77bb24e23e9a8f7b838dd4085c09dd",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1999,
    "path": "postscore_system_v2/complete_study/n055/participant_contract.py",
    "runtime_mode": "0o644",
    "sha256": "e61ebb304a51f672db86f1319e9d9cc596d1eaa85b7668bfe6fc9b19a4a30a7e",
    "transport_mode": "0o644"
  },
  {
    "bytes": 3539,
    "path": "postscore_system_v2/complete_study/n055/plan.py",
    "runtime_mode": "0o644",
    "sha256": "995a97739e565023df3cb99800a761e0ecc43445f07aac8a0a4b93fef8b83fe5",
    "transport_mode": "0o644"
  },
  {
    "bytes": 22969,
    "path": "postscore_system_v2/complete_study/n055/postscore_dispatch.py",
    "runtime_mode": "0o644",
    "sha256": "d030e240626b97a49375b49a1b0400e4c08c840c8cc6be4565dffeb3e208070e",
    "transport_mode": "0o644"
  },
  {
    "bytes": 3071,
    "path": "postscore_system_v2/complete_study/n055/postscore_policy.py",
    "runtime_mode": "0o644",
    "sha256": "ea71ef2b201e7e5bf590562ae8f5188f8c69a6a4156f70b3004ed519778119b4",
    "transport_mode": "0o644"
  },
  {
    "bytes": 15542,
    "path": "postscore_system_v2/complete_study/n055/postscore_reserved.py",
    "runtime_mode": "0o644",
    "sha256": "2f1628dd9b36c782bfe7c256b316de819d881c93ee7c28a243c556bbb872ae41",
    "transport_mode": "0o644"
  },
  {
    "bytes": 39168,
    "path": "postscore_system_v2/complete_study/n055/postscore_role_host.py",
    "runtime_mode": "0o644",
    "sha256": "b89d9144ec72b8d510b0315cf628979df02b48d65239ce81b638e5f8426da56d",
    "transport_mode": "0o644"
  },
  {
    "bytes": 30537,
    "path": "postscore_system_v2/complete_study/n055/postscore_services.py",
    "runtime_mode": "0o644",
    "sha256": "777c5dd7a4efa99da2c2ffdbf92a5d477cddfbee6c40be35ab6d3f3c160cd56f",
    "transport_mode": "0o644"
  },
  {
    "bytes": 24871,
    "path": "postscore_system_v2/complete_study/n055/postscore_v2.py",
    "runtime_mode": "0o644",
    "sha256": "3b9c3de4a7eb4fc9aed87421b337964b1fefe2a46ace7d595b076cf288814743",
    "transport_mode": "0o644"
  },
  {
    "bytes": 22111,
    "path": "postscore_system_v2/complete_study/n055/process.py",
    "runtime_mode": "0o644",
    "sha256": "8cd91d2c84842c39e1bbf87c5225439116479db59889ad8736b7b0f312839637",
    "transport_mode": "0o644"
  },
  {
    "bytes": 4946,
    "path": "postscore_system_v2/complete_study/n055/programmes.py",
    "runtime_mode": "0o644",
    "sha256": "2fcc3d57d7f02605c1c5ec039e40919516ae8c897b6a5f41fd5afdf359cb457f",
    "transport_mode": "0o644"
  },
  {
    "bytes": 14174,
    "path": "postscore_system_v2/complete_study/n055/protected.py",
    "runtime_mode": "0o644",
    "sha256": "39b412561ff2bfa9d37ee756ced3e7173759e8886621c3378688028a4e341020",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5029,
    "path": "postscore_system_v2/complete_study/n055/registry.py",
    "runtime_mode": "0o644",
    "sha256": "eeafc6239e3bdbaa9639f9fba99b0f51601aae2f9d0dce2a0cae89e725f5a3c2",
    "transport_mode": "0o644"
  },
  {
    "bytes": 12899,
    "path": "postscore_system_v2/complete_study/n055/reporting.py",
    "runtime_mode": "0o644",
    "sha256": "d47c12b6af7f13d416c98cfed88a42274cc09aeb490a808dbc9a5163407ec2af",
    "transport_mode": "0o644"
  },
  {
    "bytes": 4915,
    "path": "postscore_system_v2/complete_study/n055/resource_policy.py",
    "runtime_mode": "0o644",
    "sha256": "ede9ca66e530efcedfd581b32c9855d82c1f9316146f0aa134e51b5d61183151",
    "transport_mode": "0o644"
  },
  {
    "bytes": 3154,
    "path": "postscore_system_v2/complete_study/n055/review_service.py",
    "runtime_mode": "0o644",
    "sha256": "197bf95d1368a4c8698907ba4c62fb4f6d0635c2be1be5baa8114d1a6117be5e",
    "transport_mode": "0o644"
  },
  {
    "bytes": 2356,
    "path": "postscore_system_v2/complete_study/n055/schedule.py",
    "runtime_mode": "0o644",
    "sha256": "f44f3bd75667426bd19fee8a8576821c2684f63fbfd3ba5cc47c7388ec8d0ce0",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5528,
    "path": "postscore_system_v2/complete_study/n055/seals.py",
    "runtime_mode": "0o644",
    "sha256": "1d9b76c2d117418372f31dfb48a89d57e47355dfd10bc4b6fca0e0d38fabb670",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5185,
    "path": "postscore_system_v2/complete_study/n055/source.py",
    "runtime_mode": "0o644",
    "sha256": "e7c7d1fa0d286b6b9381da0b0f43f13bd4458bf5aec4b16d636e27dd9aaa063b",
    "transport_mode": "0o644"
  },
  {
    "bytes": 3219,
    "path": "postscore_system_v2/complete_study/n055/streaming.py",
    "runtime_mode": "0o644",
    "sha256": "b2bae4d9d78833480617ceb97db9c51c38fae2d9de97ba594e7fa1fd1820f12e",
    "transport_mode": "0o644"
  },
  {
    "bytes": 9616,
    "path": "postscore_system_v2/complete_study/n055/views.py",
    "runtime_mode": "0o644",
    "sha256": "2a933cff348129613db4ecb19c1ddb32b7490e58cbab633d3cbdcdadbe57c1bb",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1985,
    "path": "postscore_system_v2/complete_study/phase_entry.py",
    "runtime_mode": "0o644",
    "sha256": "61e35be995a8f5e061ebf74b9903f6891059d4f1573aafad470ef3e224744799",
    "transport_mode": "0o644"
  },
  {
    "bytes": 3308,
    "path": "postscore_system_v2/complete_study/postscore_gated_clone.c",
    "runtime_mode": "0o644",
    "sha256": "d55b88158539ddfe21b59f60245f00db45087adb5fb76550621e15f2c4488b6a",
    "transport_mode": "0o644"
  },
  {
    "bytes": 18189,
    "path": "postscore_system_v2/complete_study/postscore_role_worker.py",
    "runtime_mode": "0o644",
    "sha256": "d07df2f79c6787a01bd00eb70830d5bfd0df0fd3e55397e9cecc3a5e7fc9d93d",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1471,
    "path": "postscore_system_v2/complete_study/public/BROKER_REQUEST_SCHEMA.json",
    "runtime_mode": "0o644",
    "sha256": "602890f9179fa8d08b7b7ac825de04cf9c2f9adfcb244ab6c0e57612439ef91e",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1256,
    "path": "postscore_system_v2/complete_study/public/BROKER_RESPONSE_SCHEMA.json",
    "runtime_mode": "0o644",
    "sha256": "ecaf8329cece6fd419c076bd7936f5932f1d5527dfb7cf0b28e5c84310fbe2dc",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1058,
    "path": "postscore_system_v2/complete_study/public/CASE_SCHEMA.json",
    "runtime_mode": "0o644",
    "sha256": "bfaca28e448bcecc4a521efd5eb597724d19ce41995358159546f2c54da7130e",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1184,
    "path": "postscore_system_v2/complete_study/public/CELL_SCHEMA.json",
    "runtime_mode": "0o644",
    "sha256": "fd4e5c84c7d02282317d2169a5214c5e6ebc1c521cbf1de4d6ee54ee974682f9",
    "transport_mode": "0o644"
  },
  {
    "bytes": 669,
    "path": "postscore_system_v2/complete_study/public/OPERATIONS_SCHEMA.json",
    "runtime_mode": "0o644",
    "sha256": "174b0fda011134bf7633583f51194fdd3882ea84330581a689966741759bbc2b",
    "transport_mode": "0o644"
  },
  {
    "bytes": 2415,
    "path": "postscore_system_v2/complete_study/public/POLICY.json",
    "runtime_mode": "0o644",
    "sha256": "e07436584593fe62e830e76ad8d75e14e2877edc90b711933f05c09beaa7c7c6",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1854,
    "path": "postscore_system_v2/complete_study/public/PREDICTION_SCHEMA.json",
    "runtime_mode": "0o644",
    "sha256": "a5abbb135e3ccf396fbac4c017f974dc9c27086969901924fa5cea8b822aca31",
    "transport_mode": "0o644"
  },
  {
    "bytes": 3169,
    "path": "postscore_system_v2/complete_study/public/PREEXPOSURE_POLICY_SCHEMA.json",
    "runtime_mode": "0o644",
    "sha256": "eb3fc851f541d1c0f68ed4d7845ffa4e7d927e5d3b3ce41dbb8a8e0a56c98b74",
    "transport_mode": "0o644"
  },
  {
    "bytes": 14810,
    "path": "postscore_system_v2/complete_study/public/PROGRAM_ABI_V3.md",
    "runtime_mode": "0o644",
    "sha256": "bd577b3095d9c55707edeb6b12e0dd3796e5753fd74e92da84d7c93574d5af9d",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5340,
    "path": "postscore_system_v2/complete_study/public/RESOURCE_POLICY_V1.json",
    "runtime_mode": "0o644",
    "sha256": "b896b8e175cd401c70ed37584e9aa797407c89dd6d5e1c0e31b1ac286b79711a",
    "transport_mode": "0o644"
  },
  {
    "bytes": 2137,
    "path": "postscore_system_v2/complete_study/public/SELECTED_METHOD_SCHEMA.json",
    "runtime_mode": "0o644",
    "sha256": "5f62cce4c6b22c69797fa5193c98572025ffc9fe0863aa81960d60573618d907",
    "transport_mode": "0o644"
  },
  {
    "bytes": 6764,
    "path": "postscore_system_v2/complete_study/public/TASK.md",
    "runtime_mode": "0o644",
    "sha256": "e5311daa10d45d63e61c04aab9b06e194ae1abb1ac0af700f1a9287368e683b5",
    "transport_mode": "0o644"
  },
  {
    "bytes": 3914,
    "path": "postscore_system_v2/complete_study/public/interface.py",
    "runtime_mode": "0o644",
    "sha256": "ccabe30238b084b19422c920877332232d730caca712f3679b73e6c28fcb3e0c",
    "transport_mode": "0o644"
  },
  {
    "bytes": 8283,
    "path": "postscore_system_v2/complete_study/reference_entry.py",
    "runtime_mode": "0o644",
    "sha256": "1a0d4bda95ae5dd73e4fba2564532d5c45364ade8e0bf30c4690982c64b25dac",
    "transport_mode": "0o644"
  },
  {
    "bytes": 4285,
    "path": "postscore_system_v2/complete_study/tool_provider_entry.py",
    "runtime_mode": "0o644",
    "sha256": "f104b3555dcedcdfba523fa61a330a09f69bdc5e8e82785ae7f939d96b9776fc",
    "transport_mode": "0o644"
  },
  {
    "bytes": 889,
    "path": "postscore_system_v2/environment-v1/feature/Dockerfile",
    "runtime_mode": "0o644",
    "sha256": "ae0d674c804b85b345a0cd1b1a186823736422a72aef8e484359b5c901fb593f",
    "transport_mode": "0o644"
  },
  {
    "bytes": 13629,
    "path": "postscore_system_v2/environment-v1/feature/README.md",
    "runtime_mode": "0o644",
    "sha256": "64efe5dae237ff556320776f15886d7b256534c1e94eb23ef0f3e327374f8ae1",
    "transport_mode": "0o644"
  },
  {
    "bytes": 6455,
    "path": "postscore_system_v2/environment-v1/feature/SOURCE_AND_ARTIFACT_BINDINGS.json",
    "runtime_mode": "0o644",
    "sha256": "a350ac8b00dfc791abb0cbb8398b71de2b7466552b00088937c287cccce17542",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5689,
    "path": "postscore_system_v2/environment-v1/feature/WHEEL_ARTIFACTS.json",
    "runtime_mode": "0o644",
    "sha256": "36d52d019685a410e4d8b8c4a9e89b597237f17544accb9a59df452a3e1dc848",
    "transport_mode": "0o644"
  },
  {
    "bytes": 13770,
    "path": "postscore_system_v2/environment-v1/feature/feature_environment.py",
    "runtime_mode": "0o644",
    "sha256": "82cb2002dfaed427f5ef1bfc03fa00d0a443ff5ad1b285c99bcaa04ba0397a83",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1908,
    "path": "postscore_system_v2/environment-v1/feature/requirements-artifacts.lock",
    "runtime_mode": "0o644",
    "sha256": "267a728daff50fdf17243557315b9eaa0995d8a0f2f1f9c7ba12d57d2be47261",
    "transport_mode": "0o644"
  },
  {
    "bytes": 103,
    "path": "postscore_system_v2/environment-v1/feature/requirements-support.txt",
    "runtime_mode": "0o644",
    "sha256": "dadb5bb7cedd592f0161cd96ecef272016a61e30b775a3b74413ab4a38bb09cf",
    "transport_mode": "0o644"
  },
  {
    "bytes": 42,
    "path": "postscore_system_v2/environment-v1/feature/requirements-torch.txt",
    "runtime_mode": "0o644",
    "sha256": "ff3fdc84aa3aae7296eb2141f5e1c1a89b91014f9626ccc379ee03fcdd4397b0",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1274,
    "path": "postscore_system_v2/environment-v1/roles/Dockerfile",
    "runtime_mode": "0o644",
    "sha256": "0f4b8628ef28de6a52e1125bc3f0b3a42f4ee7ff6558e96b7aab1d08f39d0aa3",
    "transport_mode": "0o644"
  },
  {
    "bytes": 7838,
    "path": "postscore_system_v2/environment-v1/roles/README.md",
    "runtime_mode": "0o644",
    "sha256": "197c2d5ec665a5e3936022d73a11e86df6dee3421c7c39f42aedabed24b85451",
    "transport_mode": "0o644"
  },
  {
    "bytes": 19743,
    "path": "postscore_system_v2/environment-v1/roles/campaign/ENVIRONMENT_LOCK.json",
    "runtime_mode": "0o644",
    "sha256": "3015e3dd1f8ce816a71d6a531fc988681ca3e65e4a2d96b4a6b94a1bcd184dd8",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5739,
    "path": "postscore_system_v2/environment-v1/roles/campaign/requirements-artifacts.lock",
    "runtime_mode": "0o644",
    "sha256": "251c16beed2bb31979a82f827121bd0d90c30cffb58bc197a3625b3aa15e302e",
    "transport_mode": "0o644"
  },
  {
    "bytes": 2314,
    "path": "postscore_system_v2/environment-v1/roles/campaign/requirements.lock",
    "runtime_mode": "0o644",
    "sha256": "52ba275ebc8bfcd4bf807140c0817c0fc9085ff4475489b97926c169f177d3f4",
    "transport_mode": "0o644"
  },
  {
    "bytes": 3811,
    "path": "postscore_system_v2/environment-v1/roles/controller/ENVIRONMENT_LOCK.json",
    "runtime_mode": "0o644",
    "sha256": "ad308b80cb9926f80065b244820aa98601fe876878a574ee994226723fbbe2b3",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1038,
    "path": "postscore_system_v2/environment-v1/roles/controller/requirements-artifacts.lock",
    "runtime_mode": "0o644",
    "sha256": "8fe4bea7d76d3369486ffb999b730f6f6ece65755bbb28dd7ddcb43fa0d5d84f",
    "transport_mode": "0o644"
  },
  {
    "bytes": 379,
    "path": "postscore_system_v2/environment-v1/roles/controller/requirements.lock",
    "runtime_mode": "0o644",
    "sha256": "9763649c2c097c793fad52b47461a3a99f927393ae8caf2b1a957abf927a0533",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1256,
    "path": "postscore_system_v2/environment-v1/roles/ingestion/ENVIRONMENT_LOCK.json",
    "runtime_mode": "0o644",
    "sha256": "1c4cef1f867f3667f917df25cf49571bf70c867a7d385631c563bf0817e6b4d6",
    "transport_mode": "0o644"
  },
  {
    "bytes": 266,
    "path": "postscore_system_v2/environment-v1/roles/ingestion/requirements-artifacts.lock",
    "runtime_mode": "0o644",
    "sha256": "7914bfa65412e2a770e5f34a3218f526d926753c1f2e21f935fe8b5416b96fce",
    "transport_mode": "0o644"
  },
  {
    "bytes": 92,
    "path": "postscore_system_v2/environment-v1/roles/ingestion/requirements.lock",
    "runtime_mode": "0o644",
    "sha256": "5140d0b641569a495f123e77ab32b3f03fd1759ff38df43faecdb081871adb30",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5104,
    "path": "postscore_system_v2/environment-v1/roles/inspect_environment.py",
    "runtime_mode": "0o644",
    "sha256": "90394db685c53fe088a3cb8d76d7de387437216dd7c48509d5ad821079e2a9ed",
    "transport_mode": "0o644"
  },
  {
    "bytes": 3836,
    "path": "postscore_system_v2/environment-v1/roles/verify_wheels.py",
    "runtime_mode": "0o644",
    "sha256": "ef2e467d42b35e96d515a409c285af5fd835dc9b34db4eba2ad71ec16c86fcac",
    "transport_mode": "0o644"
  },
  {
    "bytes": 8343,
    "path": "postscore_system_v2/inspect_source.py",
    "runtime_mode": "0o644",
    "sha256": "7dfce72658a4105e7683d7f4343f055bce7e47519507a1f04025a6dadba762d3",
    "transport_mode": "0o644"
  },
  {
    "bytes": 14014,
    "path": "postscore_system_v2/model_system/README.md",
    "runtime_mode": "0o644",
    "sha256": "5571c0b01a96c14528ef290f0709bcb5416ac20b70b113166c61955c27de0174",
    "transport_mode": "0o644"
  },
  {
    "bytes": 13464,
    "path": "postscore_system_v2/model_system/authoring.py",
    "runtime_mode": "0o644",
    "sha256": "396a381285dc02e47f3a4e85a2f7807b0c7d438b97572965c13da09b61f5bc78",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5535,
    "path": "postscore_system_v2/model_system/fi_entry.py",
    "runtime_mode": "0o644",
    "sha256": "e8f2949e043883708c2d5c69bb4cc61b081f5f86e112d5718c358a32f0e35cd2",
    "transport_mode": "0o644"
  },
  {
    "bytes": 6557,
    "path": "postscore_system_v2/model_system/i-interpreter/README.md",
    "runtime_mode": "0o644",
    "sha256": "a077a16e607c4b1373c03f762707bbea72e1cc1c516937f8e12a7adf5e099b9a",
    "transport_mode": "0o644"
  },
  {
    "bytes": 45281,
    "path": "postscore_system_v2/model_system/i-interpreter/participant_template.py",
    "runtime_mode": "0o644",
    "sha256": "3de58f28fef84cc183501349c30d4b36f220f2ff681af4ac451c07242f6f0a3d",
    "transport_mode": "0o644"
  },
  {
    "bytes": 3259,
    "path": "postscore_system_v2/model_system/i_renderer.py",
    "runtime_mode": "0o644",
    "sha256": "2564400f4396bc1d46eee0daf1899e8672f02f590c01d18401764ced5259053f",
    "transport_mode": "0o644"
  },
  {
    "bytes": 6809,
    "path": "postscore_system_v2/model_system/model-job/README.md",
    "runtime_mode": "0o644",
    "sha256": "48e0d1e3bb77be9a9a317455c4d59e58e7e88cadc4b4756e9ee3007439f56612",
    "transport_mode": "0o644"
  },
  {
    "bytes": 32226,
    "path": "postscore_system_v2/model_system/model-job/model_job.py",
    "runtime_mode": "0o644",
    "sha256": "295e96a5fc77da341d5a10dada304c0fb26e22e22d68e20a2bb66d3227f434f4",
    "transport_mode": "0o644"
  },
  {
    "bytes": 9043,
    "path": "postscore_system_v2/model_system/runtime_session.py",
    "runtime_mode": "0o644",
    "sha256": "b1df8d298ca5c45067d515b511739c5985a3cb58a24faa6bc660955d2edb148f",
    "transport_mode": "0o644"
  },
  {
    "bytes": 6523,
    "path": "postscore_system_v2/model_system/source_closure.py",
    "runtime_mode": "0o644",
    "sha256": "93ae8020b1c3549db890b5c8543ec2174fc3712eb85bbef1be129bba4b63e7f4",
    "transport_mode": "0o644"
  },
  {
    "bytes": 13322,
    "path": "postscore_system_v2/operator_completion/README.md",
    "runtime_mode": "0o644",
    "sha256": "2a19df9946c3174b2dff68f50c79f6481d1e5bfd3fb70866edba32b92a27edc3",
    "transport_mode": "0o644"
  },
  {
    "bytes": 4415,
    "path": "postscore_system_v2/operator_completion/operator_entry.py",
    "runtime_mode": "0o644",
    "sha256": "8f1f0dbc9d9c1aafc96984f51a57271ad62aba9ba054a28aeeeb9515511b2158",
    "transport_mode": "0o644"
  },
  {
    "bytes": 15072,
    "path": "postscore_system_v2/operator_completion/plans.py",
    "runtime_mode": "0o644",
    "sha256": "ce37fd11d41d50daf89592592ba163bc6fd48fc2187db0b57798c304dd25793a",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1565,
    "path": "postscore_system_v2/operator_completion/plans_v2.py",
    "runtime_mode": "0o644",
    "sha256": "20df255d312edf415a425a1215cb8b855681738230b68f9dffa20bfea374bba9",
    "transport_mode": "0o644"
  },
  {
    "bytes": 19742,
    "path": "postscore_system_v2/operator_completion/preparation.py",
    "runtime_mode": "0o644",
    "sha256": "8d23de0cc50f4e935f5f3bef91dcc3084cdbc8d26359775ac39868f5603da353",
    "transport_mode": "0o644"
  },
  {
    "bytes": 6523,
    "path": "postscore_system_v2/operator_completion/source_closure.py",
    "runtime_mode": "0o644",
    "sha256": "93ae8020b1c3549db890b5c8543ec2174fc3712eb85bbef1be129bba4b63e7f4",
    "transport_mode": "0o644"
  },
  {
    "bytes": 12449,
    "path": "postscore_system_v2/role-host/README.md",
    "runtime_mode": "0o644",
    "sha256": "3b074f7e78d5fe0443db7512dbb49db64a4caa09fa1f7c988c0f36b2b03e3cbb",
    "transport_mode": "0o644"
  }
]

MEMBER_CAP = 1048576
SOURCE_CAP = 2 * 1048576
ENTRY_CAP = 256
TRANSFER_CAP = 8 * 1048576
STREAM_CAP = 16384
OUTPUT_CAP = 262144
SECONDS = 45
INSPECT_SECONDS = 30
HERE = Path(__file__).absolute().parent


def need(ok, message):
    if not ok:
        raise ValueError(message)


def identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size,
            s.st_mtime_ns, s.st_ctime_ns)


def absolute(value):
    need(type(value) is str and value and "\\" not in value
         and all(ord(c) >= 32 and ord(c) != 127 for c in value),
         "literal absolute path")
    p = Path(value)
    need(p.is_absolute() and str(p) == value and not value.startswith("//")
         and ".." not in p.parts, "canonical absolute path")
    need(not any(x.is_symlink() for x in (p, *p.parents)), "path aliases forbidden")
    return p


def selected_rows():
    rows = TRANSPORT_MANIFEST
    need(type(rows) is list and len(rows) == 130, "frozen 130-body transport required")
    names = set()
    total = 0
    for row in rows:
        need(type(row) is dict and set(row) == {
            "path", "bytes", "sha256", "transport_mode", "runtime_mode"},
            "closed transport descriptor")
        name = row["path"]
        need(type(name) is str and name and "\\" not in name
             and all(ord(c) >= 32 and ord(c) != 127 for c in name),
             "literal source member")
        p = PurePosixPath(name)
        need(not p.is_absolute() and str(p) == name and ".." not in p.parts
             and name not in names, "canonical unique source member")
        need((len(p.parts) > 1 and p.parts[0] == "postscore_system_v2"), "fixed source namespaces")
        need(type(row["bytes"]) is int and 0 < row["bytes"] <= MEMBER_CAP,
             "bounded member extent")
        h = row["sha256"]
        need(type(h) is str and len(h) == 64 and all(c in "0123456789abcdef" for c in h),
             "exact member digest")
        need(row["transport_mode"] == "0o644"
             and row["runtime_mode"] in ("0o644", "0o444"), "selected source permissions")
        names.add(name)
        total += row["bytes"]
    need(total <= SOURCE_CAP,
         "bounded fixed source transport")
    need(sum(n.startswith("postscore_system_v2/") for n in names) == 130,
         "complete source component counts")
    need(sum(r["runtime_mode"] == "0o444" for r in rows) == 12,
         "twelve readonly runtime members")
    return tuple(rows)


class Ledger:
    def __init__(self):
        self.deadline = time.monotonic() + SECONDS
        self.read_bytes = 0
        self.write_bytes = 0

    def tick(self):
        need(time.monotonic() < self.deadline, "materialization deadline")

    def reserve(self, kind, n):
        self.tick()
        need(type(n) is int and n >= 0
             and self.read_bytes + self.write_bytes + n <= TRANSFER_CAP,
             "materialization transfer allowance")
        if kind == "read":
            self.read_bytes += n
        else:
            need(kind == "write", "closed transfer kind")
            self.write_bytes += n


def read_body(path, row, mode, ledger):
    p = absolute(str(path))
    before = p.lstat()
    n = row["bytes"]
    need(type(n) is int and 0 < n <= MEMBER_CAP
         and stat.S_ISREG(before.st_mode) and before.st_nlink == 1
         and before.st_size == n and stat.S_IMODE(before.st_mode) == mode,
         "exact ordinary single-link source body")
    ledger.reserve("read", n + 1)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    first = None
    try:
        need(identity(os.fstat(fd)) == identity(before), "same opened source identity")
        parts = []
        size = 0
        while size <= n:
            part = os.read(fd, min(65536, n + 1 - size))
            if not part:
                break
            parts.append(part)
            size += len(part)
        need(identity(os.fstat(fd)) == identity(before) == identity(p.lstat()),
             "stable complete source identity")
    except BaseException as exc:
        first = exc
        raise
    finally:
        try:
            os.close(fd)
        except BaseException as secondary:
            if first is None:
                raise
            first.__dict__.setdefault("cleanup_failures", []).append(secondary)
            first.add_note("Secondary source-handle close failure: "
                           + type(secondary).__name__ + ": " + str(secondary)[:512])
    raw = b"".join(parts)
    need(len(raw) == n and hashlib.sha256(raw).hexdigest() == row["sha256"],
         "exact source body digest")
    ledger.tick()
    return raw, identity(before)


def namespace(root, rows, ledger):
    """Close only the complete postscore tree, not unrelated task siblings."""
    expected = {r["path"] for r in rows}
    expected_dirs = set()
    for name in expected:
        if "/" in name:
            expected_dirs.update(str(p) for p in PurePosixPath(name).parents if str(p) != ".")
    actual = set()
    directories = {}
    stack = [root / "postscore_system_v2"]
    entries = 0
    while stack:
        ledger.tick()
        directory = stack.pop()
        absolute(str(directory))
        s = directory.lstat()
        need(stat.S_ISDIR(s.st_mode), "ordinary selected source directory")
        directories[str(directory.relative_to(root))] = identity(s)
        stream = os.scandir(directory)
        first = None
        try:
            for entry in stream:
                entries += 1
                need(entries <= ENTRY_CAP, "bounded selected source namespace")
                s = entry.stat(follow_symlinks=False)
                p = Path(entry.path)
                if stat.S_ISDIR(s.st_mode):
                    stack.append(p)
                else:
                    need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1,
                         "no aliases or special source members")
                    actual.add(str(p.relative_to(root)))
        except BaseException as exc:
            first = exc
            raise
        finally:
            try:
                stream.close()
            except BaseException as secondary:
                if first is None:
                    raise
                first.__dict__.setdefault("cleanup_failures", []).append(secondary)
                first.add_note("Secondary source-iterator close failure: "
                               + type(secondary).__name__ + ": " + str(secondary)[:512])
        need(identity(directory.lstat()) == directories[str(directory.relative_to(root))],
             "stable source directory listing")
    need(actual == expected and set(directories) == expected_dirs,
         "exact complete selected namespaces")
    return directories


def unchanged(root, files, directories):
    for name, stamp in (*files.items(), *directories.items()):
        need(identity((root / name).lstat()) == stamp, "selected source identity unchanged")


def bounded_child(argv, ledger, timeout):
    """Run one trusted source-inspection/argument parser, with bounded two pipes."""
    ledger.tick()
    end = min(ledger.deadline, time.monotonic() + timeout)
    # Reserve both full stream capacities before launch; failures stay charged.
    ledger.reserve("read", 2 * STREAM_CAP)
    child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, close_fds=True,
                             env={k: v for k, v in os.environ.items()
                                  if not k.startswith("PYTHON")})
    selected = selectors.DefaultSelector()
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    first = None
    try:
        for name, pipe in (("stdout", child.stdout), ("stderr", child.stderr)):
            os.set_blocking(pipe.fileno(), False)
            selected.register(pipe, selectors.EVENT_READ, name)
        while selected.get_map():
            remaining = end - time.monotonic()
            need(remaining > 0, "trusted source child hard timeout")
            for key, _ in selected.select(min(remaining, 0.1)):
                name = key.data
                left = STREAM_CAP - len(buffers[name])
                data = os.read(key.fileobj.fileno(), min(65536, left + 1))
                need(len(data) <= left, "trusted source child stream bound")
                if data:
                    buffers[name].extend(data)
                else:
                    selected.unregister(key.fileobj)
                    key.fileobj.close()
        remaining = end - time.monotonic()
        need(remaining > 0, "trusted source child final deadline")
        code = child.wait(timeout=remaining)
        ledger.tick()
        return {"returncode": code,
                "stdout": bytes(buffers["stdout"]).decode("utf8"),
                "stderr": bytes(buffers["stderr"]).decode("utf8")}
    except BaseException as exc:
        first = exc
        exc.child_original = {"returncode": child.poll(),
                              "stdout": bytes(buffers["stdout"]).decode("utf8", "replace"),
                              "stderr": bytes(buffers["stderr"]).decode("utf8", "replace"),
                              "incomplete_capture": True}
        raise
    finally:
        # The selected inspector has no descendants. No native process is launched.
        cleanup_error = None
        try:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=2)
        except BaseException as exc:
            cleanup_error = exc
        try:
            selected.close()
            for pipe in (child.stdout, child.stderr):
                if not pipe.closed:
                    pipe.close()
        except BaseException as exc:
            if cleanup_error is None:
                cleanup_error = exc
        if cleanup_error is not None:
            if first is None:
                raise cleanup_error
            first.add_note("Source child cleanup also failed: " + type(cleanup_error).__name__)


class Materializer:
    def __init__(self):
        self.root = absolute(str(HERE))
        self.rows = selected_rows()
        self.ledger = Ledger()
        self.stage = "not_started"
        self.created = False
        self.destination = None
        self.copied = []
        self.files = {}
        self.directories = {}
        self.inspector_original = None

    def capture(self):
        self.stage = "source_capture"
        self.directories = namespace(self.root, self.rows, self.ledger)
        bodies = {}
        for row in self.rows:
            raw, stamp = read_body(self.root / row["path"], row, 0o644, self.ledger)
            bodies[row["path"]] = raw
            self.files[row["path"]] = stamp
        unchanged(self.root, self.files, self.directories)
        return bodies

    def make_directory(self, path):
        """Set exact selected modes through the fresh owned directory handle."""
        self.ledger.tick()
        path = absolute(str(path))
        path.mkdir(mode=0o700)
        before = path.lstat()
        need(stat.S_ISDIR(before.st_mode) and before.st_uid == os.getuid(),
             "fresh owned directory")
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        first = None
        try:
            need(identity(os.fstat(fd)) == identity(before), "same owned directory handle")
            os.fchmod(fd, 0o755)
            after = os.fstat(fd)
            need(stat.S_ISDIR(after.st_mode) and stat.S_IMODE(after.st_mode) == 0o755
                 and identity(after) == identity(path.lstat()), "exact owned directory mode")
            self.ledger.tick()
        except BaseException as exc:
            first = exc
            raise
        finally:
            try:
                os.close(fd)
            except BaseException as secondary:
                if first is None:
                    raise
                first.__dict__.setdefault("cleanup_failures", []).append(secondary)
                first.add_note("Owned directory close also failed: " + repr(secondary))

    def write_body(self, path, row, raw):
        self.ledger.reserve("write", len(raw))
        absolute(str(path))
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                     | os.O_CLOEXEC, 0o600)
        first = None
        try:
            before = os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                 "fresh ordinary owned output")
            offset = 0
            while offset < len(raw):
                n = os.write(fd, memoryview(raw)[offset:])
                need(type(n) is int and n > 0, "positive owned write")
                offset += n
                self.ledger.tick()
            os.fchmod(fd, int(row["runtime_mode"], 8))
            os.fsync(fd)
            need(identity(os.fstat(fd)) == identity(path.lstat()),
                 "same owned output path")
        except BaseException as exc:
            first = exc
            raise
        finally:
            try:
                os.close(fd)
            except BaseException:
                if first is None:
                    raise
                first.add_note("Output close also failed; original failure and partial tree remain.")

    def run(self, output):
        self.destination = absolute(str(output))
        need(not os.path.lexists(self.destination), "fresh output required")
        need(not self.destination.is_relative_to(self.root)
             and not self.root.is_relative_to(self.destination), "source/output disjoint")
        parent = self.destination.parent
        s = parent.lstat()
        need(stat.S_ISDIR(s.st_mode) and s.st_uid == os.getuid()
             and stat.S_IMODE(s.st_mode) & 0o022 == 0, "existing operator-owned output parent")
        parent_identity = (s.st_dev, s.st_ino, s.st_uid, s.st_mode)
        bodies = self.capture()  # Authenticate all transport before creating output.
        s = parent.lstat()
        need((s.st_dev, s.st_ino, s.st_uid, s.st_mode) == parent_identity,
             "same owned output parent")
        self.destination.mkdir(mode=0o700)
        self.created = True
        self.stage = "copy"
        expected_dirs = set()
        for row in self.rows:
            expected_dirs.update(str(p) for p in PurePosixPath(row["path"]).parents
                                 if str(p) != ".")
        for name in sorted(expected_dirs, key=lambda n: (n.count("/"), n)):
            self.make_directory(self.destination / name)
        for row in self.rows:
            path = self.destination / row["path"]
            self.write_body(path, row, bodies[row["path"]])
            self.copied.append(row["path"])
        del bodies
        self.stage = "owned_readback"
        directories = namespace(self.destination, self.rows, self.ledger)
        need(all(stat.S_IMODE(stamp[2]) == 0o755 for stamp in directories.values()),
             "exact selected output directory modes")
        files = {}
        for row in self.rows:
            _, files[row["path"]] = read_body(
                self.destination / row["path"], row, int(row["runtime_mode"], 8), self.ledger)
        unchanged(self.root, self.files, self.directories)
        self.stage = "actual_source_inspector"
        # Prospectively reserve its complete source read ceiling before launch.
        self.ledger.reserve("read", SOURCE_CAP)
        original = bounded_child(
            [sys.executable, "-I", "-S", "-B",
             str(self.destination / "postscore_system_v2/inspect_source.py"), "--inspect"],
            self.ledger, INSPECT_SECONDS)
        self.inspector_original = original
        need(original["returncode"] == 0, "actual source inspector natural exit zero required")
        inspected = json.loads(original["stdout"])
        need(inspected.get("status") == "source_only"
             and inspected.get("scientific_execution") is False
             and inspected.get("scientific_inputs_opened") is False
             and inspected.get("study_modules_imported") is False,
             "actual source-only inspection result")
        # The preceding reservation is retained, not refunded to this actual count.
        n = inspected.get("inspection_read_bytes")
        need(type(n) is int and 0 < n <= SOURCE_CAP, "bounded inspector source-read report")
        unchanged(self.destination, files, directories)
        unchanged(self.root, self.files, self.directories)
        self.ledger.tick()
        self.stage = "complete"
        return {"schema": "neural055_owned_public_postscore_source_v1", "status": "source_only",
                "materialized_root": str(self.destination), "source_files": 130,
                "readonly_runtime_members": 12, "inspection": inspected,
                "inspector_original": original,
                "logical_read_reserved_bytes": self.ledger.read_bytes,
                "logical_write_reserved_bytes": self.ledger.write_bytes,
                "scientific_execution": False, "benchmark_count_delta": 0,
                "authenticity": "reviewed executable/commit selection, not self-certification"}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    p.add_argument("--materialize", required=True)
    p.add_argument("--inspect", required=True, action="store_true")
    args = p.parse_args(argv)
    worker = Materializer()
    try:
        result = worker.run(args.materialize)
    except BaseException as exc:
        result = {"status": "unavailable", "stage": worker.stage,
                  "owned_partial_preserved": worker.created,
                  "materialized_root": str(worker.destination),
                  "completed_copies": len(worker.copied),
                  "inspector_original": (worker.inspector_original or getattr(exc, "child_original", None)),
                  "first_error_type": type(exc).__name__, "first_error": str(exc)[:1024],
                  "scientific_execution": False}
        raw = json.dumps(result, sort_keys=True) + "\n"
        need(len(raw.encode()) <= OUTPUT_CAP, "bounded failure output")
        sys.stderr.write(raw)
        raise
    raw = (json.dumps(result, sort_keys=True, allow_nan=False) + "\n").encode()
    need(len(raw) <= OUTPUT_CAP, "bounded materialization result")
    worker.ledger.tick()
    written = sys.stdout.buffer.write(raw)
    need(type(written) is int and written == len(raw), 'complete materialization output')
    sys.stdout.buffer.flush()
    worker.ledger.tick()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

