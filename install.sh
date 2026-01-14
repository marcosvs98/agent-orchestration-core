#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

if [[ $ENVIRONMENT == "development" ]]; then
    echo "Installing development dependencies..."
    uv pip install --system -e ".[dev]"
    echo "Installing development dependencies... Done!"
else
    echo "Installing production dependencies..."
    uv pip install --system -e .
    echo "Installing production dependencies... Done!"
fi
