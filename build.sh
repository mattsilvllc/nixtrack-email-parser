#!/usr/bin/env bash

# Remove old build
rm -rf ./lib
rm lambda_src.zip

# Install Dependencies
pip install -t lib -r requirements.txt

# Create distribution package
zip -r \
      --exclude=build.sh \
      --exclude=test.sh \
      --exclude=setup.sh \
      --exclude=event.json \
      "--exclude=*.pyc" \
      "--exclude=.DS_Store" \
      --exclude=configlocal.json \
      "--exclude=/venv/*" \
      --exclude=requirements.txt \
      --exclude=event.json \
      lambda_src.zip ./
