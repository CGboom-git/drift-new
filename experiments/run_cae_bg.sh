#!/bin/bash
cd /home/cg/Code/DRIFT
source /home/cg/.config/drift/openai.env
export OPENAI_API_KEY OPENAI_BASE_URL
exec bash /home/cg/Code/DRIFT/experiments/run_cae_ablation.sh > /home/cg/Code/DRIFT/experiments/cae_ablation.log 2>&1
