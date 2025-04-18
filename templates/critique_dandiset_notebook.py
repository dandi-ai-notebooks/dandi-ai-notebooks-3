import os
import json
import time
import requests
import argparse
from pathlib import Path
from typing import Dict, Any
from typing import List, Tuple

prompt_version = 1
model_for_cells = "google/gemini-2.0-flash-001"
model_for_summary = "anthropic/claude-3.7-sonnet"
verbose = False

def read_notebook_critic_cells_system_prompt() -> str:
    system_prompt_path = Path(__file__).parent / "notebook_critic_cells_system_prompt.txt"
    with open(system_prompt_path, "r") as f:
        system_prompt = f.read()
    return system_prompt

def run_completion(
    messages: List[Dict[str, Any]],
    *,
    model: str
) -> Tuple[str, List[Dict[str, Any]], int, int]:
    """Execute an AI completion request using the OpenRouter API

    This function manages a conversation with an AI model

    Args:
        messages: List of conversation messages, each being a dictionary with role and content.
        model: Name of the OpenRouter model to use for completion.

    Returns:
        tuple: Contains:
            - content (str): The final response content from the model
            - conversation_messages (List): Complete conversation history
            - total_prompt_tokens (int): Total tokens used in prompts
            - total_completion_tokens (int): Total tokens used in completions

    Raises:
        ValueError: If OPENROUTER_API_KEY environment variable is not set
        RuntimeError: If the OpenRouter API request fails

    Notes:

    The OPENROUTER_API_KEY environment variable must be set with a valid API key from OpenRouter.

    The messages is a list of dicts with the following structure:
    [
        {"role": "system", "content": "You are a helpful assistant... etc."},
        {"role": "user", "content": "I need help with... etc."},
        {"role": "assistant", "content": "I can help with that... etc."},
        {"role": "user", "content": "Yes, please... etc."},
        ...
    ]
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable not set")

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://neurosift.app",
        "Content-Type": "application/json"
    }

    conversation_messages = [m for m in messages]

    total_prompt_tokens = 0
    total_completion_tokens = 0

    while True:
        # Make API request
        payload = {
            "model": model,
            "messages": conversation_messages
        }
        if verbose:
            print(f"Using model: {payload['model']}")
            print(f"Num. messages in conversation: {len(conversation_messages)}")

        if verbose:
            print("Submitting completion request...")
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            raise RuntimeError(f"OpenRouter API request failed: {response.text}")

        if verbose:
            print("Processing response...")
        completion = response.json()
        prompt_tokens = completion["usage"]["prompt_tokens"]
        completion_tokens = completion["usage"]["completion_tokens"]

        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens

        message = completion["choices"][0]["message"]
        content: str = message.get("content", "")

        # Track assistant response
        current_response = {
            "role": "assistant",
            "content": content
        }
        conversation_messages.append(current_response)

        return content, conversation_messages, total_prompt_tokens, total_completion_tokens

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

def critique_notebook_cells(*, notebook_path: str):
    with open(notebook_path, "r") as f:
        notebook_content = f.read()
    notebook = json.loads(notebook_content)

    if not "cells" in notebook:
        raise Exception(f"Invalid notebook format. No cells found in the notebook.")

    total_prompt_tokens = 0
    total_completion_tokens = 0
    cells = notebook["cells"]

    if verbose:
        print(f"Critiquing notebook {notebook_path}")
    system_prompt = read_notebook_critic_cells_system_prompt()
    messages: List[Dict[str, Any]] = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]
    cell_critiques = []
    for i, cell in enumerate(cells):
        if verbose:
            print(f"Processing cell {i + 1}/{len(cells)}")
            print("==================")
        content = create_user_message_content_for_cell(cell)
        messages.append({"role": "user", "content": content})
        assistant_response, new_messagse, prompt_tokens, completion_tokens = (
            run_completion(messages=messages, model=model_for_cells)
        )
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens

        cell_critiques.append(assistant_response)
        if verbose:
            print(assistant_response)
            print("")

        messages = new_messagse
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens

    return cell_critiques, total_prompt_tokens, total_completion_tokens

def critique_dandiset_notebook(notebook_path: str):
    cell_critiques, prompt_tokens_for_cells, completion_tokens_for_cells = critique_notebook_cells(notebook_path=notebook_path)
    cell_critiques_text = ""
    for i, critique in enumerate(cell_critiques):
        cell_critiques_text += f"Cell {i + 1}\n==========\n\n{critique}\n\n"
    system_message = """
The user is going to provide a cell-by-cell critique of a Jupyter notebook.

The notebook’s purpose is to introduce a specific Dandiset from the DANDI Archive, demonstrate how to load and visualize data, and help readers begin further analysis.

Based on the cell critiques you are going to provide a critique of what needs to change in the notebook based on the reported issues.

Your response will then be used by a coding agent to make the adjustments.

Warning messages in the output cells should not be considered issues to fix in the notebook.

If there are no issues to fix in the notebook, please say so.
"""
    messages = [
        {
            "role": "system",
            "content": system_message,
        },
        {
            "role": "user",
            "content": cell_critiques_text,
        },
    ]
    assistant_response, _, prompt_tokens_for_summary, completion_tokens_for_summary = (
        run_completion(messages=messages, model=model_for_summary)
    )
    return assistant_response, prompt_tokens_for_cells, completion_tokens_for_cells, prompt_tokens_for_summary, completion_tokens_for_summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Critique a Jupyter notebook.")
    parser.add_argument(
        "notebook_path",
        type=str,
        help="Path to the Jupyter notebook file to critique.",
    )
    args = parser.parse_args()
    notebook_path = args.notebook_path
    if not os.path.exists(notebook_path):
        raise FileNotFoundError(f"Notebook file {notebook_path} does not exist.")
    if not notebook_path.endswith(".ipynb"):
        raise ValueError(f"File {notebook_path} is not a valid Jupyter notebook file.")
    if verbose:
        print(f"Critiquing notebook {notebook_path}")
    assistant_response, prompt_tokens_for_cells, completion_tokens_for_cells, prompt_tokens_for_summary, completion_token_for_summary = critique_dandiset_notebook(notebook_path)
    print(f'<prompt_tokens_for_cells>{prompt_tokens_for_cells}</prompt_tokens_for_cells>')
    print(f'<completion_tokens_for_Cells>{completion_tokens_for_cells}</completion_tokens_cor_cells>')
    print(f'<prompt_tokens_for_summary>{prompt_tokens_for_summary}</prompt_tokens_for_summary>')
    print(f'<completion_tokens_for_summary>{completion_token_for_summary}</completion_tokens_for_summary>')
    print("")
    print(assistant_response)
