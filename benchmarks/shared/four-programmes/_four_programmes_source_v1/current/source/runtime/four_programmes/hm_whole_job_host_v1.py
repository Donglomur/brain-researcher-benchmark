"""Actual H channel dispatch for whole-job HM; no native call at import.

The independently qualified launch, environment and matched-pair producer are
prerequisites. An unavailable producer is a real refusal, never a success flag.
"""
from .common import need, closed, failure, DependencyUnavailable, encode, pin
from .hm_whole_job_native_v1 import HMNativeCampaignOwnerV1
from .hm_whole_job_stage_admission_v1 import publish_original_hm_whole_stage_return_v1

_TOKEN = object()


class HMWholeHostFlowV1:
    def __init__(self, token, campaign):
        need(token is _TOKEN and type(campaign) is HMNativeCampaignOwnerV1,
             'actual source-native campaign owner')
        need(getattr(campaign, '_host_flow_v1', None) is None, 'one actual H flow attempt')
        self.campaign = campaign;self.endpoint = campaign.controller.endpoint
        self.raw_first = None;self.secondaries = [];self.entered = False;self.closed = False
        self.stages = [];self.previous_return = None;self.pending = None
        self.final_prefix = None;self.final_publication = None;self.final_response = None
        self.final_response_message = None
        self.host_terminal = None;self.host_terminal_body = None;self.controller_completion = None
        self.source_session_closed = False;self.terminal_publish_attempted = False
        campaign._host_flow_v1 = self
        campaign.require_original()
        self.endpoint._hm_whole_poll_campaign_v1 = campaign

    def retain(self, error, site):
        if self.raw_first is None:self.raw_first = error
        elif error is not self.raw_first:self.secondaries.append((site, error))
        self.campaign.retain(error, site)

    def _stage(self, pending):
        c = self.campaign;b = pending['body']['body']
        need(b.get('sequence') == len(self.stages) + 1 and len(self.stages) < 3,
             'only full original reference/A/B, never replay or extra stage')
        stage = c.run_stage_once(pending)
        self.stages.append(stage)  # Failed attempts remain in the denominator.
        if stage.raw_first is not None:raise stage.raw_first
        result = publish_original_hm_whole_stage_return_v1(stage, previous_return=self.previous_return)
        response = self.endpoint.respond(pending, status='observed', result={
            'schema': 'hm_whole_stage_dispatch_response_v1', 'return': result})
        stage._actual_controller_response = response
        self.previous_return = result['descriptor']

    def _continuation(self, pending):
        body = pending['body']['body']
        closed(body, ('schema', 'profile', 'pair_id', 'scope', 'inputs', 'full_plan',
                      'stage_returns', 'candidate_seals'))
        need(body['schema'] == 'hm_whole_matched_pair_request_v1' and
             body['profile'] == self.campaign.plan.pin and len(self.stages) == 3 and
             body['stage_returns'] == [s._public_return['descriptor'] for s in self.stages] and
             set(body['candidate_seals']) == {'A', 'B'}, 'full original stage chain before pair request')
        # This source does not prove fresh mount/network namespaces, cache
        # exclusion or common-input custody. The existing scientific consumer
        # also refuses that missing genuine producer. Preserve the hard gap.
        raise DependencyUnavailable('HM_original_matched_pair_issuer',
            'independent fresh-workspace/cache/common-input/own-run producer remains unavailable')

    def run_once(self):
        need(not self.entered, 'one original H control loop, including failure')
        self.entered = True
        try:
            while True:
                self.campaign.require_original()
                pending = self.endpoint.accept();self.pending = pending
                operation = pending['body']['operation']
                if operation == 'stage':self._stage(pending)
                elif operation == 'continuation':self._continuation(pending)
                elif operation == 'final_report':
                    self.final_prefix = self.campaign.close_once(pending)
                    self.final_publication = self.campaign.host.outputs.publish(
                        'hm_whole_CAMPAIGN_PREFIX.json', self.final_prefix)
                    response_result = {
                            'schema': 'hm_whole_final_prefix_response_v1',
                            'prefix': self.final_publication,
                            'later_original_whole_reconciliation_required': True,
                            'scientific_qualification': False}
                    self.final_response_message = {'schema': 'four_programme_host_response_v1',
                        'campaign': self.endpoint.binding['campaign'], 'source': self.endpoint.binding['source'],
                        'sequence': pending['body']['sequence'], 'request': pending['raw_identity'],
                        'status': 'observed' if self.campaign.raw_first is None else 'failed',
                        'result': response_result}
                    self.final_response = self.endpoint.respond(pending,
                        status=self.final_response_message['status'], result=response_result)
                    need(self.final_response == pin(encode(self.final_response_message)),
                         'same actual complete final H wire response, not a supplied acknowledgement')
                    break
                else:raise RuntimeError('original C reported failure; no successful replacement')
        except BaseException as error:
            self.retain(error, 'actual_H_control_loop')
            if self.endpoint.pending is self.pending and not self.endpoint.failed:
                try:
                    self.endpoint.respond(self.pending, status='failed', result={
                        'schema': 'hm_whole_control_failure_v1',
                        'profile': self.campaign.plan.pin,
                        'completed_stages': len([s for s in self.stages if s.eligible]),
                        'full_original_reservations_retained': True,
                        'reference_bodies_withheld': True,
                        'scientific_qualification': False})
                except BaseException as later:self.retain(later, 'actual_failure_response')
        finally:
            # Capture the actual C exit before closing its original observations.
            # The prefix ACK releases C; its typed native owner retains own CPU.
            try:self.controller_completion = self.campaign.finish_controller_once()
            except BaseException as error:self.retain(error, 'actual_C_process_completion')
            try:self.campaign.close_owned_once()
            except BaseException as error:self.retain(error, 'actual_native_observation_close')
            # The native owner retains post-response samples/cleanup failures;
            # its immutable earlier prefix cannot assert those future outcomes.
            self.final_observed_tail = getattr(self.campaign, 'final_tail', None)
            self.native_handles_closed = self.campaign.closed
            if self.campaign.raw_first is not None:
                self.retain(self.campaign.raw_first, 'actual_native_final_tail')
            if not self.native_handles_closed and self.raw_first is None:
                self.retain(RuntimeError('original native observation closure is unknown'), 'native_closure_unknown')
            try:self.campaign.controller.close_once(primary=self.raw_first)
            except BaseException as error:self.retain(error, 'actual_H_endpoint_close')
            self.closed = self.native_handles_closed and self.campaign.controller.close_complete
            try:
                if not self.campaign.session.closed:self.campaign.session.close()
                self.source_session_closed = self.campaign.session.closed
            except BaseException as error:self.retain(error, 'actual_H_source_session_close')
            try:self._publish_terminal_once()
            except BaseException as error:self.retain(error, 'actual_H_terminal_construction')
        if self.raw_first is not None:raise self.raw_first
        return self.host_terminal

    def _publish_terminal_once(self):
        """H publishes after actual C closure; it does not certify its own exit."""
        if self.terminal_publish_attempted:return self.host_terminal
        self.terminal_publish_attempted = True;c = self.campaign
        observation = getattr(c, 'controller_observation', None)
        exit_owner = getattr(c.controller.controller_process, '_hm_exit_accounting_v1', None)
        exit_record = None
        if exit_owner is not None:
            try:exit_record = exit_owner.record()
            except BaseException as error:self.retain(error, 'actual_C_exit_record_unavailable')
        self.host_terminal_body = {
            'schema': 'hm_whole_original_H_terminal_v1', 'profile': c.plan.pin,
            'resource_plan': c.plan.resource_plan_pin,
            'host': c.controller.host_identity, 'controller': c.controller.controller_identity,
            'reference_jobs': 8223, 'conditions': 335, 'qualification_holds': 65,
            'stage_returns': [s._public_return['descriptor'] for s in self.stages
                              if getattr(s, '_public_return', None) is not None],
            'stage_attempts': len(self.stages),
            'stage_eligible': [s.sequence for s in self.stages if s.eligible and s.closure_complete],
            'worker_launch_attempts': sum(s.outer_worker_launch_attempts for s in self.stages),
            'descendant_creations': None,
            'final_C_request': None if self.pending is None else self.pending['raw_identity'],
            'final_C_request_message': None if self.pending is None else self.pending['body'],
            'final_C_body': None if self.pending is None else self.pending['body']['body'],
            'final_H_response': self.final_response,
            'final_H_response_message': self.final_response_message,
            'native_prefix': self.final_publication,
            'final_native_tail': getattr(c, 'final_tail', None),
            'controller_observation': None if observation is None else observation.record,
            'controller_receipt': None if observation is None else observation.receipt,
            'controller_exit_cpu': exit_record,
            'volume_provisioning': c.plan.body['storage'],
            'volume_identity': None if c.volume is None else c.volume.identity,
            'native_handles_closed': self.native_handles_closed,
            'channel_closed': c.controller.close_complete,
            'source_session_closed': self.source_session_closed,
            'full_original_reservations': c.reservations.record(),
            'original_H_share_prefix': c.meter.record(),
            'original_failure': None if self.raw_first is None else failure(self.raw_first),
            'secondary_failures': [{'site': site, 'error': failure(error)}
                                   for site, error in self.secondaries],
            'H_exit_observed_here': False, 'outer_whole_reconciliation_required': True,
            'scientific_qualification': False}
        try:
            self.host_terminal = c.host.outputs.publish('hm_whole_HOST_TERMINAL.json', self.host_terminal_body)
            c.meter.check()
        except BaseException as error:self.retain(error, 'actual_H_terminal_publication')
        return self.host_terminal


def create_original_hm_whole_host_flow_v1(campaign):
    return HMWholeHostFlowV1(_TOKEN, campaign)
