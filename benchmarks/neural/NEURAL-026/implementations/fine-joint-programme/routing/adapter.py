"""Disabled source-only route; registration and execution authority are absent."""
import json
def main():
    print(json.dumps({'task_id':'NEURAL-026','status':'held_source_only','activated':False,
                      'conditions':['specification_only_reconstruction_v2','reference_code_control_v2'],
                      'full_case_count':50,'planned_native_producers':150,'canonical_tasks':1,
                      'reason':'Requires authentic full preparation, exact exposure/method/environment/resources, independent custody and separately authorized grading.'}))
    return 2
if __name__=='__main__':raise SystemExit(main())
