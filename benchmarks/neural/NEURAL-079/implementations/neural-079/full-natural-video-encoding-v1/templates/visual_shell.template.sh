#!/bin/bash
# Site notification address intentionally omitted in this public template.
#SBATCH --job-name=EMD-03_encoding_models-01_extract_stimulus_vision_features
#SBATCH --mail-type=end
#SBATCH --mem=200000
#SBATCH --time=20:00:00
#SBATCH --qos=extended

# Changing to the .py script directory
cd ${N079_SITE_HOME:?set_site_home}/projects/eeg_moments_dataset/github/EMD/03_encoding_models

# Activating the Anaconda environment
source ${N079_SITE_HOME:?set_site_home}/anaconda3/etc/profile.d/conda.sh
conda activate berg

# Running the job
python 01_extract_stimulus_vision_features.py