"""Complete reviewed reference loop with durable prefix recording on failures."""
from ach_util import need,pin,finish_owned

class ReferenceBudget:
    def __init__(self,ledger,journal):self.ledger,self.journal=ledger,journal
    def reserve(self,charges,phase):
        self.journal.append('reference_attempt',{'phase':phase,'charges':charges})
        self.ledger.reserve(charges,phase)
    def tick(self):return self.ledger.tick()
    def failed(self,phase,error):
        finish_owned([('reference failure accounting',lambda:self.ledger.fail(phase,error)),
                      ('reference failure journal',lambda:self.journal.failure(phase,error))],error)
    def report(self):return self.ledger.report()

class ReferenceRunner:
    def __init__(self,libraries,study,kinds,limits,budget,journal):
        self.libs,self.study,self.kinds,self.limits,self.budget,self.journal=libraries,study,kinds,limits,budget,journal
        self.w=libraries.get('core','reference_workflow');self.n=libraries.get('core','numeric_backend')
        self.strata=libraries.get('core','common').STRATA
    def fit(self,panel,rows):
        w,n=self.w,self.n;study=self.study
        need(panel['actor']=='operator','source-owned independent reference')
        cohort,variant,training=panel['cohort'],panel['variant'],panel['training_animals']
        sets=self.libs.get('core','study').cohort_sets(study)
        need(training==[a for a in sets[cohort] if a!=panel['animal']], 'exact complete outer training')
        need(panel['heads']==list(self.strata),'four original reference heads')
        w.validate_rows(study,rows,self.kinds,cohort,training)
        prefix=panel['bundle_fit_id'];losses=[];records=[];final={}
        try:
            for setting in n.settings():
                for validation in training:
                    inner=[a for a in training if a!=validation]
                    for stratum in self.strata:
                        phase=prefix+'|inner|'+validation+'|'+stratum+'|'+setting['id']
                        bundle=w.fit_one(study,rows,cohort,inner,stratum,variant,setting,self.kinds,self.limits,self.budget,phase)
                        self.journal.append('reference_fitted_head',{'phase':phase,'bundle':bundle})
                        held=w.selected_rows(study,rows,cohort,[validation],stratum)
                        predictions=w.predict_one(bundle,held,self.limits,self.budget,phase+'/validate')
                        _,descriptors,sessions=w.weight_rows(held,[validation])
                        loss=n.validation_loss(predictions,[r['seconds'] for r in held],descriptors,
                            validation,sessions[validation],bundle['model']['target']['variance'])
                        cell={'setting_id':setting['id'],'animal':validation,'stratum':stratum,'loss':loss}
                        record={'phase':phase,'training_animals':inner,'training_rows_pin':pin(bundle['training_row_ids']),
                            'model_pin':pin(bundle['model']),'transform_pin':pin(bundle['transform']),
                            'validation_predictions_pin':pin(dict(zip((r['id'] for r in held),predictions))),
                            'normalized_loss':loss,'resource_plan':bundle['resource_plan']}
                        self.journal.append('reference_validation',{'loss':cell,'record':record,'predictions':predictions})
                        losses.append(cell);records.append(record)
            selection=n.select_setting(losses,training)
            self.journal.append('reference_selection',selection)
            for stratum in self.strata:
                phase=prefix+'|refit|'+stratum
                bundle=w.fit_one(study,rows,cohort,training,stratum,variant,selection['setting'],self.kinds,self.limits,self.budget,phase)
                record={'phase':phase,'training_animals':training,'training_rows_pin':pin(bundle['training_row_ids']),
                    'model_pin':pin(bundle['model']),'transform_pin':pin(bundle['transform']),'resource_plan':bundle['resource_plan']}
                self.journal.append('reference_final_head',{'bundle':bundle,'record':record})
                final[stratum]=bundle;records.append(record)
            need(len(records)==4*(20*len(training)+1),'all required actual reference fits')
            result={'panel_key':prefix.removesuffix('|final'),'selection':selection,'selection_pin':pin(selection),
                'history_schedule_pin':study['admission_evidence']['logical_history'],'loss_cells':losses,
                'fitted_state':final,'pending_query_ids':list(panel['query_ids']),'fit_records':records,
                'fit_record_pin':pin(records),'logical_budget':self.budget.report(),'scientific_qualified':False}
            self.journal.append('reference_bundle_seal',result)
            return result
        except BaseException as error:
            self.budget.failed(prefix,error)
            raise
    def query(self,fit,view,entitlement):
        result=self.w.infer_reference_query(fit,view,entitlement,self.limits,self.budget)
        receipt=self.journal.append('reference_query',result)
        return result,receipt
