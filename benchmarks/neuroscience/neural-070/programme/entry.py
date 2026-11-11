"""Immutable capsule launcher; isolated Python has no host package search path."""
import sys
sys.path.insert(0,"/source")
from n070.worker_entry import main
main()

