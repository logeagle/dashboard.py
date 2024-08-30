#!/bin/bash

# Create logeagle directory if it doesn't exist
mkdir -p ~/logeagle

# Create virtual environment if it doesn't exist
if [ ! -d "$HOME/logeagle/dashboard_venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$HOME/logeagle/dashboard_venv"
fi

# Activate virtual environment
source "$HOME/logeagle/dashboard_venv/bin/activate"

# Upgrade pip
pip install --upgrade pip

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt

# Run the dashboard
echo "Running dashboard..."
python dashboard.py

# Deactivate virtual environment
deactivate