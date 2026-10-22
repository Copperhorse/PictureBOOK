#!/usr/bin/env bash
cd "$(dirname "$0")"
python3 planner_test.py --port 18080 --tag planner_e2b_rp11 --repeats 3
