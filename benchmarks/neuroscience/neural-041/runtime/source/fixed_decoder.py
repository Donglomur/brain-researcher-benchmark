"""Concrete decoder-only arm. Frozen recipe, train-only grouped tuning."""
def fit(api,recipe):
    return api.fit_reference(recipe['method'])

def predict(state,api,recipe):
    return api.predict_reference(state)

def describe(recipe):
    return {'target':'memory_load_1_vs_3','unit':'patient','window':'half_open_2.5s_maintenance',
        'estimand':'Predict high versus low load for an unseen patient under the fixed eligibility policy, using '+recipe['method']+'.',
        'uncertainty':'Report complete per-patient metrics and post-barrier paired-patient intervals conditional on frozen predictions; not refitted-training uncertainty.',
        'alternatives':['Regional/channel/unit availability and artifact selection may correlate with load.','Early maintenance may retain sensory encoding effects.','Bundle spike interpolation couples LFP and spike information.'],
        'limitations':'Observational clinical cohort, unverified preprocessing temporal support and unqualified reference competence; decoding is not a causal memory mechanism.'}
