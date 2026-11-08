"""Concrete data-free authoring and equal-view analyst execution transport.

No provider, native process or dataset is accessed on import. Candidate Python
is executed only by the pinned offline container transport. Private grading
source is never part of an analyst source or data mount.
"""
import ast,hashlib,json,os,stat
from pathlib import Path
import common as c
import schedule
from native import Bridge,Native
from transport.provider import ChatCompletionTransport

def seed(replication,model,design_sha256):
    c.integer(replication,0,2)
    c.need(type(model)is str and model,'selected author model');c.digest(design_sha256)
    return int.from_bytes(hashlib.sha256(c.encoded({'task':c.TASK,'design':design_sha256,'model':model,'replication':replication,'purpose':'paired-analyst-author-v1'},False)).digest()[:4],'big')%(2**31)

def workspace_inventory(root,budget,max_files,max_bytes,max_entries=None):
    """Full ordinary-file inventory; a cap violation fails, never truncates."""
    root=c.absolute(str(root));c.integer(max_files,1);c.integer(max_bytes,1);out=[];total=0;entry_count=0
    max_entries=2*max_files+1 if max_entries is None else c.integer(max_entries,1)
    def visit(directory):
        nonlocal total,entry_count
        budget.check_clock();entries=[]
        with os.scandir(directory)as iterator:
            for entry in iterator:
                budget.check_clock();entry_count+=1;c.need(entry_count<=max_entries,'bounded complete workspace entries before accumulation');entries.append(entry)
        entries.sort(key=lambda e:e.name)
        for entry in entries:
            p=Path(entry.path);s=entry.stat(follow_symlinks=False)
            c.need(not entry.is_symlink(),'no workspace symlinks')
            if stat.S_ISDIR(s.st_mode):visit(p);c.sync_directory(p)
            else:
                c.need(stat.S_ISREG(s.st_mode)and s.st_nlink==1,'ordinary private workspace artifact')
                total+=s.st_size;c.need(len(out)<max_files and total<=max_bytes,'complete workspace exceeds selected storage cap')
                fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
                try:os.fsync(fd)
                finally:os.close(fd)
                budget.charge('read_bytes',s.st_size+1);h=hashlib.sha256();n=0
                with p.open('rb')as stream:
                    while n<=s.st_size:
                        budget.check_clock();b=stream.read(min(1048576,s.st_size+1-n))
                        if not b:break
                        n+=len(b);h.update(b)
                after=p.lstat();c.need(n==s.st_size and all(getattr(s,k)==getattr(after,k)for k in('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_nlink')),'stable complete workspace body')
                out.append({'relative_path':str(p.relative_to(root)),'source':{'path':str(p),'bytes':n,'sha256':h.hexdigest()}})
    visit(root);c.sync_directory(root);budget.check_clock();return out

def source_response(text,max_bytes):
    c.need(type(text)is str and len(text.encode())<=max_bytes,'bounded full final provider source')
    body=c.parse(text);c.exact(body,('python_source',));source=body['python_source']
    c.need(type(source)is str and source.strip(),'nonempty final Python source')
    raw=source.encode();c.need(len(raw)<=max_bytes,'complete candidate source cap');ast.parse(source)
    # Parsing establishes syntactic completeness only. The qualified namespace
    # and exact observed mounts provide access separation, not an AST blacklist.
    return raw

