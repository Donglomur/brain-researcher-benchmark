#!/bin/bash
set -e
TASK=/private/tmp/claude-501/-Users-nicholas-Desktop-brain-researcher-benchmark/f9fbdff6-413e-4671-9547-7707c56b1d7c/scratchpad/GABOR-002
WORK=/private/tmp/claude-501/-Users-nicholas-Desktop-brain-researcher-benchmark/f9fbdff6-413e-4671-9547-7707c56b1d7c/scratchpad/gabor_valwork
rm -rf "$WORK"; mkdir -p "$WORK"
export GABOR_DATA_DIR="$TASK/environment/data"

echo "########## 0. bit-identical core check ##########"
for f in gabor_ref.py gabor_pipeline.py; do
  if diff -q "$TASK/solution/$f" "$TASK/tests/$f" >/dev/null; then echo "  $f: identical"; else echo "  $f: !!! DIFFERS"; fi
done

echo ""
echo "########## 1. regenerate fixtures ##########"
python3 "$TASK/synth_build/generate_fixtures.py" | tail -2

echo ""
echo "########## 2. oracle -> grade (expect 1.000) ##########"
export OUTPUT_DIR="$WORK/oracle_out"
GABOR_DATA_DIR="$GABOR_DATA_DIR" OUTPUT_DIR="$OUTPUT_DIR" python3 "$TASK/solution/oracle_gabor.py"
GRADE_DIR="$OUTPUT_DIR" python3 "$TASK/validation/grade_dir.py"

echo ""
echo "########## 3. independent impl -> invariance (expect 1.000 + high corr) ##########"
export OUTPUT_DIR="$WORK/indep_out"
python3 "$TASK/validation/independent_impl.py"
GRADE_DIR="$OUTPUT_DIR" python3 "$TASK/validation/grade_dir.py"
INDEP_OUT="$OUTPUT_DIR" python3 "$TASK/validation/invariance_report.py"

echo ""
echo "########## 3b. sanity_recover (planted structure + bimodal gap) ##########"
python3 "$TASK/validation/sanity_recover.py"

echo ""
echo "########## 4. wrong pipelines -> grade (expect <1.0; naive_single is the majority-bite) ##########"
for MODE in naive_single no_exclude no_deconv no_corrupt keep_all_thresh; do
  export OUTPUT_DIR="$WORK/wrong_$MODE"
  WRONG_MODE=$MODE python3 "$TASK/validation/wrong_pipelines.py" 2>/dev/null
  printf "%-18s " "$MODE:"
  GRADE_DIR="$OUTPUT_DIR" python3 "$TASK/validation/grade_dir.py"
done
