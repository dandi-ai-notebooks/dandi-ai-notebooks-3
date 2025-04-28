#!/usr/bin/env python

import os
import json
from pathlib import Path

def main():
    # Get the path to the gradings directory
    gradings_dir = Path(__file__).parent.parent / "gradings2" / "dandisets"
    output_path = Path(__file__).parent.parent / "notebook_gradings.json"

    # Initialize the combined gradings list
    combined_gradings = []

    prefixes = ['2025-04-28']

    # Walk through the gradings/dandisets directory
    for dandiset_dir in os.listdir(gradings_dir):
        dandiset_path = gradings_dir / dandiset_dir
        if not dandiset_path.is_dir():
            continue

        # Process each subfolder within the dandiset directory
        for subfolder in os.listdir(dandiset_path):
            starts_with_one_of_the_target_prefixes = any(
                subfolder.startswith(prefix) for prefix in prefixes
            )
            if not starts_with_one_of_the_target_prefixes:
                continue

            subfolder_path = dandiset_path / subfolder
            if not subfolder_path.is_dir():
                continue

            grades_file = subfolder_path / "grades.json"
            if grades_file.exists():
                print(f"Processing {dandiset_dir}/{subfolder}")
                with open(grades_file, "r") as f:
                    grades_data = json.load(f)
                    entry = {
                        "dandiset_id": dandiset_dir,
                        "subfolder": subfolder,
                        "gradings": grades_data
                    }
                    combined_gradings.append(entry)

    # Save the combined gradings
    with open(output_path, "w") as f:
        json.dump(combined_gradings, f, indent=2)

    print(f"Successfully saved combined gradings to {output_path}")

if __name__ == "__main__":
    main()