class AnalystStudy:
    def __init__(self,config,whole,output_root,public_sources):
        c.exact(config,('provider','native','native_phase_limits','author_limits','execution_limits','author_turns','max_source_bytes','max_workspace_files','max_workspace_bytes','max_submission_bytes','tool_return_bytes','provider_seed_supported','design_sha256','protocol','protocol_sources'))
        for k in('author_turns','max_source_bytes','max_workspace_files','max_workspace_bytes','max_submission_bytes','tool_return_bytes'):c.integer(config[k],1)
        c.need(type(config['provider_seed_supported'])is bool,'explicit provider seed capability')
        self.config=config;self.whole=whole;self.root=c.absolute(str(output_root));self.public_sources=public_sources;self.contexts=[]
        c.need(type(public_sources)is list and public_sources,'only selected public event/io source')
        c.need(all(Path(d['path']).name in('event_protocol.py','io_contract.py')for d in public_sources),'protected reconstruction source cannot enter analyst mounts')

    def protocol(self,budget):
        descriptors=[self.config['protocol'],*self.config['protocol_sources']]
        rows=[]
        for d in descriptors:
            raw=c.capture(d,budget,[Path(d['path']).parent]);rows.append({'source':d,'text':raw.decode('utf-8')})
        return rows

    def invoke_author(self,identity,replication,root,inputs,prompt,budget):
        scripts=c.new_directory(root/'scripts',budget);native_root=c.new_directory(root/'native',budget)
        cfg=dict(self.config['provider']);cfg['seed']=seed(replication,cfg['model'],self.config['design_sha256'])if self.config['provider_seed_supported']else None
        provider=ChatCompletionTransport(cfg,Bridge(budget),root/'provider')
        native=Native(self.config['native'],self.config['native_phase_limits'],budget,native_root,self.public_sources)
        messages=[{'role':'system','content':'You must implement the specified complete numerical reconstruction. Use only the supplied data and tools. Finish with exactly JSON {"python_source":"..."}; no Markdown. The final program is run once as python -I -B PROGRAM --request ABS --output ABS. It must read the exact context request and write one complete JSON submission to --output. Partial support is refused.'},{'role':'user','content':json.dumps(prompt,sort_keys=True,allow_nan=False)}]
        workspace=[];attempts=[];result=None
        for turn in range(self.config['author_turns']):
            budget.check_clock();message,finish=provider.complete(messages,allow_tools=True);messages.append(message)
            if finish=='stop':
                result=source_response(message['content'],self.config['max_source_bytes']);break
            call=message['tool_calls'][0];arguments=c.parse(call['function']['arguments']);c.exact(arguments,('code',));raw=arguments['code'].encode()
            c.need(len(raw)<=self.config['max_source_bytes'],'bounded complete tool code');ast.parse(raw)
            script=c.publish(scripts/('%04d.py'%turn),raw,budget)
            observed=native.run(identity+'/tool/'+str(turn),script['path'],[],[script,*inputs],kind='tool',workspace=workspace)
            workspace=workspace_inventory(observed['work_root'],budget,self.config['max_workspace_files'],self.config['max_workspace_bytes'],self.config['native']['workspace_entry_cap'])
            directory=Path(observed['receipt']['path']).parent;stream=observed['observation']['streams']['stdout']
            stdout=c.capture({'path':str(directory/'stdout.bin'),'bytes':stream['bytes'],'sha256':stream['sha256']},budget,[directory],empty=True)
            c.need(len(stdout)<=self.config['tool_return_bytes'],'full tool stdout exceeds selected provider-return cap; no truncation')
            tool_result={'stdout':stdout.decode('utf-8',errors='strict'),'workspace':[{'relative_path':x['relative_path'],'bytes':x['source']['bytes'],'sha256':x['source']['sha256']}for x in workspace],'natural_receipt':observed['receipt']}
            messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(tool_result,sort_keys=True,allow_nan=False)})
            attempts.append({'turn':turn,'script':script,'native':observed['receipt'],'workspace':workspace})
        c.need(result is not None,'author did not finish within complete selected turn budget')
        final=c.publish(root/'SEALED_PROGRAM.py',result,budget)
        # No previous tool artifact is silently carried into final execution.
        # The permitted carry is exactly the sealed Python source; final workers
        # receive the common public inputs in a fresh workspace.
        record={'schema':'neural010-author-episode-v1','identity':identity,'replication':replication,'sealed_source':final,'provider':provider.records,'tools':attempts,'provider_seed':cfg['seed'],'provider_determinism':'unknown; identical request seeds do not establish determinism','input_files':inputs,'prompt':prompt,'budget':budget.snapshot(),'status':'completed','whole_study_exit_established':False}
        receipt=c.publish_json(root/'AUTHOR.json',record,budget);budget.check_clock();return {'source':final,'receipt':receipt,'body':record}

    def fixed_authors(self):
        results=[]
        for replication in range(3):
            budget=c.LocalBudget(self.whole,self.config['author_limits']);root=c.new_directory(self.root/str(replication),budget)
            protocol=self.protocol(budget);inputs=[self.config['protocol'],*self.config['protocol_sources'],*self.public_sources]
            prompt={'phase':'data_free_author','replication':replication,'protocol':protocol,'public_source_paths':[d['path']for d in self.public_sources],'authentic_data_or_realized_results_supplied':False,'tool_working_directory':'/work','final_request_is_future_data_only':True}
            results.append(self.invoke_author('fixed-author/'+str(replication),replication,root,inputs,prompt,budget))
        self.whole.check_clock();return {'schema':'neural010-data-free-authors-v1','authors':results,'count':3,'paired_view_author_cost_allocation':'Each replication author cost is counted once globally and allocated one half to each fixed-view comparison. These allocations are not additional work.'}

    def views(self,released,budget):
        c.need(released['schema']=='neural010-released-analysis-v1','complete protected release')
        # The release adapter supplies the same H/M/envelope bytes to every view.
        common=[released[k]for k in('historical','matched','envelope')]
        for d in common:c.authenticate_stream(d,budget,[Path(d['path']).parent])
        c.need(type(released['waveforms'])is list and len(released['waveforms'])==686,'all686 exact waveform descriptors')
        return common

    def execute(self,fixed,released):
        c.need(fixed['schema']=='neural010-data-free-authors-v1'and type(fixed['count'])is int and fixed['count']==3 and len(fixed['authors'])==3,'all3 frozen data-free author episodes')
        common=self.views(released,self.whole);outputs=[];contexts=[];views={}
        for context in schedule.analyst_contexts():
            root=c.new_directory(self.root/('%02d'%len(contexts)),self.whole)
            view={'schema':'neural010-analyst-view-v1','context':context,'envelope':released['envelope'],'historical':released['historical'],'matched':released['matched'],'source':self.public_sources,'waveforms':released['waveforms']if context['view']=='full_waveform'else[],'forbidden_accessors':['assessment_operand','expected_reports','other_contexts','reference_models','reference_training_labels'],'physical_namespace_qualification_required':True}
            viewpin=c.publish_json(root/'VIEW.json',view,self.whole);views[context['id']]=viewpin
            inputs=[*common,viewpin,*view['waveforms'],*self.public_sources]
            if context['mode']=='frozen_program':
                author=fixed['authors'][context['replication']];source=author['source'];author_receipt=author['receipt']
            else:
                authorbudget=c.LocalBudget(self.whole,self.config['author_limits']);authorroot=c.new_directory(root/'author',authorbudget)
                prompt={'phase':'case_adaptive_equal_inputs_tools_compute','context':context,'protocol':self.protocol(authorbudget),'input_files':inputs,'view':view,'tool_working_directory':'/work','final_source_carried_alone':True}
                author=self.invoke_author(context['id'],context['replication'],authorroot,inputs,prompt,authorbudget);source=author['source'];author_receipt=author['receipt']
            budget=c.LocalBudget(self.whole,self.config['execution_limits']);c.authenticate_stream(source,budget,[Path(source['path']).parent])
            request={'schema':'neural010-complete-context-request-v1','task_id':c.TASK,'context':context,'source':source,'envelope':released['envelope'],'view_manifest':viewpin,'historical_packet':released['historical'],'matched_packet':released['matched'],'output_contract':'Both complete historical_submission and matched_submission; exact protocol supplied to author.'}
            requestpin=c.publish_json(root/'REQUEST.json',request,budget)
            nativeroot=c.new_directory(root/'execution',budget);native=Native(self.config['native'],self.config['native_phase_limits'],budget,nativeroot,self.public_sources)
            result=native.run(context['id']+'/final',source['path'],['--request',requestpin['path'],'--output','{WORK}/SUBMISSION.json'],[source,requestpin,*inputs],kind='fixed')
            artifacts=workspace_inventory(result['work_root'],budget,self.config['max_workspace_files'],self.config['max_workspace_bytes'],self.config['native']['workspace_entry_cap'])
            matches=[d['source']for d in artifacts if d['relative_path']=='SUBMISSION.json'];c.need(len(matches)==1 and matches[0]['bytes']<=self.config['max_submission_bytes'],'one complete bounded final report')
            reportpin=matches[0];submission=c.capture_json(reportpin,budget,[Path(result['work_root'])]);c.need(type(submission)is dict,'whole context JSON object')
            record={'context':context,'sealed_source':source,'author':author_receipt,'request':requestpin,'view':viewpin,'native':result['receipt'],'output':reportpin,'status':'completed','returncode':0,'natural_completion':True,'unknown_survivors':False,'budget':budget.snapshot(),'permitted_author_limits':self.config['author_limits'],'permitted_execution_limits':self.config['execution_limits'],'author_actual_cost_allocation':0.5 if context['mode']=='frozen_program'else 1.0,'context_staging_cost_scope':'separately charged whole-phase overhead, same source path in both modes'}
            receipt=c.publish_json(root/'CONTEXT.json',record,budget);record['receipt']=receipt;contexts.append(record);outputs.append(reportpin)
            budget.check_clock()
        self.whole.check_clock();return {'schema':'neural010-complete-analysts-v1','contexts':contexts,'outputs':outputs,'views':views,'envelope':released['envelope'],'count':12,'separate_external_observer_closure_required':True}
