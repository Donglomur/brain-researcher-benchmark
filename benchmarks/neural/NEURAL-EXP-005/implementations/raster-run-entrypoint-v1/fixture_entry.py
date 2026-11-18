"""Generated participant adapter: consume public instructions then reuse PNG probe."""
from pathlib import Path
import sys

fixture, prompt = Path(sys.argv[1]), Path(sys.argv[2])
text = prompt.read_text()
assert "[29,30)" in text and "three expert" in text
sys.argv = [str(fixture), "good", "1"]
exec(compile(fixture.read_bytes(), str(fixture), "exec"),
     {"__name__": "__main__", "__file__": str(fixture)})
