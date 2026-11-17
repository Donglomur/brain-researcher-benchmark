"""Emit source-derived commands only. Never imports/executes NeuroPyxels or downloads weights."""
import argparse,json

def commands(data_root,feature_root):
    return {'status':'unexecuted_source_recipe_not_qualified_reference',
      'dataset':['python','-m','npyx.c4.dataset_init','--data-folder',data_root],
      'monkey':['python','-m','npyx.c4.monkey_dataset_init','--data-folder',data_root],
      'baseline_template':['python','-m','npyx.c4.run_baseline_classifier','--features-folder',feature_root,'--model','MODEL','--loo'],
      'deep_template':['python','-m','npyx.c4.run_deep_classifier','--data-folder',data_root,'--loo','--use_layer','--augment_acg','--augment_wvf'],
      'blocking':['Option spellings are source-checked; complete input/config/version bindings still precede any execution.','Official preprocessing/ACG paths, engineered feature selection, unit selection and VAE training exposure require full binding.','Deep entry automatically requests VAE checkpoints; supplied source is not permission to use its legacy/private-link downloader.','Use only verified public Figshare originals; no encrypted link/password flow.','Import/dependency lock and baseline sklearn penalty compatibility remain unqualified.']}
def main():
    p=argparse.ArgumentParser();p.add_argument('--data-root',required=True);p.add_argument('--features-root',required=True);a=p.parse_args();print(json.dumps(commands(a.data_root,a.features_root),indent=2))
if __name__=='__main__':main()
