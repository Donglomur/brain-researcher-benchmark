"""Execute exactly one globally frozen program in its own fresh container."""
import sys
import os
sys.path.insert(0,'/trusted')
from entry_common import guard,need
r,v=guard();need(v['mode'] in ('spectral','spatial','corrected'),'candidate-only context')
os.execv(sys.executable,[sys.executable,'-I','-B','/program/program.py','--input','/input/VIEW.json','--output','/output/submission.json'])
