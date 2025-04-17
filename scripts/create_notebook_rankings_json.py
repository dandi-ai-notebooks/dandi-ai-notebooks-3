#!/usr/bin/env python

import os
import json
from pathlib import Path

def main():
    # Get the path to the rankings directory
    rankings_dir = Path(__file__).parent.parent / "rankings" / "dandisets"
    output_path = Path(__file__).parent.parent / "notebook_rankings.json"

    # Initialize the combined rankings dictionary
    combined_rankings = {}

    # Walk through the rankings/dandisets directory
    for dandiset_dir in os.listdir(rankings_dir):
        rankings_file = rankings_dir / dandiset_dir / "rankings.json"
        if rankings_file.exists():
            print(f"Processing {dandiset_dir}")
            with open(rankings_file, "r") as f:
                rankings_data = json.load(f)
                combined_rankings[dandiset_dir] = rankings_data

    # Save the combined rankings
    with open(output_path, "w") as f:
        json.dump(combined_rankings, f, indent=2)

    print(f"Successfully saved combined rankings to {output_path}")

if __name__ == "__main__":
    main()
