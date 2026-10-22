#!/usr/bin/env bash
cd "$(dirname "$0")"
export DATASET=_v2
python3 run_critic.py --port 18080 --tag v2_e2b_img1120_off --think off
