"""Single-program entrypoint; no scheduler, native controller or resource admission."""
import runpy,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ACTIONS={'acquire','prepare','reference','score'}
if len(sys.argv)<2 or sys.argv[1] not in ACTIONS:raise SystemExit('Usage: run.py {acquire|prepare|reference|score} [arguments]')
action=sys.argv.pop(1)
if HERE.name=='private':sys.path.insert(0,str(HERE.parent/'public'))
sys.path.insert(0,str(HERE));runpy.run_path(str(HERE/(action+'.py')),run_name='__main__')
