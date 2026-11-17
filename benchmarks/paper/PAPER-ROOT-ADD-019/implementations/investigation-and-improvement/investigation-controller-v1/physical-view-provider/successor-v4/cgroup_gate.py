"""Source-pinned gate: the supervisor attaches this PID before opening stdin."""
import os
import sys

def main():
    if len(sys.argv)<2 or os.read(0,1)!=b'G':raise SystemExit(125)
    null=os.open('/dev/null',os.O_RDONLY);os.dup2(null,0);os.close(null)
    os.execv(sys.argv[1],sys.argv[1:])

if __name__=='__main__':main()
