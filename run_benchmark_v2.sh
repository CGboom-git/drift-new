#!/bin/bash
# AgentDojo full benchmark with auto-resume and checkpoint support
# Usage: nohup ./run_benchmark_v2.sh > benchmark_v2.log 2>&1 &

set -e
source ~/anaconda3/etc/profile.d/conda.sh
conda activate drift
export OPENAI_API_KEY="sk-9Q8E6mPWFMSMcohvt5eDMIt8HHW5y8SPcqbPhf5oGB4VWMjx"
export OPENAI_BASE_URL="https://api.uiuihao.com/v1"
cd /home/cg/Code/DRIFT

CHECKPOINT_FILE="/home/cg/Code/DRIFT/benchmark_checkpoint.txt"
LOG_DIR="/home/cg/Code/DRIFT/benchmark_logs"
mkdir -p "$LOG_DIR"

SUITES=(banking slack travel workspace)
FLAGS="--do_attack --attack_type important_instructions --model gpt-4o-mini-2024-07-18 --benchmark_version v1.2 --build_constraints --injection_isolation --dynamic_validation --source_flow_validation --controlled_action_extension --source_flow_log"

# Read checkpoint
COMPLETED=""
if [ -f "$CHECKPOINT_FILE" ]; then
    COMPLETED=$(cat "$CHECKPOINT_FILE")
    echo "=== [$(date)] Resuming from checkpoint. Completed: $COMPLETED ==="
fi

for suite in "${SUITES[@]}"; do
    if echo "$COMPLETED" | grep -q "$suite"; then
        echo "=== [$(date)] SKIP $suite (already completed) ==="
        continue
    fi

    LOGFILE="$LOG_DIR/${suite}.log"
    echo "=== [$(date)] Start $suite ==="
    
    # First attempt: without force_rerun (skip existing)
    python pipeline_main.py --suites $suite $FLAGS >> "$LOGFILE" 2>&1 && SUITE_OK=1 || SUITE_OK=0
    
    # If crashed mid-way, resume without force_rerun to skip completed cases
    RETRY=0
    while [ $SUITE_OK -ne 1 ] && [ $RETRY -lt 3 ]; do
        RETRY=$((RETRY + 1))
        echo "=== [$(date)] $suite crashed, retry $RETRY/3 ===" >> "$LOGFILE"
        sleep $((RETRY * 10))
        python pipeline_main.py --suites $suite $FLAGS >> "$LOGFILE" 2>&1 && SUITE_OK=1 || SUITE_OK=0
    done

    if [ $SUITE_OK -eq 1 ]; then
        echo "$suite" >> "$CHECKPOINT_FILE"
        echo "=== [$(date)] End $suite (OK) ==="
    else
        echo "=== [$(date)] End $suite (FAILED after 3 retries) ==="
    fi
done

echo "=== [$(date)] ALL DONE ==="
