#!/bin/bash
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
source "$SCRIPT_DIR/venv/bin/activate"

# Use pulseaudio for audio output
export SDL_AUDIODRIVER=pulse

python3 "$SCRIPT_DIR/main.py" "$@"
