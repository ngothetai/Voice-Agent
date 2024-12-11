#!/bin/bash

# Start the Burr UI
poetry run burr --host 0.0.0.0 --port 5001 &

# Start the Botvov
poetry run python -m botvov.main