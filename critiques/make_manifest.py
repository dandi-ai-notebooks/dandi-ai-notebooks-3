import os
import json
from pathlib import Path

def find_all_files(base_dir: str):
    """Recursively find all files in the base directory."""
    result = []
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file == "manifest.json":  # Skip the manifest file itself
                continue
            # Get path relative to base_dir (critiques directory)
            abs_path = os.path.join(root, file)
            rel_path = os.path.relpath(abs_path, base_dir)
            result.append(rel_path)
    return sorted(result)  # Sort for consistent ordering

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    manifest_path = os.path.join(base_dir, 'manifest.json')

    print(f"Scanning for files in {base_dir}")
    files = find_all_files(base_dir)

    manifest = {
        "files": files,
        "file_count": len(files)
    }

    print(f"Writing manifest with {len(files)} files to {manifest_path}")
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

if __name__ == "__main__":
    main()
