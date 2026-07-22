#!/bin/bash
source /home/cg/.config/drift/openai.env
export OPENAI_API_KEY OPENAI_BASE_URL
cd /home/cg/Code/DRIFT
exec bash /home/cg/Code/DRIFT/experiments/run_repair_smoke.sh > /home/cg/Code/DRIFT/experiments/repair_smoke.log 2>&1
