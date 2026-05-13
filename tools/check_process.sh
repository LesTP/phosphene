#!/bin/bash
# Check if seed process is running, kill if requested
ps aux | grep "run.py" | grep -v grep
if [ $? -eq 0 ]; then
    echo "Process found. Kill with: pkill -f 'run.py'"
else
    echo "No run.py process found."
fi
