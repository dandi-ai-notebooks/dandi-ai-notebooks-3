import os
import json
import time
import platform
import requests
from pathlib import Path
from typing import Dict, Any
from typing import List, Tuple
from helpers.run_completion import run_completion


prompt_version = "1"
model_for_cells = "google/gemini-2.0-flash-001"
model_for_summary = "anthropic/claude-3.7-sonnet"


def find_notebooks(base_dir: str, *, prefixes: List[str]) -> List[Tuple[str, str]]:
    """Find notebooks matching the pattern dandisets/<DANDISET_ID>/subfolder/<DANDISET_ID>.ipynb."""
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
            # check if it starts with any of the prefixes
            if not any(dirname.startswith(prefix) for prefix in prefixes):
                continue

            # Check for matching notebook
            notebook_name = f"{dandiset_id}.ipynb"
            notebook_path = os.path.join(subfolder_path, notebook_name)
            if os.path.isfile(notebook_path):
                notebook_paths.append((dandiset_id, notebook_path))

    return notebook_paths


def read_notebook_critic_cells_system_prompt() -> str:
    """Read and process the system prompt template."""
    template_path = (
        Path(__file__).parent / "templates" / "notebook_critic_cells_system_prompt.txt"
    )
    with open(template_path, "r") as f:
        content = f.read()
    return content


def read_notebook_critic_summary_system_prompt() -> str:
    """Read and process the summary system prompt template."""
    template_path = (
        Path(__file__).parent
        / "templates"
        / "notebook_critic_summary_system_prompt.txt"
    )
    with open(template_path, "r") as f:
        content = f.read()
    return content


def create_user_message_content_for_cell(cell: Dict[str, Any]) -> List[Dict[str, Any]]:
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


def critique_notebook_cells(*, notebook_path_or_url: str):
    # If it's a notebook in a GitHub repo then translate the notebook URL to raw URL
    if notebook_path_or_url.startswith("https://github.com/"):
        notebook_path_or_url = notebook_path_or_url.replace(
            "github.com", "raw.githubusercontent.com"
        ).replace("/blob/", "/")

    # If notebook_path_or_url is a URL, download the notebook and read it as JSON
    # otherwise, read the file directly
    if notebook_path_or_url.startswith("http://") or notebook_path_or_url.startswith(
        "https://"
    ):
        response = requests.get(notebook_path_or_url)
        if response.status_code != 200:
            raise Exception(f"Failed to download notebook from {notebook_path_or_url}")
        notebook_content = response.content.decode("utf-8")
        notebook = json.loads(notebook_content)
    else:
        with open(notebook_path_or_url, "r") as f:
            notebook_content = f.read()
        notebook = json.loads(notebook_content)

    if not "cells" in notebook:
        raise Exception(f"Invalid notebook format. No cells found in the notebook.")

    total_prompt_tokens = 0
    total_completion_tokens = 0
    cells = notebook["cells"]

    result = {
        "notebook": notebook_path_or_url,
        "dandiset_id": notebook_path_or_url.split("/")[-3],
        "subfolder": notebook_path_or_url.split("/")[-2],
        "prompt_version": prompt_version,
        "cell_critiques": [],
        "metadata": {},
    }

    print(f"Critiquing notebook {notebook_path_or_url}")
    timer = time.time()
    system_prompt = read_notebook_critic_cells_system_prompt()
    messages: List[Dict[str, Any]] = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]
    for i, cell in enumerate(cells):
        print(f"Processing cell {i + 1}/{len(cells)}")
        print("==================")
        content = create_user_message_content_for_cell(cell)
        messages.append({"role": "user", "content": content})
        assistant_response, new_messagse, prompt_tokens, completion_tokens = (
            run_completion(messages=messages, model=model_for_cells)
        )

        result["cell_critiques"].append(assistant_response)
        print(assistant_response)
        print("")

        messages = new_messagse
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens
    elapsed_sec = time.time() - timer

    result["metadata"] = {
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "model_for_cells": model_for_cells,
        "elapsed_time_seconds": elapsed_sec,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "system_info": {"platform": platform.platform(), "hostname": platform.node()},
    }

    return result, total_prompt_tokens, total_completion_tokens


