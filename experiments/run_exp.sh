#!/bin/bash
source /home/cg/.config/drift/openai.env
export OPENAI_API_KEY
export OPENAI_BASE_URL
cd /home/cg/Code/DRIFT
exec /home/cg/anaconda3/envs/drift/bin/python experiments/run_cg_5per.py > experiments/run_cg_5per_v2.log 2>&1
