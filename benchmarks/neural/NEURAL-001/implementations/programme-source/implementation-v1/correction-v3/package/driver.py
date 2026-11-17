"""Complete phase composition, without a finished-prediction callback substitute.

Host capabilities implement independently qualified storage, sandbox, monitoring,
provider credential custody and method admission. They are execution dependencies;
this source does not infer isolation from their Python identity. Reference and
protected grading math dispatch to the captured local implementations below.
"""
from .protocol import require, panels
from .investigator import investigate
from .provider import Provider


class ExecutionDriver:
    def __init__(self, *, host, packet_store, subjects, provider_selection,
                 instructions, method_reviewer, reference_progress, channel_kinds_by_person):
        self.host, self.store = host, packet_store
        self.subjects = subjects
        self.by_person = {s.canonical_id:s for s in subjects}
        self.provider_selection = provider_selection
        self.instructions = instructions
        self.reviewer = method_reviewer
        self.reference_progress = reference_progress
        self.channel_kinds_by_person = channel_kinds_by_person
        self.local_reference_states = {}
        self.training_person = None
        self.training_views = {}

    def _training(self, person, arm):
        if self.training_person != person:
            # Plan order completes every panel for one person before advancing.
            # Keep at most one person's numerical training and reference states.
            self.training_views.clear()
            self.local_reference_states.clear()
            self.training_person = person
        key = 'no_neural' if arm == 'no_neural' else 'neural'
        if key not in self.training_views:
            self.training_views[key] = self.store.load_training(person,key)
        return self.training_views[key]

    def _context(self, request, request_pin):
        s = self.by_person.get(request['person'])
        public = {'task_id':'NEURAL-001', 'replicate':self.host.replicate,
                  'mode':request['mode'], 'arm':request['arm'],
                  'operation':request['operation'],
                  'tool_feedback_byte_cap':self.host.tool_feedback_byte_cap}
        if s is not None:
            public['person_alias'] = s.public_alias
        if request['query_id']:
            public['query_id'] = request['query_id']
        # Public dict deliberately lacks canonical ID, source order, root paths,
        # another participant/query, protected target/groups and private keys.
        return self.host.fresh_context(request,request_pin,public)

    def _investigate(self, request, ctx, phase):
        provider = Provider(self.provider_selection,ctx.budget,ctx.journal,
                            self.host.credential_capability)
        return investigate(provider=provider,engine=ctx.engine,method_reviewer=self.reviewer,
                instruction=self.instructions[phase],view_description=ctx.public_description,
                context=ctx.opaque_id,phase=phase,budget=ctx.budget,journal=ctx.journal,
                cutoff=ctx.cutoff,max_steps=ctx.max_steps)

    def author(self, request, request_pin):
        ctx = self._context(request,request_pin)
        require(request['exposure']['llm_numeric_access'] is False
                and request['exposure']['query_count']==0,'predata authoring only')
        ctx.stage_documents_only()
        sealed = self._investigate(request,ctx,'author')
        artifacts = ctx.capture_authoring(sealed,source_cap=65536)
        return ctx.finish_observed(artifacts)

    def train(self, request, request_pin):
        # Lazy scientific imports occur only after outer independent qualification.
        from . import operators
        from .reference.reference_engine import state_payload
        ctx = self._context(request,request_pin)
        s = self.by_person[request['person']]
        arm = request['arm']
        training = self._training(s.canonical_id,arm)
        if request['actor']=='reference':
            family=request['reference_family']
            kinds=self.channel_kinds_by_person[s.canonical_id]
            state=operators.reference_training(training,s,family,kinds,
                        lambda event:ctx.reference_progress(event))
            metadata,arrays=state_payload(state)
            artifacts=ctx.capture_reference_state(metadata,arrays,metadata['report'])
            self.local_reference_states[(s.canonical_id,family)]=state
        else:
            ctx.stage_training_only(training,request['artifacts'])
            if request['mode']=='adaptive_case':
                sealed=self._investigate(request,ctx,'training')
                # Current training investigation must still produce a sealed fit
                # recipe/state; no training workspace becomes a query workspace.
                artifacts=ctx.execute_training_and_seal(sealed,request['artifacts'])
            else:
                artifacts=ctx.execute_training_and_seal(None,request['artifacts'])
            require(self.reviewer.admit_frozen_training(artifacts,s.public_alias,arm) is True,
                    'independent frozen training method admission refused')
        return ctx.finish_observed(artifacts)

    def predict(self, request, request_pin):
        from . import operators
        ctx=self._context(request,request_pin)
        s=self.by_person[request['person']]
        query=self.store.load_query(s.canonical_id,request['query_id'],request['arm'])
        if request['actor']=='reference':
            state=self.local_reference_states[(s.canonical_id,request['reference_family'])]
            prediction=operators.reference_prediction(state,query,ctx.reference_progress)
            artifacts=ctx.capture_prediction(prediction,query,method='independent_frozen_reference')
        else:
            # Allowed training views plus exactly one transformed current query.
            ctx.stage_current_case(query,request['artifacts'],readonly_trained_state=True)
            if request['mode']=='adaptive_case':
                sealed=self._investigate(request,ctx,'case')
                artifacts=ctx.execute_current_prediction(sealed,query,request['artifacts'])
            else:
                artifacts=ctx.execute_current_prediction(None,query,request['artifacts'])
            # Broad synthesis is allowed. This is method review, not forced
            # equality to one tool or a finite-bank routing restriction.
            require(self.reviewer.admit_case_method(artifacts,query['id'],request['exposure']) is True,
                    'independent current-case method admission refused')
        return ctx.finish_observed(artifacts)

    def assemble(self, request, request_pin):
        from . import operators
        ctx=self._context(request,request_pin)
        s=self.by_person[request['person']]
        refs=request['artifacts']['predictions']
        require(set(refs)==set(s.query_ids),'all120 predictions before person assembly')
        predictions={qid:ctx.read_prediction(refs[qid],qid,n)
                     for qid,n in zip(s.query_ids,s.query_lengths)}
        body=operators.assemble(predictions,s)
        return ctx.finish_observed({'submission':ctx.capture_submission(body,s.canonical_id)})

    def grade_all(self, request, request_pin):
        from . import operators
        ctx=self._context(request,request_pin)
        refs=request['artifacts']['submissions']
        require(len(refs)==264,'complete11x24 submissions before protected grade')
        bodies={panel:{s.canonical_id:ctx.read_submission(refs[panel+'/'+s.canonical_id])
                       for s in self.subjects} for panel in panels()}
        # These capabilities are not called until operators validates ALL264 bodies.
        report=operators.grade_all(bodies,self.subjects,self.host.protected_target_loader,
                                   self.host.protected_group_loader,progress=ctx.reference_progress)
        artifacts=ctx.capture_protected_report(report)
        return ctx.finish_observed(artifacts)

    def confirm_trained_state_unchanged(self, request, report):
        # Independent outside-worker reauthentication, not candidate self-report.
        return self.host.confirm_trained_state_unchanged(request,report)

    def fail_current_phase(self, reason, request_pin):
        return self.host.fail_current_context(reason,request_pin)
