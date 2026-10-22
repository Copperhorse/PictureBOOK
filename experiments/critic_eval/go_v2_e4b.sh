#!/usr/bin/env bash
cd "$(dirname "$0")"
export DATASET=_v2
python3 run_critic.py --port 18080 --tag v2_e4b_off_rp11 --think off
python3 run_critic.py --port 18080 --tag v2_e4b_on2048_rp11 --think default
