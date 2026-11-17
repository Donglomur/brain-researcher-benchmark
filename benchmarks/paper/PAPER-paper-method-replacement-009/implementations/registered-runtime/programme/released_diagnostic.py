"""Literal release scripts are post-capture diagnostics, never blind references."""
from pathlib import Path
import os,runpy,sys
from .native.io import load,need,read,write_new

def run(inputs,output):
 recipe=load(inputs/'release.json');need(recipe['phase']=='postcapture_literal_release','explicit historical diagnostic')
 root=Path('/scratch/literal');root.mkdir();source=Path('/source/source_contexts/public/B/author-code')
 for row in recipe['source_files']:
  relative=row['path'];raw=read(source/relative,row['bytes'],row);write_new(root/relative,raw,len(raw))
 # Original cached data are independently selected and read-only in the image.
 (root/'cached_ibl_data').symlink_to(inputs/'original_cache',target_is_directory=True)
 sys.path.insert(0,str(root/'src'));old=os.getcwd();os.chdir(root)
 try:
  for call in recipe['calls']:
   need(call['script']in('1_decode_single_session.py','2_decode_multi_session.py','3_decode_multi_region.py'),'literal released script family')
   sys.argv=[str(root/'src'/call['script']),*call['argv']];runpy.run_path(sys.argv[0],run_name='__main__')
 finally:os.chdir(old)
 # Full original outputs are copied under ordinary native quota observation.
 import shutil
 for name in recipe['output_directories']:shutil.copytree(root/name,output/name)
 return {'phase':'postcapture_literal_release','blind_reference':False,'equivalence':'unqualified'}
