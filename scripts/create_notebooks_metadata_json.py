#!/usr/bin/env python

import json
import os

def find_metadata_files():
    metadata_files = []
    dandisets_dir = 'dandisets'

    # Walk through dandisets directory
    for dandiset in os.listdir(dandisets_dir):
        dandiset_path = os.path.join(dandisets_dir, dandiset)
        if not os.path.isdir(dandiset_path) or dandiset.startswith('.'):
            continue

        # Walk through notebook runs
        for run in os.listdir(dandiset_path):
            run_path = os.path.join(dandiset_path, run)
            if not os.path.isdir(run_path) or run.startswith('.'):
                continue

            # Check for metadata.json
            metadata_path = os.path.join(run_path, 'metadata.json')
            if os.path.exists(metadata_path):
                metadata_files.append({
                    'path': metadata_path,
                    'subfolder': run
                })

    return metadata_files

def has_required_fields(metadata):
    required_fields = ['dandiset_id', 'model', 'prompt']
    return all(field in metadata for field in required_fields)

def create_notebooks_metadata():
    metadata_files = find_metadata_files()
    all_metadata = []

    # Read each metadata file
    for file_info in metadata_files:
        try:
            with open(file_info['path'], 'r') as f:
                metadata = json.load(f)
                if has_required_fields(metadata):
                    metadata['subfolder'] = file_info['subfolder']
                    all_metadata.append(metadata)
        except Exception as e:
            print(f"Error reading {file_info['path']}: {str(e)}")
            continue

    # Write combined metadata
    with open('notebooks_metadata.json', 'w') as f:
        json.dump(all_metadata, f, indent=2)

if __name__ == '__main__':
    create_notebooks_metadata()
