#!/usr/bin/env bash
PROJECT_ROOT_FOLDER="$(pwd)"

# Remove old build
rm -rf ./build

# Copy files
mkdir build

cp requirements.txt ./build/requirements.txt
cp main.py ./build
cp -r ./config ./build

# Install Dependencies
cd build
pip install -t lib -r requirements.txt

# Create distribution package
zip -r \
      --exclude=requirements.txt \
      dist.zip ./
