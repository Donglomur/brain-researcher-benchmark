"""One source-fixed Harbor agent; model/credentials/settings have no defaults."""
from __future__ import annotations
from pathlib import Path
from harbor.agents.base import BaseAgent
from .schema import *
from .responses import investigate,InvestigationFailure

class FigureAgent(BaseAgent):
    @staticmethod
    def name():return 'tms-figure2b-responses'
    def version(self):return 'source-only-v1'
    def __init__(self,logs_dir,model_name=None,logger=None,mcp_servers=None,skills_dir=None,
                 *,extra_env=None,load_trajectory=None,operator_configuration=None,**kwargs):
        require(not mcp_servers and not skills_dir and not extra_env and load_trajectory is None,'no extra candidate capabilities')
        # The pinned Harbor factory may supply its supported logger/context keys;
        # caller validation rejects additional selected agent kwargs before import.
        super().__init__(logs_dir,model_name=model_name,logger=logger,mcp_servers=None,
                         skills_dir=None,extra_env=None,load_trajectory=None,**kwargs)
        keys(operator_configuration,{'path','bytes','sha256'});pin({k:operator_configuration[k] for k in ('bytes','sha256')})
        self._configuration=operator_configuration;self._selected_model=model_name;self._admitted=None
    async def setup(self,environment):
        budget=environment._tms_budget;exact_budget(budget)
        row=self._configuration
        cfg=load(row['path'],{k:row[k] for k in ('bytes','sha256')},budget)
        keys(cfg,{'schema','binding','capsule','limits','credential','journal'})
        require(cfg['schema']=='tms_figure2b_agent_configuration_v1','private fixed agent configuration')
        capsule(cfg['capsule']);limits(cfg['limits']);directory(cfg['journal'])
        require(self._selected_model==cfg['capsule']['model'],'same exact selected model')
        self._admitted=cfg
    async def run(self,instruction,environment,context):
        require(self._admitted is not None,'setup admission required');cfg=self._admitted
        require(instruction==cfg['capsule']['instruction'],'same complete frozen instruction')
        try:
            result=await investigate(environment=environment,configuration=cfg['capsule'],
                policy=cfg['limits'],credential_selection=cfg['credential'],output=cfg['journal'],
                binding=cfg['binding'],budget=environment._tms_budget,
                receipt_budget=environment._tms_receipt_budget)
        except InvestigationFailure as error:
            # Harbor may serialize/swallow an agent exception. Preserve the strong
            # source-owned carrier for the trusted child, separate from its summary.
            environment._tms_investigation_failure=error
            raise
        require(result['outcome']=='completed' and result['unknown_provider_outcome'] is False,'actual agent completion')
        # Context metadata is secondary; the host authenticates the complete raw
        # AGENT_RESULT and response/tool chain rather than trusting these fields.
        if hasattr(context,'n_input_tokens'):context.n_input_tokens=result['observed_input_tokens']
        if hasattr(context,'n_output_tokens'):context.n_output_tokens=result['observed_output_tokens']
