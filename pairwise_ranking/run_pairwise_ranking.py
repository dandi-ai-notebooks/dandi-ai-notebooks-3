import os
import json
import re
import time
import platform
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Tuple, TypedDict
from dataclasses import dataclass
from helpers.run_completion import run_completion
from html import escape as html_escape

# model_for_pairwise_ranking = "anthropic/claude-3.7-sonnet"
# model_for_pairwise_ranking = "google/gemini-2.0-flash-001"
model_for_pairwise_ranking = "google/gemini-2.5-pro-preview-03-25"
prompt_version = "1"

def find_notebooks(base_dir: str) -> List[Tuple[str, str, str]]:
    results = []

    prefixes = ['2025-04-28']

    # List dandiset directories
    for dandiset_id in os.listdir(base_dir):
        dandiset_path = os.path.join(base_dir, dandiset_id)
        if not os.path.isdir(dandiset_path):
            continue

        # List subdirectories within dandiset
        for subfolder in os.listdir(dandiset_path):
            starts_with_one_of_the_target_prefixes = any(
                subfolder.startswith(prefix) for prefix in prefixes
            )
            if not starts_with_one_of_the_target_prefixes:
                continue
            subfolder_path = os.path.join(dandiset_path, subfolder)
            if not os.path.isdir(subfolder_path):
                continue

            # Check for notebook
            notebook_path = os.path.join(subfolder_path, f"{dandiset_id}.ipynb")
            if os.path.isfile(notebook_path):
                results.append((dandiset_id, subfolder, notebook_path))

    return results

def read_template_prompt(name: str):
    template_path = (
        Path(__file__).parent / "templates" / name
    )
    with open(template_path, "r") as f:
        content = f.read()
    return content

