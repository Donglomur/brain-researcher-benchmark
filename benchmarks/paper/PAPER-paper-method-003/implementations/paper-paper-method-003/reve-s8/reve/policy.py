"""Production authority is a pinned controller input, never a participant flag."""
from .errors import require
from .deadline import Window
import time
from .objects import Reader,canonical,digest,fields

# These are independently accepted PRE-FLIGHT portions of the named gates,
# never a claim that the eventual full scientific gate is closed. Gates whose
# evidence is an output are not required before that output can be generated. In particular G15/G19/G21/G29 do not create
# a circular prerequisite to producing pretraining/reference/process evidence.
PRELAUNCH={'G01','G02','G03','G04','G05','G06','G07','G08','G09','G10','G11','G12','G14','G16','G17','G18','G20','G22','G23','G26','G27','G28','G30'}


class Authority:
    def __init__(self,root,selection_pin,plan_identity,source_identity,mode,driver_identity=None,window=None):
        if window is not None:window.check()
        reader=Reader(root,8*1024**2,256,guard=window.check if window is not None else None);self.reader=reader
        selection=reader.json(selection_pin)
        fields(selection,('schema','mode','plan','implementation','allowed_jobs','input_roots','source_roots','environment','domain_roster','gates','targets','limits','output_root','valid_after','expires_at'),('driver',))
        require(selection['schema']=='reve-root-execution-selection-v1' and selection['mode']==mode,'execution selection mode')
        require(selection['plan']==plan_identity and selection['implementation']==source_identity,'whole plan/source authority')
        self.window=window or Window(selection['valid_after'],selection['expires_at'])
        require(self.window.original==(selection['valid_after'],selection['expires_at']),'original authority window changed')
        self.check_current();reader.guard=self.check_current
        self.selection=selection;self.identity=selection_pin;self.mode=mode
        if mode=='production':
            require(driver_identity is not None and selection.get('driver')==driver_identity,'exact complete action recipe required')
            require(PRELAUNCH<=set(selection['gates']),'production qualification gaps remain')
            for gate in sorted(PRELAUNCH):
                evidence=reader.json(selection['gates'][gate])
                fields(evidence,('gate','scope','implementation','status','independent_review','evidence','requirements'))
                require(evidence['gate']==gate and evidence['scope']==plan_identity and evidence['implementation']==source_identity and evidence['status']=='accepted_preflight' and evidence['evidence'] and evidence['requirements'],'preflight scope not independently accepted')
                review=reader.json(evidence['independent_review'])
                fields(review,('schema','gate','scope','implementation','status','evidence','requirements','blocking_findings','reviewer'))
                require(review['schema']=='reve-independent-preflight-acceptance-v1' and review['status']=='ACCEPTED' and not review['blocking_findings'] and review['reviewer'],'independent preflight verdict')
                require(all(review[k]==evidence[k] for k in ('gate','scope','implementation','evidence','requirements')),'exact independent preflight evidence closure')
        else:require(mode=='inert-control' and not selection['targets'],'inert controls cannot mount targets')
        self.check_current()
        self.reader_cost={'bytes':reader.bytes,'files':reader.files,'consumed_bytes':reader.consumed_bytes,'partial_observations':reader.partial_observations}

    def check_current(self):self.window.check()

    def check_time(self,now):
        require(self.window.original[0]<=now<self.window.original[1],'selection time window')
        self.check_current()

    def job(self,job,custody_only=False):
        if not custody_only:self.check_current()
        require(job['id'] in self.selection['allowed_jobs'],'job not selected')
        expected=self.selection['allowed_jobs'][job['id']]
        require(expected==digest(canonical(job)),'job selection identity')

    def target_access(self,closed):
        self.check_current()
        require(self.mode=='production' and closed['receipt'] and closed['jobs'],'target access before global closure')
        return self.selection['targets']
