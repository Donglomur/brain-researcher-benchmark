"""Materialize the fixed public source into a fresh owned tree, then inspect.

The reviewed commit authenticates this executable; this helper does not certify
itself. Only the fixed 88-body transport is admitted. No study input, model,
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

# Parent injects exactly one final reviewed 88-row literal before publication.
TRANSPORT_MANIFEST = [
  {
    "bytes": 3142,
    "path": "SOURCE_COMPONENTS.json",
    "runtime_mode": "0o644",
    "sha256": "ac518de0c3e979c673df2b9a63396d2b3f47f5556f233c2cdeed5da9ed37346c",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5244,
    "path": "complete_study/FEATURE_PREPARATION.md",
    "runtime_mode": "0o644",
    "sha256": "bcc7ede6fbe0bbee007685fdf1396b4cbe15f610777bca396602369cc58862b3",
    "transport_mode": "0o644"
  },
  {
    "bytes": 2796,
    "path": "complete_study/LEGACY_ROLES.json",
    "runtime_mode": "0o644",
    "sha256": "6a6f9e06444ce8ef866672a0923d9fad00e3f56a5b27793a7b17f681cae9c136",
    "transport_mode": "0o644"
  },
  {
    "bytes": 15355,
    "path": "complete_study/OPERATING_CONTRACT_V3.md",
    "runtime_mode": "0o644",
    "sha256": "90909f424996769aeacddf74414ce0a757ab3df7ac1b284a6e297abddf444921",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5908,
    "path": "complete_study/README.md",
    "runtime_mode": "0o644",
    "sha256": "bf201e2e233dfa28d1af487aac957e847e4a50f537f7f7cb25e8e00f40ae26aa",
    "transport_mode": "0o644"
  },
  {
    "bytes": 16641,
    "path": "complete_study/RUNTIME_SOURCE_MANIFEST.json",
    "runtime_mode": "0o644",
    "sha256": "1e3ec2628854c3038cc446a74e0bb29e786649ae2d84dbc17f69334529185bf9",
    "transport_mode": "0o644"
  },
  {
    "bytes": 2195,
    "path": "complete_study/broker_client.py",
    "runtime_mode": "0o644",
    "sha256": "55a27f5c199400012f852206f2754872a3dc73013c5dbd859261a5b190f3badf",
    "transport_mode": "0o644"
  },
  {
    "bytes": 8013,
    "path": "complete_study/capture_entry.py",
    "runtime_mode": "0o644",
    "sha256": "f6a171d1b1f4511f1ca7f848cf7d7002672825a5ec8b1da7fa955fa9108f61b7",
    "transport_mode": "0o644"
  },
  {
    "bytes": 4431,
    "path": "complete_study/central_entry.py",
    "runtime_mode": "0o644",
    "sha256": "b69df03b5a9ff93329d0ce0df363675c79b8d078929c05f761716c65c34abd96",
    "transport_mode": "0o644"
  },
  {
    "bytes": 7938,
    "path": "complete_study/contracts/CONTRASTS.json",
    "runtime_mode": "0o644",
    "sha256": "b5b24650a8288272cd4642bb76bb68ffead79b1c116a5f7c43062874925d2411",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5317,
    "path": "complete_study/contracts/ISOLATION_CONTRACT.json",
    "runtime_mode": "0o644",
    "sha256": "4327e061f8f2bde65aaccbb7ca1bfe7832c8c88f23be5cacd57d886f69487d34",
    "transport_mode": "0o644"
  },
  {
    "bytes": 4510,
    "path": "complete_study/contracts/MODE_PERMISSIONS.json",
    "runtime_mode": "0o644",
    "sha256": "43e935217e43926337b740d76ca198116ba2b0864dd80bbd1c6f31aea849dee1",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5535,
    "path": "complete_study/contracts/POSTSCORE_CONTRACT.md",
    "runtime_mode": "0o644",
    "sha256": "08eb9ca53d1d49cc133c5a9d5d86b96b0b774ed5b33f754ec14a74d60821b1d0",
    "transport_mode": "0o644"
  },
  {
    "bytes": 9765,
    "path": "complete_study/contracts/REPORT_HIERARCHY.json",
    "runtime_mode": "0o644",
    "sha256": "649784fcf8f3a128466ee06704e66ee4648fbd50d6fbbca191c8750a22339ffb",
    "transport_mode": "0o644"
  },
  {
    "bytes": 13469,
    "path": "complete_study/contracts/RESOURCE_DEFINITION.md",
    "runtime_mode": "0o644",
    "sha256": "c63d5db851c8e0e8460119ec8922a0e77119cd25095cb57acfdc17fe37cc8542",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5124,
    "path": "complete_study/contracts/RESOURCE_POLICY_V1.json",
    "runtime_mode": "0o644",
    "sha256": "d87a869636bad14078418685a6e5a2d498c5349c5a0c82f672f7e423cb8b516d",
    "transport_mode": "0o644"
  },
  {
    "bytes": 9678,
    "path": "complete_study/contracts/TRUSTED_BROKER_CONTRACT_V3.json",
    "runtime_mode": "0o644",
    "sha256": "c55f7ae042d574ce2e4c1ac6ddfef48b340d2959a60ec1a145da58332d769054",
    "transport_mode": "0o644"
  },
  {
    "bytes": 16199,
    "path": "complete_study/legacy/015/packet.py",
    "runtime_mode": "0o644",
    "sha256": "a08ab5725aa95c3603a37c588d52b19a5a0cb50f42af6c0a2d3d9eee007d80f5",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5554,
    "path": "complete_study/legacy/020/grade.py",
    "runtime_mode": "0o444",
    "sha256": "3a7581455fed1de2c164bacc1db6b1838f5ef0b883e3213d98749026e43a780d",
    "transport_mode": "0o644"
  },
  {
    "bytes": 10420,
    "path": "complete_study/legacy/022/build_case.py",
    "runtime_mode": "0o444",
    "sha256": "1cf45a94db6b2d6b359b9d56672f9dccc3226af2def501240655b84f12ddec15",
    "transport_mode": "0o644"
  },
  {
    "bytes": 2940,
    "path": "complete_study/legacy/023/build_panel.py",
    "runtime_mode": "0o444",
    "sha256": "8bdf8afd76ef356fd3b5c0c3c672edfac061b17cbae5b8d94effa7464b19824f",
    "transport_mode": "0o644"
  },
  {
    "bytes": 6949,
    "path": "complete_study/legacy/024/metadata_core.py",
    "runtime_mode": "0o444",
    "sha256": "45fe4b4ad92b8fc5e1fc2e883d4a61e2285630513d20321e8584aab1542fec95",
    "transport_mode": "0o644"
  },
  {
    "bytes": 3892,
    "path": "complete_study/legacy/025/source_io.py",
    "runtime_mode": "0o444",
    "sha256": "a3947a17b05bd0a3c63962ecb69643ee1a54b461be21f053a057aea3d3fd9bea",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5315,
    "path": "complete_study/legacy/026/stage_source.py",
    "runtime_mode": "0o444",
    "sha256": "2d5cb7b7c75d8f139208c6546dc89391cf4d04d21fd01643aff9bcdacd768a93",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5541,
    "path": "complete_study/legacy/027/reference_core.py",
    "runtime_mode": "0o444",
    "sha256": "6955d03232b545a4df0694669cb41338aa77bb24e23e9a8f7b838dd4085c09dd",
    "transport_mode": "0o644"
  },
  {
    "bytes": 7789,
    "path": "complete_study/legacy/028/scorer.py",
    "runtime_mode": "0o444",
    "sha256": "32d523db849cf8f32120e44d2f5cdb47b46bd8d9657d8e3f05310d1c28f264f8",
    "transport_mode": "0o644"
  },
  {
    "bytes": 2415,
    "path": "complete_study/legacy/029/POLICY.json",
    "runtime_mode": "0o444",
    "sha256": "e07436584593fe62e830e76ad8d75e14e2877edc90b711933f05c09beaa7c7c6",
    "transport_mode": "0o644"
  },
  {
    "bytes": 6764,
    "path": "complete_study/legacy/030/TASK.md",
    "runtime_mode": "0o444",
    "sha256": "e5311daa10d45d63e61c04aab9b06e194ae1abb1ac0af700f1a9287368e683b5",
    "transport_mode": "0o644"
  },
  {
    "bytes": 3914,
    "path": "complete_study/legacy/031/interface.py",
    "runtime_mode": "0o444",
    "sha256": "ccabe30238b084b19422c920877332232d730caca712f3679b73e6c28fcb3e0c",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1058,
    "path": "complete_study/legacy/036/CASE_SCHEMA.json",
    "runtime_mode": "0o644",
    "sha256": "bfaca28e448bcecc4a521efd5eb597724d19ce41995358159546f2c54da7130e",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1854,
    "path": "complete_study/legacy/037/PREDICTION_SCHEMA.json",
    "runtime_mode": "0o644",
    "sha256": "a5abbb135e3ccf396fbac4c017f974dc9c27086969901924fa5cea8b822aca31",
    "transport_mode": "0o644"
  },
  {
    "bytes": 4022,
    "path": "complete_study/model_provider_entry.py",
    "runtime_mode": "0o644",
    "sha256": "6e16253e83a1981eb63fac72f9d170c3587a3ec19095892c5662b0591c85b67f",
    "transport_mode": "0o644"
  },
  {
    "bytes": 135,
    "path": "complete_study/n055/__init__.py",
    "runtime_mode": "0o644",
    "sha256": "44ecb3ff12c2e72ea315fade04fd2062de0bdad868b3ff259cb862904d04fe30",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1680,
    "path": "complete_study/n055/assignment.py",
    "runtime_mode": "0o644",
    "sha256": "7298f00e81c3ac13db9ac00e4e01ff14e0782d6ba4c8e5a20e9d35d903657861",
    "transport_mode": "0o644"
  },
  {
    "bytes": 2634,
    "path": "complete_study/n055/authority.py",
    "runtime_mode": "0o644",
    "sha256": "adfed10ceeaaf2b02c75f943c25d73cc47ec7392b6786ee914e545f121089bc9",
    "transport_mode": "0o644"
  },
  {
    "bytes": 12096,
    "path": "complete_study/n055/banks.py",
    "runtime_mode": "0o644",
    "sha256": "f46590ddd8f71ac163ad9cdef358560e0653cb6a03a27f50286b832ec3a9c0ea",
    "transport_mode": "0o644"
  },
  {
    "bytes": 19392,
    "path": "complete_study/n055/broker.py",
    "runtime_mode": "0o644",
    "sha256": "9d0ec39e1e8cc86bd21fdfb606561d2c69a7ae3558dd19987351333ad93eeec9",
    "transport_mode": "0o644"
  },
  {
    "bytes": 15845,
    "path": "complete_study/n055/budget.py",
    "runtime_mode": "0o644",
    "sha256": "ba04fa0dd81cbc79e811b68522350bfa8908b530e8dd6019b8503b5026b28b16",
    "transport_mode": "0o644"
  },
  {
    "bytes": 15014,
    "path": "complete_study/n055/campaign.py",
    "runtime_mode": "0o644",
    "sha256": "7abcb46d1ad886373450724e2c1f83ad2ff614c86635a5c0bccc369fb87b8f8c",
    "transport_mode": "0o644"
  },
  {
    "bytes": 7273,
    "path": "complete_study/n055/central.py",
    "runtime_mode": "0o644",
    "sha256": "a6ad7effee770681a8c710b6554bb1530bb12b67a77a03dc654c023f4e0d9845",
    "transport_mode": "0o644"
  },
  {
    "bytes": 7404,
    "path": "complete_study/n055/cgroup.py",
    "runtime_mode": "0o644",
    "sha256": "75c14a2afcb73fd5052c22a89d7df175e72950faa32f0197ce47bfa4c0f6e539",
    "transport_mode": "0o644"
  },
  {
    "bytes": 9861,
    "path": "complete_study/n055/collector.py",
    "runtime_mode": "0o644",
    "sha256": "95d553e96c1cec3820cf873abe02a0bd6c70410693491fd4f1c00509aaec6ffd",
    "transport_mode": "0o644"
  },
  {
    "bytes": 9590,
    "path": "complete_study/n055/common.py",
    "runtime_mode": "0o644",
    "sha256": "8593b6ae72247e72f7dc98015168cd43fd635defc6a004129b078a2cff5ddda9",
    "transport_mode": "0o644"
  },
  {
    "bytes": 19589,
    "path": "complete_study/n055/features.py",
    "runtime_mode": "0o644",
    "sha256": "5e828b2aaa283e98a5dc28f59e89298d0ad4476c25ccccbb2de8b77e15cf2bd6",
    "transport_mode": "0o644"
  },
  {
    "bytes": 4476,
    "path": "complete_study/n055/inputs.py",
    "runtime_mode": "0o644",
    "sha256": "ad3b4f78574ecc4991d15841e7569b81c6031fc8dc9ce70dad01477d048b1183",
    "transport_mode": "0o644"
  },
  {
    "bytes": 26819,
    "path": "complete_study/n055/interpretation.py",
    "runtime_mode": "0o644",
    "sha256": "1648bbb6f312056c7de99aca3acbf84f86e3d373e8daa04bd5b68f6ba1c5865a",
    "transport_mode": "0o644"
  },
  {
    "bytes": 6448,
    "path": "complete_study/n055/journal.py",
    "runtime_mode": "0o644",
    "sha256": "9846cba35f63a69823e57c6cb00b34f65d8f08a33fc04267bfad3169115b3738",
    "transport_mode": "0o644"
  },
  {
    "bytes": 18104,
    "path": "complete_study/n055/learning.py",
    "runtime_mode": "0o644",
    "sha256": "01737a462f4625f8845bf747af349242d5cb141d95b46901e7fa4b7b315594fc",
    "transport_mode": "0o644"
  },
  {
    "bytes": 35669,
    "path": "complete_study/n055/native.py",
    "runtime_mode": "0o644",
    "sha256": "2c8a86128b41d69a0e137876d63ddff90ffe0e0be86a6e47f31c2ec9952517ef",
    "transport_mode": "0o644"
  },
  {
    "bytes": 6932,
    "path": "complete_study/n055/native_providers.py",
    "runtime_mode": "0o644",
    "sha256": "1c2560962a3fa15df2f1361f14778444af8ad3cc1a3cb58b3b04a7d4fb51cda0",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5541,
    "path": "complete_study/n055/original_r1.py",
    "runtime_mode": "0o444",
    "sha256": "6955d03232b545a4df0694669cb41338aa77bb24e23e9a8f7b838dd4085c09dd",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1999,
    "path": "complete_study/n055/participant_contract.py",
    "runtime_mode": "0o644",
    "sha256": "e61ebb304a51f672db86f1319e9d9cc596d1eaa85b7668bfe6fc9b19a4a30a7e",
    "transport_mode": "0o644"
  },
  {
    "bytes": 3537,
    "path": "complete_study/n055/plan.py",
    "runtime_mode": "0o644",
    "sha256": "fe268444290415f47f0c221475ac5ccc15e2cec7fb1d0b7b5ce451acf637d93f",
    "transport_mode": "0o644"
  },
  {
    "bytes": 8802,
    "path": "complete_study/n055/process.py",
    "runtime_mode": "0o644",
    "sha256": "81bffa2976142b95744438f5fd4c9469fbd86ebdb6631bdc174833165b3ae158",
    "transport_mode": "0o644"
  },
  {
    "bytes": 4946,
    "path": "complete_study/n055/programmes.py",
    "runtime_mode": "0o644",
    "sha256": "2fcc3d57d7f02605c1c5ec039e40919516ae8c897b6a5f41fd5afdf359cb457f",
    "transport_mode": "0o644"
  },
  {
    "bytes": 14075,
    "path": "complete_study/n055/protected.py",
    "runtime_mode": "0o644",
    "sha256": "a7acb71c8290dd95c2f0726f1b03694b4825d5db4719a52a461c9b4022800cfc",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5029,
    "path": "complete_study/n055/registry.py",
    "runtime_mode": "0o644",
    "sha256": "eeafc6239e3bdbaa9639f9fba99b0f51601aae2f9d0dce2a0cae89e725f5a3c2",
    "transport_mode": "0o644"
  },
  {
    "bytes": 12899,
    "path": "complete_study/n055/reporting.py",
    "runtime_mode": "0o644",
    "sha256": "d47c12b6af7f13d416c98cfed88a42274cc09aeb490a808dbc9a5163407ec2af",
    "transport_mode": "0o644"
  },
  {
    "bytes": 4915,
    "path": "complete_study/n055/resource_policy.py",
    "runtime_mode": "0o644",
    "sha256": "ede9ca66e530efcedfd581b32c9855d82c1f9316146f0aa134e51b5d61183151",
    "transport_mode": "0o644"
  },
  {
    "bytes": 3154,
    "path": "complete_study/n055/review_service.py",
    "runtime_mode": "0o644",
    "sha256": "197bf95d1368a4c8698907ba4c62fb4f6d0635c2be1be5baa8114d1a6117be5e",
    "transport_mode": "0o644"
  },
  {
    "bytes": 2356,
    "path": "complete_study/n055/schedule.py",
    "runtime_mode": "0o644",
    "sha256": "f44f3bd75667426bd19fee8a8576821c2684f63fbfd3ba5cc47c7388ec8d0ce0",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5528,
    "path": "complete_study/n055/seals.py",
    "runtime_mode": "0o644",
    "sha256": "1d9b76c2d117418372f31dfb48a89d57e47355dfd10bc4b6fca0e0d38fabb670",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5185,
    "path": "complete_study/n055/source.py",
    "runtime_mode": "0o644",
    "sha256": "e7c7d1fa0d286b6b9381da0b0f43f13bd4458bf5aec4b16d636e27dd9aaa063b",
    "transport_mode": "0o644"
  },
  {
    "bytes": 3219,
    "path": "complete_study/n055/streaming.py",
    "runtime_mode": "0o644",
    "sha256": "b2bae4d9d78833480617ceb97db9c51c38fae2d9de97ba594e7fa1fd1820f12e",
    "transport_mode": "0o644"
  },
  {
    "bytes": 9616,
    "path": "complete_study/n055/views.py",
    "runtime_mode": "0o644",
    "sha256": "2a933cff348129613db4ecb19c1ddb32b7490e58cbab633d3cbdcdadbe57c1bb",
    "transport_mode": "0o644"
  },
  {
    "bytes": 7121,
    "path": "complete_study/operator_entry.py",
    "runtime_mode": "0o644",
    "sha256": "bfb60478a13fbcb20099bbd6f5c24a9c359c05ff22bb8266ff14dee3a54eebcb",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1985,
    "path": "complete_study/phase_entry.py",
    "runtime_mode": "0o644",
    "sha256": "61e35be995a8f5e061ebf74b9903f6891059d4f1573aafad470ef3e224744799",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1471,
    "path": "complete_study/public/BROKER_REQUEST_SCHEMA.json",
    "runtime_mode": "0o644",
    "sha256": "602890f9179fa8d08b7b7ac825de04cf9c2f9adfcb244ab6c0e57612439ef91e",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1256,
    "path": "complete_study/public/BROKER_RESPONSE_SCHEMA.json",
    "runtime_mode": "0o644",
    "sha256": "ecaf8329cece6fd419c076bd7936f5932f1d5527dfb7cf0b28e5c84310fbe2dc",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1058,
    "path": "complete_study/public/CASE_SCHEMA.json",
    "runtime_mode": "0o644",
    "sha256": "bfaca28e448bcecc4a521efd5eb597724d19ce41995358159546f2c54da7130e",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1184,
    "path": "complete_study/public/CELL_SCHEMA.json",
    "runtime_mode": "0o644",
    "sha256": "fd4e5c84c7d02282317d2169a5214c5e6ebc1c521cbf1de4d6ee54ee974682f9",
    "transport_mode": "0o644"
  },
  {
    "bytes": 669,
    "path": "complete_study/public/OPERATIONS_SCHEMA.json",
    "runtime_mode": "0o644",
    "sha256": "174b0fda011134bf7633583f51194fdd3882ea84330581a689966741759bbc2b",
    "transport_mode": "0o644"
  },
  {
    "bytes": 2415,
    "path": "complete_study/public/POLICY.json",
    "runtime_mode": "0o644",
    "sha256": "e07436584593fe62e830e76ad8d75e14e2877edc90b711933f05c09beaa7c7c6",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1854,
    "path": "complete_study/public/PREDICTION_SCHEMA.json",
    "runtime_mode": "0o644",
    "sha256": "a5abbb135e3ccf396fbac4c017f974dc9c27086969901924fa5cea8b822aca31",
    "transport_mode": "0o644"
  },
  {
    "bytes": 3169,
    "path": "complete_study/public/PREEXPOSURE_POLICY_SCHEMA.json",
    "runtime_mode": "0o644",
    "sha256": "04f494a0569b91fe25fc54dca8e46df70b8531a008d4662bdefc2663f2251701",
    "transport_mode": "0o644"
  },
  {
    "bytes": 14810,
    "path": "complete_study/public/PROGRAM_ABI_V3.md",
    "runtime_mode": "0o644",
    "sha256": "bd577b3095d9c55707edeb6b12e0dd3796e5753fd74e92da84d7c93574d5af9d",
    "transport_mode": "0o644"
  },
  {
    "bytes": 5124,
    "path": "complete_study/public/RESOURCE_POLICY_V1.json",
    "runtime_mode": "0o644",
    "sha256": "d87a869636bad14078418685a6e5a2d498c5349c5a0c82f672f7e423cb8b516d",
    "transport_mode": "0o644"
  },
  {
    "bytes": 2137,
    "path": "complete_study/public/SELECTED_METHOD_SCHEMA.json",
    "runtime_mode": "0o644",
    "sha256": "5f62cce4c6b22c69797fa5193c98572025ffc9fe0863aa81960d60573618d907",
    "transport_mode": "0o644"
  },
  {
    "bytes": 6764,
    "path": "complete_study/public/TASK.md",
    "runtime_mode": "0o644",
    "sha256": "e5311daa10d45d63e61c04aab9b06e194ae1abb1ac0af700f1a9287368e683b5",
    "transport_mode": "0o644"
  },
  {
    "bytes": 3914,
    "path": "complete_study/public/interface.py",
    "runtime_mode": "0o644",
    "sha256": "ccabe30238b084b19422c920877332232d730caca712f3679b73e6c28fcb3e0c",
    "transport_mode": "0o644"
  },
  {
    "bytes": 8283,
    "path": "complete_study/reference_entry.py",
    "runtime_mode": "0o644",
    "sha256": "1a0d4bda95ae5dd73e4fba2564532d5c45364ade8e0bf30c4690982c64b25dac",
    "transport_mode": "0o644"
  },
  {
    "bytes": 4285,
    "path": "complete_study/tool_provider_entry.py",
    "runtime_mode": "0o644",
    "sha256": "f104b3555dcedcdfba523fa61a330a09f69bdc5e8e82785ae7f939d96b9776fc",
    "transport_mode": "0o644"
  },
  {
    "bytes": 10818,
    "path": "operator_completion/README.md",
    "runtime_mode": "0o644",
    "sha256": "0b5bcdb81f5d0045c4752e17d60de84fcb56d5d92ff96ec0b1056f2e18a1d0ad",
    "transport_mode": "0o644"
  },
  {
    "bytes": 3823,
    "path": "operator_completion/operator_entry.py",
    "runtime_mode": "0o644",
    "sha256": "366bbf79fe8a835f2140985602909fdb6fbe4a358721fdb0aa5800eaa0f1a96c",
    "transport_mode": "0o644"
  },
  {
    "bytes": 14933,
    "path": "operator_completion/plans.py",
    "runtime_mode": "0o644",
    "sha256": "5c2d5d9fcd7a53fde99c2bafe373aea4027fbb2994c95966829acaf11fa75c38",
    "transport_mode": "0o644"
  },
  {
    "bytes": 1565,
    "path": "operator_completion/plans_v2.py",
    "runtime_mode": "0o644",
    "sha256": "20df255d312edf415a425a1215cb8b855681738230b68f9dffa20bfea374bba9",
    "transport_mode": "0o644"
  },
  {
    "bytes": 19742,
    "path": "operator_completion/preparation.py",
    "runtime_mode": "0o644",
    "sha256": "8d23de0cc50f4e935f5f3bef91dcc3084cdbc8d26359775ac39868f5603da353",
    "transport_mode": "0o644"
  },
  {
    "bytes": 6481,
    "path": "operator_completion/source_closure.py",
    "runtime_mode": "0o644",
    "sha256": "65990d78d7e6758981fa1223aceb22a9f5ffad4e972af4dddf0ffc553b7512db",
    "transport_mode": "0o644"
  }
]

MEMBER_CAP = 1048576
SOURCE_CAP = 1048576
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
    need(type(rows) is list and len(rows) == 88, "frozen 88-body transport required")
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
        need((len(p.parts) > 1 and p.parts[0] in ("complete_study", "operator_completion"))
             or name == "SOURCE_COMPONENTS.json", "fixed source namespaces")
        need(type(row["bytes"]) is int and 0 < row["bytes"] <= MEMBER_CAP,
             "bounded member extent")
        h = row["sha256"]
        need(type(h) is str and len(h) == 64 and all(c in "0123456789abcdef" for c in h),
             "exact member digest")
        need(row["transport_mode"] == "0o644"
             and row["runtime_mode"] in ("0o644", "0o444"), "selected source permissions")
        names.add(name)
        total += row["bytes"]
    need(total <= SOURCE_CAP and list(names).count("SOURCE_COMPONENTS.json") == 1,
         "bounded fixed source transport")
    need(sum(n.startswith("complete_study/") for n in names) == 81
         and sum(n.startswith("operator_completion/") for n in names) == 6,
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
    """Close only the selected two trees and sidecar, not unrelated task siblings."""
    expected = {r["path"] for r in rows}
    expected_dirs = set()
    for name in expected:
        if "/" in name:
            expected_dirs.update(str(p) for p in PurePosixPath(name).parents if str(p) != ".")
    actual = {"SOURCE_COMPONENTS.json"}
    directories = {}
    stack = [root / "complete_study", root / "operator_completion"]
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
            absolute(str(self.destination / name)).mkdir(mode=0o755)
        for row in self.rows:
            path = self.destination / row["path"]
            self.write_body(path, row, bodies[row["path"]])
            self.copied.append(row["path"])
        del bodies
        self.stage = "owned_readback"
        directories = namespace(self.destination, self.rows, self.ledger)
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
             str(self.destination / "complete_study/operator_entry.py"), "--inspect"],
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
        return {"schema": "neural055_owned_public_source_v1", "status": "source_only",
                "materialized_root": str(self.destination), "source_files": 88,
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
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()
    worker.ledger.tick()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

