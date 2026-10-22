#!/bin/sh
H=/home/copper/Git/PictureBOOK/experiments/page_defects; cd $H
python3 detect_list.py manifest_v2.json results/list_q35.jsonl --model qwen35_4b > results/list_q35.log 2>&1
python3 detect.py manifest_v2.json results/v2_q35.jsonl --crops --model qwen35_4b > results/v2_q35.log 2>&1
echo done > results/q35_done.txt
