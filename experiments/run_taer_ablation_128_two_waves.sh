#!/usr/bin/env bash
set -u
source /usr/local/miniconda3/etc/profile.d/conda.sh
source /data/home/qyc/.config/drift/openai.env
cd /data/home/qyc/Project/drift-new

STATUS=experiments/taer_ablation128_two_waves.status
echo "$(date -Is) wave1_start full no_anchor" >> "$STATUS"
conda run --no-capture-output -n drift python -B experiments/run_taer_ablation_128_variant.py --variant full \
  > experiments/taer_ablation128_full.log 2>&1 &
full_pid=$!
echo "$full_pid" > experiments/taer_ablation128_full.pid
conda run --no-capture-output -n drift python -B experiments/run_taer_ablation_128_variant.py --variant no_anchor \
  > experiments/taer_ablation128_no_anchor.log 2>&1 &
anchor_pid=$!
echo "$anchor_pid" > experiments/taer_ablation128_no_anchor.pid

wait "$full_pid"; full_rc=$?
wait "$anchor_pid"; anchor_rc=$?
echo "$(date -Is) wave1_end full_rc=$full_rc no_anchor_rc=$anchor_rc" >> "$STATUS"
if [[ $full_rc -ne 0 || $anchor_rc -ne 0 ]]; then
  echo "$(date -Is) stopped_before_wave2" >> "$STATUS"
  exit 1
fi

echo "$(date -Is) wave2_start no_scope no_ephemeral" >> "$STATUS"
conda run --no-capture-output -n drift python -B experiments/run_taer_ablation_128_variant.py --variant no_scope \
  > experiments/taer_ablation128_no_scope.log 2>&1 &
scope_pid=$!
echo "$scope_pid" > experiments/taer_ablation128_no_scope.pid
conda run --no-capture-output -n drift python -B experiments/run_taer_ablation_128_variant.py --variant no_ephemeral \
  > experiments/taer_ablation128_no_ephemeral.log 2>&1 &
ephemeral_pid=$!
echo "$ephemeral_pid" > experiments/taer_ablation128_no_ephemeral.pid

wait "$scope_pid"; scope_rc=$?
wait "$ephemeral_pid"; ephemeral_rc=$?
echo "$(date -Is) wave2_end no_scope_rc=$scope_rc no_ephemeral_rc=$ephemeral_rc" >> "$STATUS"
if [[ $scope_rc -ne 0 || $ephemeral_rc -ne 0 ]]; then
  exit 1
fi
echo "$(date -Is) all_complete" >> "$STATUS"
