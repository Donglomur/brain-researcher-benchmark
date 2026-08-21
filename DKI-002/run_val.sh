#!/bin/bash
set -e
TASK=/private/tmp/claude-501/-Users-nicholas-Desktop-brain-researcher-benchmark/f9fbdff6-413e-4671-9547-7707c56b1d7c/scratchpad/DKI-002
WORK=$TASK/_valwork
rm -rf "$WORK"; mkdir -p "$WORK"
export DKI_DATA_DIR="$TASK/environment/data"

echo "########## 1. regenerate fixtures ##########"
python3 "$TASK/synth_build/generate_fixtures.py" 2>/dev/null

echo ""
echo "########## 2. oracle -> grade (expect 40/40 = 1.000) ##########"
export OUTPUT_DIR="$WORK/oracle_out"
python3 "$TASK/solution/oracle_dki.py"
GRADE_DIR="$OUTPUT_DIR" python3 "$TASK/validation/grade_dir.py"

echo ""
echo "########## 3. independent impl (WLS + diff quadrature) -> invariance ##########"
export OUTPUT_DIR="$WORK/indep_out"
python3 "$TASK/validation/independent_impl.py"
INDEP_OUT="$OUTPUT_DIR" python3 "$TASK/validation/invariance_report.py"

echo ""
echo "########## 3b. sanity_recover (recompute vs planted truth + drop detection) ##########"
python3 "$TASK/validation/sanity_recover.py"

echo ""
echo "########## 4. wrong pipelines -> grade (expect <1.0; each fails its axis) ##########"
for MODE in naive_uniform force_kurtosis nonrobust dti_all_shells; do
  export OUTPUT_DIR="$WORK/wrong_$MODE"
  WRONG_MODE=$MODE python3 "$TASK/validation/wrong_pipelines.py"
  printf "%-16s " "$MODE:"
  GRADE_DIR="$OUTPUT_DIR" python3 "$TASK/validation/grade_dir.py"
done
