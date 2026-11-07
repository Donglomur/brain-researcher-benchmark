"""Only tiny disposable Git repositories; never operates on the real index/HEAD."""
from pathlib import Path
import concurrent.futures
import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
import time
import sys
import unittest
from unittest.mock import patch

HERE=Path(__file__).absolute().parent
ROOT=HERE.parents[3]
SPEC=importlib.util.spec_from_file_location('source_queue',ROOT/'tools/neurobench_source_queue.py')
Q=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(Q)
BRANCH='refs/heads/build/neuroscience-200'

def git(root,*args,input=None,index=None):
    env=os.environ.copy()
    for k in list(env):
        if k.startswith('GIT_'):del env[k]
    if index:env['GIT_INDEX_FILE']=str(index)
    return subprocess.check_output(['git','-C',str(root),*args],input=input,stderr=subprocess.PIPE,env=env).decode().strip()

def fp(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='toy-git-',dir=HERE);self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).absolute();self.assertNotEqual(self.root,ROOT)
        git(self.root,'init','-b','build/neuroscience-200');git(self.root,'config','user.name','Toy Reviewer');git(self.root,'config','user.email','toy@example.invalid')
        (self.root/'notes.md').write_text('user base\n');git(self.root,'add','notes.md');git(self.root,'commit','-m','base')
        self.repo=Q.Repo(self.root)
    def snapshot(self):return(git(self.root,'rev-parse','HEAD'),(self.root/'.git/index').read_bytes())
    def fixture(self,name):
        prefix='authoring/'+name;folder=self.root/prefix;folder.mkdir(parents=True)
        (folder/'source.py').write_text('value = '+repr(name)+'\n')
        row={'path':prefix+'/source.py',**fp((folder/'source.py').read_bytes())}
        proposal=folder/'ALLOWLIST.json';proposal.write_text(json.dumps({'files':[row]})+'\n')
        rel=str(proposal.relative_to(self.root));pin=fp(proposal.read_bytes())
        return Q.reviewed_manifest(self.repo,rel,pin['bytes'],pin['sha256'],[prefix],include_manifest=True)
    def queued(self,name):
        records,manifest,prefixes=self.fixture(name);ref='refs/heads/agents/neuro/'+name
        result=Q.make_commit(self.repo,records,manifest,prefixes,ref,'source '+name)
        return records,manifest,prefixes,ref,result
    def merge(self,q):
        records,manifest,prefixes,ref,result=q
        return Q.integrate(self.repo,records,manifest,prefixes,ref,result['commit'],'merge reviewed source',BRANCH,True)
    def test_parallel_scoped_commits_then_merges_preserve_all_worktree_bytes(self):
        before=self.snapshot();a=self.fixture('a');b=self.fixture('b')
        (self.root/'notes.md').write_text('dirty user note\n');(self.root/'untracked.txt').write_text('keep this\n')
        def create(name,parts):return Q.make_commit(self.repo,*parts,'refs/heads/agents/neuro/'+name,'queue '+name)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2)as pool:
            fa=pool.submit(create,'a',a);fb=pool.submit(create,'b',b);qa=fa.result();qb=fb.result()
        self.assertEqual(self.snapshot(),before)
        (self.root/'authoring/a/source.py').write_text('new dirty source after review\n')
        work={str(p.relative_to(self.root)):p.read_bytes()for p in self.root.rglob('*')if p.is_file()and'.git'not in p.relative_to(self.root).parts}
        for name,parts,queued in [('a',a,qa),('b',b,qb)]:
            out=self.merge((*parts,'refs/heads/agents/neuro/'+name,queued));self.assertEqual(out['status'],'integrated');self.assertEqual(out['cleanup'],'complete')
            self.assertEqual(git(self.root,'rev-list','--parents','-n','1',out['commit']).split()[2],queued['commit'])
        after={str(p.relative_to(self.root)):p.read_bytes()for p in self.root.rglob('*')if p.is_file()and'.git'not in p.relative_to(self.root).parts}
        self.assertEqual(work,after);self.assertEqual(git(self.root,'diff','--cached','--name-only'),'')
        self.assertIn('notes.md',git(self.root,'diff','--name-only'));self.assertIn('untracked.txt',git(self.root,'ls-files','--others','--exclude-standard'))
    def test_forbidden_member_gate_before_any_member_body_read(self):
        records,manifest,prefixes=self.fixture('bad');proposal=self.root/manifest['path']
        rows=[dict(records[0]),{'path':'authoring/bad/private.pem','bytes':1,'sha256':'0'*64}]
        proposal.write_text(json.dumps({'files':rows}));p=fp(proposal.read_bytes());seen=[];real=Q.capture
        def checked(root,path,*args):
            seen.append(path);self.assertEqual(path,manifest['path']);return real(root,path,*args)
        before=self.snapshot()
        with patch.object(Q,'capture',side_effect=checked):
            with self.assertRaisesRegex(Q.Refusal,'forbidden_payload'):Q.reviewed_manifest(self.repo,manifest['path'],p['bytes'],p['sha256'],prefixes)
        self.assertEqual(seen,[manifest['path']]);self.assertEqual(self.snapshot(),before)
    def test_tamper_outside_prefix_and_ambiguous_keys(self):
        parts=self.fixture('a');before=self.snapshot();(self.root/'authoring/a/source.py').write_text('TAMPER\n')
        with self.assertRaises(Q.Refusal):Q.make_commit(self.repo,*parts,'refs/heads/agents/neuro/a','tampered')
        self.assertEqual(self.snapshot(),before)
        records,manifest,prefixes=parts;proposal=self.root/manifest['path'];proposal.write_text(json.dumps({'files':[{'path':'other.py','bytes':0,'sha256':hashlib.sha256(b'').hexdigest()}]}));p=fp(proposal.read_bytes())
        with self.assertRaisesRegex(Q.Refusal,'outside_owned_prefix'):Q.reviewed_manifest(self.repo,manifest['path'],p['bytes'],p['sha256'],prefixes)
        proposal.write_text(json.dumps({'files':[],'members':[]}));p=fp(proposal.read_bytes())
        with self.assertRaisesRegex(Q.Refusal,'ambiguous_member_key'):Q.reviewed_manifest(self.repo,manifest['path'],p['bytes'],p['sha256'],prefixes)
    def test_staged_user_work_is_untouched(self):
        q=self.queued('a');(self.root/'notes.md').write_text('staged user change\n');git(self.root,'add','notes.md');before=self.snapshot()
        with self.assertRaisesRegex(Q.Refusal,'staged_user_work'):self.merge(q)
        self.assertEqual(self.snapshot(),before);self.assertFalse(self.repo.journal.exists());self.assertFalse((self.repo.gitdir/'index.lock').exists())
    def test_agent_commit_outside_diff_refused_before_shared_mutation(self):
        q=self.queued('a');rec,man,pre,ref,res=q;idx=self.root/'.git/malicious-index';git(self.root,'read-tree',res['commit'],index=idx)
        blob=git(self.root,'hash-object','-w','--stdin',input=b'outside\n');git(self.root,'update-index','--add','--cacheinfo','100644,'+blob+',outside.md',index=idx)
        tree=git(self.root,'write-tree',index=idx);bad=git(self.root,'commit-tree',tree,'-p',res['base'],input=b'bad\n');git(self.root,'update-ref',ref,bad,res['commit']);idx.unlink();before=self.snapshot()
        with self.assertRaisesRegex(Q.Refusal,'agent_diff_outside'):Q.integrate(self.repo,rec,man,pre,ref,bad,'bad merge',BRANCH,True)
        self.assertEqual(self.snapshot(),before);self.assertFalse(self.repo.journal.exists())
    def test_failure_after_index_publication_rolls_back_both(self):
        q=self.queued('a');before=self.snapshot();real=Q.publish_index
        def fail(*a,**k):real(*a,**k);raise OSError('injected after atomic index replace')
        with patch.object(Q,'publish_index',side_effect=fail):
            with self.assertRaises(OSError):self.merge(q)
        self.assertEqual(self.snapshot(),before);self.assertFalse(self.repo.journal.exists());self.assertFalse((self.repo.gitdir/'index.lock').exists())
    def test_prepared_ref_commit_failure_rolls_back_index(self):
        q=self.queued('a');before=self.snapshot()
        with patch.object(Q.RefTransaction,'commit',side_effect=OSError('injected precommit')):
            with self.assertRaises(OSError):self.merge(q)
        self.assertEqual(self.snapshot(),before);self.assertFalse(self.repo.journal.exists())
    def test_CAS_race_preserves_other_actor_ref_and_original_index(self):
        q=self.queued('a');old,index=self.snapshot();tree=git(self.root,'rev-parse','HEAD^{tree}');raced=git(self.root,'commit-tree',tree,'-p',old,input=b'other actor\n');real=Q.RefTransaction
        def race(repo,branch,old,new):
            git(self.root,'update-ref',branch,raced,old);return real(repo,branch,old,new)
        with patch.object(Q,'RefTransaction',side_effect=race):
            with self.assertRaises(Q.Refusal):self.merge(q)
        self.assertEqual(self.snapshot(),(raced,index));self.assertFalse(self.repo.journal.exists())
    def test_conflict_refuses_without_shared_changes(self):
        (self.root/'authoring').mkdir();(self.root/'authoring/x.py').write_text('base\n');git(self.root,'add','authoring/x.py');git(self.root,'commit','-m','shared source base')
        q=self.queued('a')
        # Add an independent commit to the queued source path, then restore source bytes dirty.
        source=self.root/'authoring/a/source.py';source.write_text('root conflicting version\n');git(self.root,'add','authoring/a/source.py');git(self.root,'commit','-m','root conflict');source.write_text('dirty survives\n');before=self.snapshot()
        with self.assertRaises(Q.Refusal):self.merge(q)
        self.assertEqual(self.snapshot(),before);self.assertEqual(source.read_text(),'dirty survives\n')

    def test_git_child_setup_failure_reaps_and_closes(self):
        real=Q.subprocess.Popen
        for target in ('selector','nonblocking'):
            children=[]
            def started(*a,**k):
                child=real(*a,**k);children.append(child);return child
            fail=patch.object(Q.selectors,'DefaultSelector',side_effect=OSError('injected setup')) if target=='selector' else patch.object(Q.os,'set_blocking',side_effect=OSError('injected setup'))
            before=self.snapshot()
            with patch.object(Q.subprocess,'Popen',side_effect=started),fail:
                with self.assertRaisesRegex(OSError,'injected setup'):Q.GitProcess(self.repo,['update-ref','--stdin'])
            self.assertEqual(len(children),1);child=children[0]
            self.assertIsNotNone(child.poll())
            self.assertTrue(all(s.closed for s in(child.stdin,child.stdout,child.stderr)))
            self.assertEqual(self.snapshot(),before)

    def test_reviewed_author_license_names_only(self):
        for name in ('LICENSE.author','NOTICE.author'):
            self.assertEqual(str(Q.source_path('owned/'+name)),'owned/'+name)
        for name in ('arbitrary.author','LICENSE.pem.author','NOTICE.key.author'):
            with self.assertRaises(Q.Refusal):Q.source_path('owned/'+name)

    def test_process_death_after_index_publish_is_recoverable(self):
        q=self.queued('crash');records,manifest,prefixes,ref,result=q;before=self.snapshot()
        code="""import importlib.util,sys,os,json
spec=importlib.util.spec_from_file_location('queue_child',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
a=json.loads(sys.argv[2]);r=m.Repo(a['repo']);records,manifest,prefixes=m.reviewed_manifest(r,a['manifest']['path'],a['manifest']['bytes'],a['manifest']['sha256'],a['prefixes'],include_manifest=True)
m.RefTransaction.commit=lambda self:os._exit(73)
m.integrate(r,records,manifest,prefixes,a['ref'],a['commit'],'crash control',a['branch'],True)
"""
        args={'repo':str(self.root),'manifest':manifest,'prefixes':prefixes,'ref':ref,'commit':result['commit'],'branch':BRANCH}
        child=subprocess.run([sys.executable,'-I','-S','-B','-c',code,str(ROOT/'tools/neurobench_source_queue.py'),json.dumps(args)],capture_output=True,timeout=10)
        self.assertEqual(child.returncode,73);self.assertTrue(self.repo.journal.exists())
        self.assertEqual(git(self.root,'rev-parse','HEAD'),before[0])
        self.assertNotEqual((self.root/'.git/index').read_bytes(),before[1])
        end=time.monotonic()+5
        while True:
            try:out=Q.recover(self.repo,True);break
            except Q.Refusal as e:
                if str(e)!='journal_owner_process_still_exists'or time.monotonic()>=end:raise
                time.sleep(.02)
        self.assertEqual(out['status'],'recovered_rolled_back');self.assertEqual(self.snapshot(),before)
        self.assertFalse(self.repo.journal.exists());self.assertFalse((self.repo.gitdir/'index.lock').exists())

if __name__=='__main__':unittest.main(verbosity=2)
