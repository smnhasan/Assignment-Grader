#!/bin/bash

# Port where the Gradio web interface runs
PORT=7860

echo "Checking if port $PORT is currently in use..."
PID=$(lsof -t -i:$PORT)

if [ -n "$PID" ]; then
  echo "Stopping previous instance (PID: $PID)..."
  kill -9 $PID
  sleep 1.5
  echo "Port $PORT is now free."
else
  echo "Port $PORT is free."
fi

# Run the app in the current active conda/python environment
echo "Starting the AI Assignment Grader..."
/home/nahid/anaconda3/envs/assessment-env/bin/python3 app.py
