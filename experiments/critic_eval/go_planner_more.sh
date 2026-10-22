#!/usr/bin/env bash
cd "$(dirname "$0")"
kill $(cat .run/server_18080.pid) 2>/dev/null; sleep 4
./serve.sh e2b 18080 2048 1.0 4
python3 planner_test.py --port 18080 --tag planner_e2b_rp10 --conds single_on,multi_off --repeats 2
kill $(cat .run/server_18080.pid); sleep 4
./serve.sh e4b 18080 2048 1.1 4
python3 planner_test.py --port 18080 --tag planner_e4b_rp11 --conds single_on,multi_off --repeats 2
kill $(cat .run/server_18080.pid); sleep 3
echo ALL DONE
