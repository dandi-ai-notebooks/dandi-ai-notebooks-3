#!/bin/bash

# Initialize and update all submodules
git submodule update --init --recursive

# Loop through each submodule with custom branch handling
# replace main with other branch if using dev branch on get-nwbfile-info package
git submodule foreach '
  if [ "$path" = "packages/get-nwbfile-info" ]; then
    git checkout main && git pull origin main
  else
    git checkout main && git pull origin main
  fi
'
