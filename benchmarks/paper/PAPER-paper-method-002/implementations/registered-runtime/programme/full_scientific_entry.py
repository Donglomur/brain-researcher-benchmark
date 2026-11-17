"""Fixed isolated child entry; its immutable /program tree is parent-authenticated."""
import sys
if __name__=='__main__':
    if __file__!='/program/full_scientific_entry.py':raise SystemExit('fixed installed entry required')
    if len(sys.argv)!=5:raise SystemExit('explicit invocation/output/extents required')
    sys.path.insert(0,'/program')
    from runtime.full_scientific_bridge import main
    main(sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4]))
