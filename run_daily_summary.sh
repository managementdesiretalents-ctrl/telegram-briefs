#!/bin/zsh
cd ~/telegram-briefs || exit 1
source .venv/bin/activate
python post_daily_summary_slack.py >> logs/daily.log 2>&1
