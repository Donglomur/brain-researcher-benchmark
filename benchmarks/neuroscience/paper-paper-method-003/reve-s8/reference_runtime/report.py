"""Concrete report assembly from the closed operator projection, no query access."""
from .catalog import need

def scientific_report(io,c):
    projections=[]
    for pin in io.r['input_manifest']:
        if not pin['path'].endswith('.json'):continue
        obj=io.json(pin['path'])
        if obj.get('schema')=='reve-post-grading-participant-view-v1':projections.append(obj)
    need(len(projections)==1,'one actual closed public grader projection');g=projections[0]
    for name,s in io.r['expected_outputs'].items():
        need(s['kind']=='claim','report cannot alter a state or prediction');io.emit(name,{'obligations':s['obligations'],'hypotheses':['Reproduce each immutable original scientific question; evaluate prospectively selected improvements separately.'],'methods':{'fixed_recipe':c['recipe'],'source_id':io.r['source_id']},'citations':['https://github.com/elouayas/reve_eeg','https://github.com/wjq-learning/CBraMod'],'limitations':['Source construction and successful passive collection do not establish numerical qualification or recovered historical training.','Missing mandatory studies remain in the denominator.'],'results':g})