def create_message_content_for_cell(cell: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Create user message content for a given cell."""
    content: List[Dict[str, Any]] = []
    if cell["cell_type"] == "markdown":
        markdown_source = cell["source"]
        content.append(
            {"type": "text", "text": "INPUT-MARKDOWN: " + "".join(markdown_source)}
        )
    elif cell["cell_type"] == "code":
        code_source = cell["source"]
        content.append({"type": "text", "text": "INPUT-CODE: " + "".join(code_source)})
        for x in cell["outputs"]:
            output_type = x["output_type"]
            if output_type == "stream":
                content.append(
                    {"type": "text", "text": "OUTPUT-TEXT: " + "\n".join(x["text"])}
                )
            elif output_type == "display_data" or output_type == "execute_result":
                if "image/png" in x["data"]:
                    png_base64 = x["data"]["image/png"]
                    image_data_url = f"data:image/png;base64,{png_base64}"
                    content.append({"type": "text", "text": "OUTPUT-IMAGE:"})
                    content.append(
                        {"type": "image_url", "image_url": {"url": image_data_url}}
                    )
                elif "text/plain" in x["data"]:
                    content.append(
                        {
                            "type": "text",
                            "text": "OUTPUT-TEXT: " + "".join(x["data"]["text/plain"]),
                        }
                    )
                elif "text/html" in x["data"]:
                    content.append(
                        {
                            "type": "text",
                            "text": "OUTPUT-TEXT: " + "".join(x["data"]["text/html"]),
                        }
                    )
                else:
                    print(
                        f"Warning: got output type {output_type} but no image/png data or text/plain or text/html"
                    )
            else:
                print(f"Warning: unsupported output type {output_type}")
    else:
        print(f'Warning: unsupported cell type {cell["cell_type"]}')
        content.append({"type": "text", "text": "Unsupported cell type"})
    return content

def do_notebook_comparison(notebook1_path: str, notebook2_path: str) -> Tuple[str, int, int]:
    with open(notebook1_path, "r") as f:
        notebook1_obj = json.load(f)
    with open(notebook2_path, "r") as f:
        notebook2_obj = json.load(f)
    system_prompt = read_template_prompt("rankings_system_message_1.txt")

    messages: List[Dict[str, Any]] = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]
    for notebook_num in range(1, 2 + 1):
        messages.append({
            "role": "user",
            "content": f"BEGIN NOTEBOOK {notebook_num} CONTENT",
        })
        notebook_obj = notebook1_obj if notebook_num == 1 else notebook2_obj
        for cell in notebook_obj["cells"]:
            if cell["cell_type"] not in ["code", "markdown"]:
                continue
            cell_content = create_message_content_for_cell(cell)
            messages.append(
                {
                    "role": "user",
                    "content": cell_content,
                }
            )
        messages.append({
            "role": "user",
            "content": f"END NOTEBOOK {notebook_num} CONTENT",
        })

    user_message_1 = read_template_prompt("rankings_user_message.txt")
    messages.append(
        {
            "role": "user",
            "content": user_message_1,
        }
    )

    assistant_response, new_messages, prompt_tokens, completion_tokens = (
        run_completion(messages=messages, model=model_for_pairwise_ranking)
    )
    messages = new_messages

    return assistant_response, prompt_tokens, completion_tokens

def parse_ranking_text(ranking_text: str) -> Tuple[str, int]:
    i1 = ranking_text.find("<thinking>")
    i2 = ranking_text.find("</thinking>")
    if i1 == -1 or i2 == -1:
        print(ranking_text)
        raise ValueError("Invalid ranking text: <thinking> tag not found")
    thinking = ranking_text[i1 + len("<thinking>"):i2].strip()
    i1 = ranking_text.find("<ranking>")
    i2 = ranking_text.find("</ranking>")
    if i1 == -1 or i2 == -1:
        print(ranking_text)
        raise ValueError("Invalid ranking text: <ranking> tag not found")
    ranking_str = ranking_text[i1 + len("<ranking>"):i2].strip()
    if ranking_str == '1':
        ranking = 1
    elif ranking_str == '2':
        ranking = 2
    else:
        print(ranking_text)
        raise ValueError("Invalid ranking text")
    return thinking, ranking

def main():
    dandiset_notebooks_base_dir = Path(__file__).parent.parent / "dandisets"
    rankings_base_dir = Path(__file__).parent / "dandisets"
    notebooks = find_notebooks(str(dandiset_notebooks_base_dir))
    print(f"Found {len(notebooks)} notebooks to process")

    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0

    # Process each dandiset
    for ii1, a1 in enumerate(notebooks):
        dandiset_id, subfolder1, notebook1_path = a1

        for ii2, a2 in enumerate(notebooks):
            if ii1 == ii2:
                continue
            dandiset_id2, subfolder2, notebook2_path = a2
            if dandiset_id != dandiset_id2:
                continue

            # Check if ranking already exist
            output_dir1 = rankings_base_dir / dandiset_id / subfolder1
            output_dir2 = output_dir1 / subfolder2
            output_file = output_dir2 / "ranking.json"
            if output_file.exists():
                with open(output_file, "r") as f:
                    existing_ranking = json.load(f)
                if existing_ranking.get("prompt_version") == prompt_version:
                    print(f"Ranking for {dandiset_id}/{subfolder1}/{subfolder2} already exist.")
                    continue
                print(f"Deleting existing ranking for {dandiset_id}/{subfolder1}/{subfolder2} to regenerate.")
                os.remove(output_file)

            ranking_text, prompt_tokens, completion_tokens = do_notebook_comparison(
                notebook1_path, notebook2_path
            )
            total_prompt_tokens += prompt_tokens
            total_completion_tokens += completion_tokens

            thinking, ranking = parse_ranking_text(ranking_text)

            print(thinking)
            print(f'Ranking for {dandiset_id}/{subfolder1}/{subfolder2}: {ranking}')

            # Create output directory if it doesn't exist
            os.makedirs(output_dir1, exist_ok=True)
            os.makedirs(output_dir2, exist_ok=True)
            with open(output_file, "w") as f:
                json.dump(
                    {
                        "prompt_version": prompt_version,
                        "ranking": ranking,
                        "thinking": thinking,
                        "metadata": {
                            "total_prompt_tokens": prompt_tokens,
                            "total_completion_tokens": completion_tokens,
                            "model": model_for_pairwise_ranking,
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "system_info": {"platform": platform.platform(), "hostname": platform.node()}
                        }
                    },
                    f,
                    indent=2
                )
            print(f"Ranking saved to {output_file}")
            print("")
            print(f'Prompt tokens: {prompt_tokens}')
            print(f'Completion tokens: {completion_tokens}')

            print(f"\nTotal prompt tokens: {total_prompt_tokens}")
            print(f"Total completion tokens: {total_completion_tokens}")

if __name__ == "__main__":
    main()
