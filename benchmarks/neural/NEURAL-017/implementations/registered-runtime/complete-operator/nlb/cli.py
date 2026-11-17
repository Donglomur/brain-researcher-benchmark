"""Operator-only finite JSON-lines driver and inert source-status route."""
import argparse,json,sys,time,select,os,stat
from pathlib import Path
from .contracts import need,parse,canonical,digest,closed,Budget,Custody,Store,Authority,ReadOwner,stable

def load_design(store,pins):
 out={k:store.json(v,16*2**20)for k,v in pins.items()};need(set(out)=={'roster','contrasts','dag','lineage','gates'},'whole accepted design inputs');out['dag_stages']={x['id']:x for x in out['dag']['stages']};return out

class OperatorLines:
 def __init__(self,fd):self.fd=fd;self.pending=bytearray();self.eof=False;self.owner=None;self.regular_checked=False;self.regular=None
 def remaining(self):
  if not self.regular_checked:
   original=os.fstat(self.fd)
   if stat.S_ISREG(original.st_mode):
    position=os.lseek(self.fd,0,os.SEEK_CUR);need(0<=position<=original.st_size,'original operator file position');self.regular=(stable(original),position,original.st_size)
   self.regular_checked=True
  if self.regular is None:return None
  original,start,end=self.regular;need(stable(os.fstat(self.fd))==original,'operator file changed')
  position=os.lseek(self.fd,0,os.SEEK_CUR);need(position==start+self.owner.known_returned,'operator file cursor changed');return end-position
 def read(self,budget):
  if self.owner is None:
   custody=budget.custody if type(budget.custody)is Custody else Custody('operator_lines');self.owner=ReadOwner(budget,custody,'operator_lines')
  need(self.owner.budget is budget,'same original operator read budget')
  try:
   while b'\n'not in self.pending and not self.eof:
    budget.admit();remaining=self.remaining()
    if remaining==0:self.eof=True;break
    need(len(self.pending)<=2**20,'operator message cap')
    # Regular files terminate at their stable admitted extent without a probe.
    # An unknown-length stream may spend ONE admitted byte to distinguish EOF
    # from an oversized frame; that byte is retained and charged, never free.
    maximum=min(65536,2**20+1-len(self.pending))
    if remaining is not None:
     maximum=min(maximum,remaining,2**20-len(self.pending));need(maximum>0,'operator message cap')
    if not select.select([self.fd],[],[],min(1,max(0,budget.deadline-time.monotonic())))[0]:continue
    raw=self.owner.read(self.fd,maximum,self.pending)
    if not raw:self.eof=True
    self.remaining();need(len(self.pending)<=2**20,'operator message cap')
   if b'\n'in self.pending:i=self.pending.index(10)+1;out=bytes(self.pending[:i]);del self.pending[:i];return out
   out=bytes(self.pending);self.pending.clear();return out
  except BaseException as error:
   self.owner.quarantine(error,'operator_lines');self.owner.custody.raise_if_failed()

def main(argv=None):
 parser=argparse.ArgumentParser(description='NLB017 complete source; authentic execution requires separately selected current operator authority.')
 parser.add_argument('route',choices=('describe','operator'));parser.add_argument('--root');parser.add_argument('--selection');parser.add_argument('--selection-sha256');args=parser.parse_args(argv)
 if args.route=='describe':
  print(json.dumps({'canonical_id':'NEURAL-017','status':'source_unqualified','groups':100,'F_programmes':50,'I_cases':28700,'references':[f'R{i}'for i in range(9)],'contrasts':65,'stages':16,'open_scientific_gates':24,'authentic_execution_performed':False,'default_deployment_enabled':False,'routes':['operator','source-describe'],'legacy_L20':'unchanged separate installed route, never relabelled P4H'}));return 0
 need(args.root and args.selection and args.selection_sha256,'explicit operator selection identity')
 c=Custody('operator_driver');campaign=None
 try:
  # The selected ordinary metadata file is bounded before decoding; it cannot
  # authorize itself by being named on a model/tool request. This CLI is not
  # exposed inside participant namespaces or through the broker surface.
  root=Path(args.root);boot=Budget(dict(cpu_seconds=10,read_bytes=16*2**20,write_bytes=0,stream_bytes=0,model_tokens=0,created_files=0,tool_calls=0),time.monotonic()+10,custody=c);bootstrap=Store(root,boot,c);pin,raw=bootstrap.capture(args.selection,16*2**20);c.original_bootstrap_budget=boot;need(pin['sha256']==args.selection_sha256,'current selected source identity');s=parse(raw)
  closed(s,{'schema','source_sha256','authority','budget','original_deadline','programme','design','campaign'})
  need(s['schema']=='NLB017_operator_selection_v1','operator selection');c.facts['bootstrap_budget']=boot.snapshot();budget=Budget(s['budget'],s['original_deadline'],custody=c)
  # Preserve both original ledgers. Used bytes are charged exactly once;
  # carrying their reservations is not another charge or a new allowance.
  for k,v in boot.used.items():budget.charge(k,v)
  for k,v in boot.reserved.items():budget.reserve(k,v)
  store=Store(root,budget,c);authority=Authority.from_selected(store,s['authority'],s['source_sha256'])
  from .controller import Campaign
  campaign=Campaign(authority,s['source_sha256'],store.json(s['programme']),load_design(store,s['design']),store.json(s['campaign'],1024*2**20),store);campaign.initialize_preconditions()
  # One original process holds custody across exact independent operator
  # reviews. No restart/replay or renewed per-stage deadline is implemented.
  lines=OperatorLines(sys.stdin.fileno())
  while True:
   budget.guard();raw=lines.read(budget);need(len(raw)<=2**20,'operator message cap')
   if not raw:break
   message=parse(raw);op=message.get('operation')
   if op=='advance':closed(message,{'operation','stage'});result=campaign.advance(message['stage'])
   elif op=='resume_development':closed(message,{'operation'});result=campaign.resume_development()
   elif op=='admit_independent_review':
    closed(message,{'operation','authority','checkpoint','review'});new=Authority.from_selected(store,message['authority'],s['source_sha256']);campaign.admit_operator_evidence(new,message['checkpoint'],message['review']);result={'accepted_exact_review':message['review'],'budget_not_renewed':True}
   elif op=='admit_report_judgment':
    closed(message,{'operation','authority','reviews','adjudication'});new=Authority.from_selected(store,message['authority'],s['source_sha256']);result=campaign.admit_report_judgment(new,message['reviews'],message['adjudication'])
   elif op=='claims':closed(message,{'operation'});result=campaign.claims()
   else:raise ValueError('closed operator operation')
   sys.stdout.buffer.write(canonical({'operation':op,'result':result}));sys.stdout.buffer.flush()
  need('S16'in campaign.evidence.done,'operator EOF before complete study');return 0
 except BaseException as e:
  c.fail(e,'operator_driver');c.original_campaign=campaign
  try:sys.stderr.buffer.write(canonical({'status':'incomplete','original':c.snapshot(),'campaign':None if campaign is None else campaign.incomplete()}));sys.stderr.buffer.flush()
  except BaseException as secondary:c.fail(secondary,'operator_failure_publication')
  raise c.first_error
if __name__=='__main__':raise SystemExit(main())
