#!/usr/bin/env bash

set -u

MODE="${1:-sequential}"  # sequential | parallel
RUNS="${2:-2}"
PAPERS_JSON="${3:-data/gap_analysis_papers.json}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/results/run_logs"
mkdir -p "${LOG_DIR}"

TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/run_${TIMESTAMP}_${MODE}.log"

run_one() {
  local label="$1"
  local cmd="$2"
  echo "[${label}] START $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "${LOG_FILE}"
  echo "[${label}] CMD: ${cmd}" | tee -a "${LOG_FILE}"
  (cd "${PROJECT_ROOT}" && bash -lc "source .venv/bin/activate && ${cmd}") >> "${LOG_FILE}" 2>&1
  local status=$?
  echo "[${label}] EXIT ${status} $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "${LOG_FILE}"
  return ${status}
}

run_sequence() {
  local run_id="$1"
  run_one "${run_id}-strands" "python orchestrators/strands/run_gap_analysis.py --papers-json ${PAPERS_JSON}"
  run_one "${run_id}-langgraph" "python orchestrators/langgraph/run_gap_analysis.py --papers-json ${PAPERS_JSON}"
  run_one "${run_id}-autogen" "python orchestrators/autogen/run_gap_analysis.py --papers-json ${PAPERS_JSON}"
  run_one "${run_id}-openai" "python orchestrators/openai_swarm/run_gap_analysis.py --papers-json ${PAPERS_JSON}"
}

run_parallel() {
  local run_id="$1"
  run_one "${run_id}-strands" "python orchestrators/strands/run_gap_analysis.py --papers-json ${PAPERS_JSON}" &
  p1=$!
  run_one "${run_id}-langgraph" "python orchestrators/langgraph/run_gap_analysis.py --papers-json ${PAPERS_JSON}" &
  p2=$!
  run_one "${run_id}-autogen" "python orchestrators/autogen/run_gap_analysis.py --papers-json ${PAPERS_JSON}" &
  p3=$!
  run_one "${run_id}-openai" "python orchestrators/openai_swarm/run_gap_analysis.py --papers-json ${PAPERS_JSON}" &
  p4=$!
  wait ${p1} ${p2} ${p3} ${p4}
}

case "${MODE}" in
  sequential|seq)
    echo "Running ${RUNS} sequential rounds" | tee -a "${LOG_FILE}"
    for i in $(seq 1 "${RUNS}"); do
      run_sequence "run${i}"
    done
    ;;
  parallel|par)
    echo "Running ${RUNS} parallel rounds" | tee -a "${LOG_FILE}"
    for i in $(seq 1 "${RUNS}"); do
      run_parallel "run${i}"
    done
    ;;
  *)
    echo "Unknown mode: ${MODE}. Use 'sequential' or 'parallel'." | tee -a "${LOG_FILE}"
    exit 2
    ;;
esac

echo "All runs complete. Log: ${LOG_FILE}"
