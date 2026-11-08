"""Accepted full cerebellar program identities; no execution at import."""
import hashlib
import json
import math
import re
TASK = 'PAPER-FIND-REP-014'
ROLES = ('A', 'B', 'reference')
PROFILES = ('C', 'M', 'CM', 'CM-shuffled')
MODALITIES = ('GrC', 'CF')
BRANCHES = {
  "MainData": {
    "inputs": [
      "mainData1.mat",
      "mainData2.mat"
    ],
    "targets": [
      "allGrCs_rew",
      "allGrCs_omit",
      "allCFs_rew",
      "allCFs_omit",
      "GrCsChronInfo",
      "CFsChronInfo",
      "ant_sig",
      "anti_sig",
      "post",
      "mvCFs",
      "corr_2s_1s",
      "corr_2s_1s_rand",
      "chronCellNums"
    ]
  },
  "learningCurves_DA": {
    "inputs": [
      "mainLearn.mat"
    ],
    "targets": [
      "allattmpts",
      "allsucc",
      "allcomplt",
      "normtraining"
    ]
  },
  "CF_novice": {
    "inputs": [
      "CF_novice.mat"
    ],
    "targets": [
      "allNovCFs_rew",
      "postmag",
      "postcfs",
      "tplt_tmplt_s"
    ]
  },
  "IOChRmine": {
    "inputs": [
      "IOChRmine.mat"
    ],
    "targets": [
      "attmptRate",
      "succRate",
      "compltd",
      "mvlen",
      "cumultrials"
    ]
  },
  "learningCurves_IOChRmine": {
    "inputs": [
      "IOChRmine_learn.mat"
    ],
    "targets": [
      "allattmpts",
      "allsucc",
      "allcomplt",
      "normtraining",
      "isIO",
      "isCtrl"
    ]
  },
  "IOChRmine_imaging": {
    "inputs": [
      "IOChRmine_imaging.mat"
    ],
    "targets": [
      "allgrcsIO",
      "allgrcsIO_a",
      "allpvals",
      "prerewIO",
      "prerewmbaseIO",
      "prerewmrewdecIO",
      "antIO",
      "winplt_s"
    ]
  },
  "passiveMFB": {
    "inputs": [
      "passiveMFB.mat"
    ],
    "targets": [
      "allcells",
      "antp",
      "sessnums",
      "preavg",
      "baseavg",
      "postavg",
      "ant",
      "antbysess",
      "ncsbysess",
      "antbysesspct"
    ]
  },
  "gtacr1": {
    "inputs": [
      "gtacr1.mat"
    ],
    "targets": [
      "mvlens_opto",
      "attmptRates_opto",
      "succRates_opto",
      "compltd_opto",
      "cumultrials_opto",
      "laser_rew_opto",
      "pos_start_opto",
      "succRates_MFB",
      "attmptRates_MFB",
      "mvlens_MFB",
      "compltd_MFB"
    ]
  },
  "learningCurves_gtacr1": {
    "inputs": [
      "gtacr1_learn.mat"
    ],
    "targets": [
      "allattmpts",
      "allsucc",
      "allcomplt",
      "normtraining",
      "isNorm",
      "isGt"
    ]
  }
}
INPUTS = [
  {
    "name": "mainData1.mat",
    "bytes": 2408952933,
    "md5": "f2d3b27ebbbd99a58c6ff62e8b473a58"
  },
  {
    "name": "gtacr1.mat",
    "bytes": 800373479,
    "md5": "b96d812d30e99288e5081ccbef356a14"
  },
  {
    "name": "mainLearn.mat",
    "bytes": 790060784,
    "md5": "11780e33a744ba688ac494e9f6da5798"
  },
  {
    "name": "mainData2.mat",
    "bytes": 3002001774,
    "md5": "1f163dee80ad4baf1574e581954f0213"
  },
  {
    "name": "IOChRmine_imaging.mat",
    "bytes": 271362373,
    "md5": "03c591edbd10ef7001d9041949a90258"
  },
  {
    "name": "IOChRmine.mat",
    "bytes": 126154245,
    "md5": "26cccd5dd5d83d4abf7d52faa1c477ca"
  },
  {
    "name": "CF_novice.mat",
    "bytes": 102790189,
    "md5": "dff1bd34f3df624559dfd79eae91af43"
  },
  {
    "name": "IOChRmine_learn.mat",
    "bytes": 334685598,
    "md5": "fe00c7e0f328a926c3b262e1b389fc3c"
  },
  {
    "name": "gtacr1_learn.mat",
    "bytes": 1573941784,
    "md5": "d9706581331b7874c0b475c1c4a164b3"
  },
  {
    "name": "passiveMFB.mat",
    "bytes": 138795791,
    "md5": "88718bba0a28bfe45cfafabc0db3aec0"
  }
]

def need(condition, message):
    if not condition: raise ValueError(message)

def encoded(value):
    return (json.dumps(value,sort_keys=True,separators=(',', ':'),allow_nan=False)+'\n').encode('utf-8')

def identity(value): return hashlib.sha256(encoded(value)).hexdigest()

def finite(value): return type(value) in (float,int) and math.isfinite(value)

def descriptor(value, allow_empty=False):
    need(type(value) is dict and set(value)=={'bytes','sha256'}, 'Exact descriptor')
    need(type(value['bytes']) is int and value['bytes'] >= (0 if allow_empty else 1), 'Bounded extent')
    need(type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}',value['sha256']), 'SHA256')
    return value

def token(value):
    need(type(value) is str and re.fullmatch('[A-Za-z0-9_-]{1,96}',value), 'Opaque bounded identifier')
    return value

def high_level_jobs():
    encoding=[{'kind':'encoding','role':r,'fold':f,'profile':p} for f in range(5) for p in PROFILES for r in ROLES]
    native=[{'kind':'reconstruction','role':r,'branch':b} for b in BRANCHES for r in ROLES]
    return [{**j,'job_id':identity(j)} for j in encoding+native]