def get_summary_critique(cells_critique_text: str):
    """Get summary critique for the notebook."""
    system_prompt = read_notebook_critic_summary_system_prompt()
    user_content = [
        {
            "type": "text",
            "text": "Please summarize the following cell critiques based on your instructions."
        },
        {
            "type": "text",
            "text": cells_critique_text
        }

    ]
    messages: List[Dict[str, Any]] = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {"role": "user", "content": user_content},
    ]

    assistant_response, _, prompt_tokens, completion_tokens = (
        run_completion(messages=messages, model=model_for_summary)
    )

    return assistant_response, prompt_tokens, completion_tokens


def main():
    dandisets_base_dir = Path(__file__).parent.parent / "dandisets"
    notebooks = find_notebooks(str(dandisets_base_dir), prefixes=["2025-04-15", "2025-04-16", "2025-04-17", "2025-04-18"])
    print(f"Found {len(notebooks)} notebooks to process")

    total_cells_prompt_tokens = 0
    total_cells_completion_tokens = 0
    total_summary_prompt_tokens = 0
    total_summary_completion_tokens = 0

    # Do the cell critiques
    for i, (dandiset_id, abs_notebook_path) in enumerate(notebooks, 1):
        print(f"\nProcessing notebook {i}/{len(notebooks)}")
        print(f"Dandiset: {dandiset_id}")
        print(f"Path: {abs_notebook_path}")

        # notebook_path is relative notebook path
        notebook_path = Path(abs_notebook_path).relative_to(dandisets_base_dir)
        output_dir_path = (Path(__file__).parent / "dandisets" / notebook_path).parent

        cells_critique_json_path = output_dir_path / "cells_critique.json"
        cells_critique_text_path = output_dir_path / "cells_critique.txt"
        summary_critique_text_path = output_dir_path / "summary_critique.txt"
        if os.path.exists(cells_critique_json_path):
            with open(cells_critique_json_path, "r") as f:
                critiques = json.load(f)
            if critiques["prompt_version"] == prompt_version:
                print("Notebook already critiqued, skipping...")
                continue

        # remove the file
        if os.path.exists(cells_critique_json_path):
            print(f"Removing existing critique file: {cells_critique_json_path}")
            os.remove(cells_critique_json_path)
        if os.path.exists(cells_critique_text_path):
            print(f"Removing existing critique file: {cells_critique_text_path}")
            os.remove(cells_critique_text_path)
        if os.path.exists(summary_critique_text_path):
            print(f"Removing existing critique file: {summary_critique_text_path}")

        new_critique, prompt_tokens, completion_tokens = critique_notebook_cells(
            notebook_path_or_url=str(abs_notebook_path)
        )
        total_cells_prompt_tokens += prompt_tokens
        total_cells_completion_tokens += completion_tokens

        cells_critique_text = ""
        for i, cell in enumerate(new_critique["cell_critiques"]):
            cells_critique_text += f"Cell {i + 1}\n==========\n\n"
            cells_critique_text += cell + "\n\n"

        summary_critique_text, prompt_tokens, completion_tokens = get_summary_critique(
            cells_critique_text
        )
        total_summary_prompt_tokens += prompt_tokens
        total_summary_completion_tokens += completion_tokens
        print("Summary critique:")
        print(summary_critique_text)
        print("")

        # Create output directory it it doesn't exist
        os.makedirs(cells_critique_json_path.parent, exist_ok=True)
        print(f"Writing cells critique to {cells_critique_json_path}")
        with open(cells_critique_json_path, "w") as f:
            json.dump(new_critique, f, indent=2)
        print(f"Writing cells critique text to {cells_critique_text_path}")
        with open(cells_critique_text_path, "w") as f:
            f.write(cells_critique_text)
        print(f"Writing summary critique text to {summary_critique_text_path}")
        with open(summary_critique_text_path, "w") as f:
            f.write(summary_critique_text)

        print(f"Total cells prompt tokens: {total_cells_prompt_tokens}")
        print(f"Total cells completion tokens: {total_cells_completion_tokens}")
        print(f"Total summary prompt tokens: {total_summary_prompt_tokens}")
        print(f"Total summary completion tokens: {total_summary_completion_tokens}")


if __name__ == "__main__":
    main()
