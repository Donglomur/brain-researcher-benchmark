#!/bin/bash
set -e
TASK=/private/tmp/claude-501/-Users-nicholas-Desktop-brain-researcher-benchmark/f9fbdff6-413e-4671-9547-7707c56b1d7c/scratchpad/TRACKDENSITY-002
WORK="$TASK/work"
rm -rf "$WORK"; mkdir -p "$WORK"
export TDI_DATA_DIR="$TASK/environment/data"

echo "########## 1. regenerate fixtures ##########"
python3 "$TASK/synth_build/generate_fixtures.py"

echo ""
echo "########## 2. oracle -> grade (expect 1.000) ##########"
export OUTPUT_DIR="$WORK/oracle_out"
python3 "$TASK/solution/oracle_tdi.py"
GRADE_DIR="$OUTPUT_DIR" python3 "$TASK/validation/grade_dir.py"

echo ""
echo "########## 3. independent impl -> invariance ##########"
export OUTPUT_DIR="$WORK/indep_out"
python3 "$TASK/validation/independent_impl.py"
INDEP_OUT="$OUTPUT_DIR" python3 "$TASK/validation/invariance_report.py"

echo ""
echo "########## 4. wrong pipelines -> grade (expect <1.0; each fails only its axis) ##########"
for MODE in naive vertex_binning no_fragment_qc no_omit wrong_super_grid; do
  export OUTPUT_DIR="$WORK/wrong_$MODE"
  WRONG_MODE=$MODE python3 "$TASK/validation/wrong_pipelines.py"
  printf "%-18s " "$MODE:"
  GRADE_DIR="$OUTPUT_DIR" python3 "$TASK/validation/grade_dir.py"
done
