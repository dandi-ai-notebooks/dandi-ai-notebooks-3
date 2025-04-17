import os
import json
import time
import platform
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple, TypedDict
from helpers.run_completion import run_completion

class RankingEntry(TypedDict):
    notebook_id: str
    rank: int
    thinking: str

model_for_rankings = "anthropic/claude-3.7-sonnet"
prompt_version = "1"

def find_critiqued_notebooks(base_dir: str, *, prefix: str) -> List[Tuple[str, str]]:
    """Find notebooks that have been critiqued."""
    notebook_paths = []

    # List dandiset directories
    for dandiset_id in os.listdir(base_dir):
        dandiset_path = os.path.join(base_dir, dandiset_id)
        if not os.path.isdir(dandiset_path):
            continue

        # List subdirectories within dandiset
        for subfolder in os.listdir(dandiset_path):
            subfolder_path = os.path.join(dandiset_path, subfolder)
            if not os.path.isdir(subfolder_path):
                continue

            dirname = subfolder_path.split("/")[-1]
            if not dirname.startswith(prefix):
                continue

            # Check for summary critique
            summary_critique_path = os.path.join(subfolder_path, "summary_critique.txt")
            if os.path.isfile(summary_critique_path):
                notebook_paths.append((dandiset_id, summary_critique_path))

    return notebook_paths

def read_rankings_system_prompt() -> str:
    """Read and process the rankings system prompt template."""
    template_path = (
        Path(__file__).parent / "templates" / "rankings_system_prompt.txt"
    )
    with open(template_path, "r") as f:
        content = f.read()
    return content

def get_rankings_for_dandiset(critiques: List[Tuple[str, str]]) -> Tuple[str, int, int]:
    """Get rankings for a dandiset based on critiques."""
    system_prompt = read_rankings_system_prompt()

    # Create ID mapping for de-identification
    # We mask real IDs (e.g. 2025-04-16-claude-3.7...) with generic ones (NB_01, NB_02...)
    # to prevent any potential bias in the ranking based on model names
    id_mapping: Dict[str, str] = {}
    reverse_mapping: Dict[str, str] = {}
    for i, (notebook_id, _) in enumerate(critiques, 1):
        masked_id = f"NB_{i:02d}"
        id_mapping[notebook_id] = masked_id
        reverse_mapping[masked_id] = notebook_id
    print("Masking IDs for critiques:")
    for original_id, masked_id in id_mapping.items():
        print(f"{original_id} -> {masked_id}")

    # Format critiques as required by the template
    # Use masked IDs in the message to the model
    formatted_critiques = ""
    for notebook_id, critique_path in critiques:
        with open(critique_path, "r") as f:
            critique_content = f.read()
        # Use masked ID in place of actual notebook ID
        masked_id = id_mapping[notebook_id]
        formatted_critiques += f"""
<notebook>
<notebook_id>{masked_id}</notebook_id>
<critique>
{critique_content}
</critique>
</notebook>
"""

    messages: List[Dict[str, Any]] = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": [{"type": "text", "text": formatted_critiques}]
        }
    ]

    assistant_response, _, prompt_tokens, completion_tokens = (
        run_completion(messages=messages, model=model_for_rankings)
    )

    # Unmask the IDs in the response before returning
    # Replace all masked IDs (NB_01, NB_02...) with their original notebook IDs
    unmasked_response = assistant_response
    for masked_id, original_id in reverse_mapping.items():
        unmasked_response = unmasked_response.replace(masked_id, original_id)

    return unmasked_response, prompt_tokens, completion_tokens

def main():
    critiques_base_dir = Path(__file__).parent.parent / "critiques" / "dandisets"
    rankings_base_dir = Path(__file__).parent / "dandisets"
    notebooks = find_critiqued_notebooks(str(critiques_base_dir), prefix="2025-04-16")
    print(f"Found {len(notebooks)} critiqued notebooks to process")

    # Group notebooks by dandiset
    dandiset_notebooks: Dict[str, List[Tuple[str, str]]] = {}
    for dandiset_id, critique_path in notebooks:
        if dandiset_id not in dandiset_notebooks:
            dandiset_notebooks[dandiset_id] = []
        notebook_id = critique_path.split("/")[-2]  # Get the notebook ID from the path
        dandiset_notebooks[dandiset_id].append((notebook_id, critique_path))

    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0

    # Process each dandiset
    for dandiset_id, critiques in dandiset_notebooks.items():
        print(f"\nProcessing rankings for dandiset {dandiset_id}")

        # Check if rankings already exist
        output_dir = rankings_base_dir / dandiset_id
        output_file = output_dir / "rankings.json"
        if output_file.exists():
            with open(output_file, "r") as f:
                existing_rankings = json.load(f)
            if existing_rankings.get("prompt_version") == prompt_version:
                print("Rankings already exist, skipping...")
                continue

        rankings_text, prompt_tokens, completion_tokens = get_rankings_for_dandiset(critiques)
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens
        # Parse rankings text into structured format
        rankings_entries: List[RankingEntry] = []
        notebook_matches = re.finditer(
            r'<notebook>\s*'
            r'<thinking>(.*?)</thinking>\s*'
            r'<notebook_id>(.*?)</notebook_id>\s*'
            r'<rank>(\d+)</rank>\s*'
            r'</notebook>',
            rankings_text,
            re.DOTALL
        )

        for match in notebook_matches:
            thinking = match.group(1).strip()
            notebook_id = match.group(2).strip()
            rank = int(match.group(3))
            rankings_entries.append({
                "notebook_id": notebook_id,
                "rank": rank,
                "thinking": thinking
            })

        # Sort by rank
        rankings_entries.sort(key=lambda x: x["rank"])

        print("Parsed rankings:")
        for entry in rankings_entries:
            print(f"Rank {entry['rank']}: {entry['notebook_id']}")
            print(f"Thinking: {entry['thinking']}\n")

        # Create output directory if needed
        os.makedirs(output_dir, exist_ok=True)

        # Generate human-readable rankings text
        human_readable = ""
        for entry in rankings_entries:
            human_readable += f"Rank {entry['rank']}: {entry['notebook_id']}\n"
            human_readable += f"{entry['thinking']}\n\n"

        # Save rankings to both JSON and text files
        result = {
            "prompt_version": prompt_version,
            "rankings": rankings_entries,
            "rankings_text": rankings_text,  # Store raw text for troubleshooting
            "metadata": {
                "total_prompt_tokens": prompt_tokens,
                "total_completion_tokens": completion_tokens,
                "model": model_for_rankings,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "system_info": {"platform": platform.platform(), "hostname": platform.node()}
            }
        }

        print(f"Writing rankings to {output_file}")
        # Save JSON format
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)

        # Save human-readable format
        output_text_file = output_dir / "rankings.txt"
        with open(output_text_file, "w") as f:
            f.write(human_readable)

    print(f"\nTotal prompt tokens: {total_prompt_tokens}")
    print(f"Total completion tokens: {total_completion_tokens}")

if __name__ == "__main__":
    main()
