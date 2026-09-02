#!/bin/bash

set -e

if [[ $ENVIRONMENT == "development" ]]; then
    echo "Installing development dependencies from uv.lock (frozen)..."
    uv sync --frozen --no-install-project --extra dev
    echo "Installing development dependencies... Done!"
else
    echo "Installing production dependencies from uv.lock (frozen)..."
    uv sync --frozen --no-install-project --no-default-groups
    echo "Installing production dependencies... Done!"
fi
