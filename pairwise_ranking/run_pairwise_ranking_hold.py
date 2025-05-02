import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Tuple, TypedDict
from dataclasses import dataclass
from helpers.run_completion import run_completion
from html import escape as html_escape
import random

model_for_rankings = "anthropic/claude-3.5-sonnet"
# model_for_rankings = "google/gemini-2.5-pro-preview-03-25"
# model_for_rankings = "google/gemini-2.0-flash-001"
prompt_version = "1"

class XMLParsingError(Exception):
    """Custom exception for XML parsing errors."""
    pass

@dataclass
class RankingBlock:
    question_id: str
    thinking: str
    selection: int

    @classmethod
    def from_xml_element(cls, element: ET.Element) -> 'RankingBlock':
        """Parse a ranking block from an XML element."""
        if element.tag != 'ranking':
            raise ValueError(f"Expected 'ranking' element, got '{element.tag}'")

        question_id = ''
        thinking = ''
        selection = 0

        for child in element:
            if child.tag == 'question_id':
                question_id = child.text.strip() if child.text else ''
            elif child.tag == 'thinking':
                thinking = child.text.strip() if child.text else ''
            elif child.tag == 'selection':
                try:
                    selection = int(child.text.strip()) if child.text else 0
                except ValueError:
                    raise ValueError(f"Invalid selection value: {child.text}")

        if not question_id:
            raise ValueError("Missing question_id")
        if not thinking:
            raise ValueError("Missing thinking")

        return cls(question_id=question_id, thinking=thinking, selection=selection)

class RankingEntry(TypedDict):
    question_id: str
    selection: int
    thinking: str

def escape_xml_chars(xml_text: str) -> str:
    """
    Escape '<' and '>' everywhere *except* inside our whitelisted tags.
    """
    _ALLOWED_TAGS = [
        '<ranking>', '</ranking>',
        '<question_id>', '</question_id>',
        '<thinking>', '</thinking>',
        '<selection>', '</selection>'
    ]
    _PLACEHOLDER = '__TAG_{:02d}__'
    _PLACEHOLDER_RE = re.compile(r'__TAG_(\d{2})__')
    # 1 . swap each allowed tag for a unique placeholder
    for i, tag in enumerate(_ALLOWED_TAGS):
        xml_text = xml_text.replace(tag, _PLACEHOLDER.format(i))

    # 2 . escape everything that remains
    xml_text = html_escape(xml_text, quote=False)   # keeps & and quotes unchanged

    # 3 . put the real tags back
    def _restore(match: re.Match) -> str:
        return _ALLOWED_TAGS[int(match.group(1))]

    return _PLACEHOLDER_RE.sub(_restore, xml_text)

def parse_rankings_xml(xml_text: str, *, question_ids: List[str]) -> List[RankingBlock]:
    """Parse rankings from XML text into a list of RankingBlock objects.

    Args:
        xml_text: String containing XML ranking blocks

    Returns:
        List of parsed RankingBlock objects

    Raises:
        XMLParsingError: If XML is malformed or missing required elements
    """
    try:
        # Escape < and > characters not part of our tags before wrapping
        escaped_xml = escape_xml_chars(xml_text)
        # Wrap in root element for parsing multiple ranking blocks
        wrapped_xml = f"<rankings>{escaped_xml}</rankings>"
        root = ET.fromstring(wrapped_xml)

        rankings: List[RankingBlock] = []
        for ranking_elem in root.findall('ranking'):
            try:
                ranking_block = RankingBlock.from_xml_element(ranking_elem)
                rankings.append(ranking_block)
            except ValueError as e:
                raise XMLParsingError(f"Failed to parse ranking block: {str(e)}")

        # check that the number of rankings equals the number of questions
        if len(rankings) != len(question_ids):
            raise XMLParsingError(f"Number of rankings ({len(rankings)}) does not match number of questions ({len(question_ids)})")
        # check that the question IDs match
        for i, ranking in enumerate(rankings):
            q = ranking.question_id
            if not q in question_ids:
                raise XMLParsingError(f"Question ID {q} not found in expected question IDs")

        return rankings

    except ET.ParseError as e:
        raise XMLParsingError(f"Invalid XML format: {str(e)}")

def read_template_prompt(name: str):
    template_path = (
        Path(__file__).parent / "templates" / name
    )
    with open(template_path, "r") as f:
        content = f.read()
    return content

def get_question_ids() -> List[str]:
    p = read_template_prompt("rankings_user_message_rubric_with_questions.txt")
    # each question has a line of the form
    # question_id: <question_id>
    ret = []
    for line in p.splitlines():
        if line.startswith("question_id:"):
            _, question_id = line.split(":", 1)
            ret.append(question_id.strip())
    return ret

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

def get_rankings_for_notebooks(notebook1_path: str, notebook2_path: str) -> Tuple[str, int, int]:
    with open(notebook1_path, "r") as f:
        notebook1_obj = json.load(f)
    with open(notebook2_path, "r") as f:
        notebook2_obj = json.load(f)

    total_prompt_tokens = 0
    total_completion_tokens = 0
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

    user_message_1 = read_template_prompt("rankings_user_message_rubric_with_questions.txt")
    messages.append(
        {
            "role": "user",
            "content": user_message_1,
        }
    )
    assistant_rankings, new_messages, prompt_tokens, completion_tokens = (
        run_completion(messages=messages, model=model_for_rankings)
    )
    total_prompt_tokens += prompt_tokens
    total_completion_tokens += completion_tokens
    messages = new_messages

    return assistant_rankings, total_prompt_tokens, total_completion_tokens

def find_notebooks_for_dandiset(dandiset_id: str, subfolder_prefixes: List[str]):
    # find notebooks of the form
    # dandisets/<dandiset_id>/<subfolder>/<dandiset_id>.ipynb
    ret: List[str] = []
    for subfolder in Path(f"dandisets/{dandiset_id}").iterdir():
        starts_with_prefix = False
        for prefix in subfolder_prefixes:
            if subfolder.name.startswith(prefix):
                starts_with_prefix = True
                break
        if not starts_with_prefix:
            continue
        if subfolder.is_dir():
            notebook_path = subfolder / f"{dandiset_id}.ipynb"
            if notebook_path.exists():
                ret.append(subfolder.name)
    if len(ret) == 0:
        raise Exception(f"No notebooks found for dandiset {dandiset_id}")
    return ret


def get_next_pair_to_compare(subfolder_names: List[str], comparisons):
    comparison_counts = [
        len([
            c for c in comparisons if c[0] == subfolder_name or c[1] == subfolder_name
        ])
        for subfolder_name in subfolder_names
    ]
    num_wins = [
        len([
            c for c in comparisons if (c[0] == subfolder_name and c[2] == 1) or (c[1] == subfolder_name and c[2] == 2)
        ])
        for subfolder_name in subfolder_names
    ]
    active_subfolders = [
        True for _ in range(len(subfolder_names))
    ]
    comparison_count_for_second_least_compared = sorted(comparison_counts)[1]
    for i in range(len(subfolder_names)):
        if comparison_counts[i] > comparison_count_for_second_least_compared:
            active_subfolders[i] = False
    # For all candidate pairs, make a score
    all_scores = []
    for i, subfolder1 in enumerate(subfolder_names):
        if not active_subfolders[i]:
            continue
        for j, subfolder2 in enumerate(subfolder_names):
            if i == j or not active_subfolders[j]:
                continue
            already_compared = False
            for c in comparisons:
                if (c[0] == subfolder1 and c[1] == subfolder2) or (c[0] == subfolder2 and c[1] == subfolder1):
                    already_compared = True
                    break
            if already_compared:
                score = -4
            else:
                score = 0
            score -= abs(num_wins[i] - num_wins[j])
            all_scores.append([subfolder1, subfolder2, score])
    # get all comparisons with the highest score
    highest_score = max([s[2] for s in all_scores])
    best_comparisons = [
        s for s in all_scores if s[2] == highest_score
    ]
    # randomly choose one of the best comparisons
    best_comparison = random.choice(best_comparisons)
    subfolder1 = best_comparison[0]
    subfolder2 = best_comparison[1]
    return subfolder1, subfolder2

def rank_subfolders(subfolders: List[str], comparisons: List[List], k: float = 32.0) -> Tuple[List[str], Dict[str, Dict[str, int]]]:
    # Initialize ratings
    ratings: Dict[str, float] = {sf: 1500.0 for sf in subfolders}

    def expected_score(rating_a, rating_b):
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

    # Process each comparison
    for aa in comparisons:
        sf1 = aa[0]
        sf2 = aa[1]
        result = aa[2]
        if result == 0:
            continue  # skip ties or unknowns

        r1, r2 = ratings[sf1], ratings[sf2]
        e1, e2 = expected_score(r1, r2), expected_score(r2, r1)

        if result == 1:
            s1, s2 = 1, 0
        elif result == 2:
            s1, s2 = 0, 1
        else:
            continue  # invalid result

        ratings[sf1] += k * (s1 - e1)
        ratings[sf2] += k * (s2 - e2)

    # Initialize stats for each subfolder
    stats = {sf: {"wins": 0, "losses": 0, "ties": 0} for sf in subfolders}
    for c in comparisons:
        if c[2] == 1:
            stats[c[0]]["wins"] += 1
            stats[c[1]]["losses"] += 1
        elif c[2] == 2:
            stats[c[1]]["wins"] += 1
            stats[c[0]]["losses"] += 1
        elif c[2] == 0:  # tie
            stats[c[0]]["ties"] += 1
            stats[c[1]]["ties"] += 1

    # Return sorted subfolders and stats
    return sorted(subfolders, key=lambda sf: ratings[sf], reverse=True), stats

def main():
    dandiset_id = "000690"
    subfolder_names = find_notebooks_for_dandiset(dandiset_id=dandiset_id, subfolder_prefixes=["2025-04-28-"])
    num_comparisons_to_do = 10
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    thisdir = os.path.dirname(os.path.abspath(__file__))
    comparisons_fname = thisdir + "/comparisons/" + dandiset_id + "/" + "comparisons.json"
    if os.path.exists(comparisons_fname):
        with open(comparisons_fname, 'r') as f:
            comparisons = json.load(f)
    else:
        comparisons = []
    for j in range(num_comparisons_to_do):
        subfolder1, subfolder2 = get_next_pair_to_compare(subfolder_names, comparisons)
        print(f'Comparing {subfolder1} and {subfolder2}')
        notebook1_path = f"dandisets/{dandiset_id}/{subfolder1}/{dandiset_id}.ipynb"
        notebook2_path = f"dandisets/{dandiset_id}/{subfolder2}/{dandiset_id}.ipynb"

        rankings_text, prompt_tokens, completion_tokens = get_rankings_for_notebooks(notebook1_path, notebook2_path)
        print("======")
        print(rankings_text)
        print("======")
        print("")
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens

        # Parse rankings text into structured format
        try:
            rankings = parse_rankings_xml(rankings_text, question_ids=get_question_ids())
        except XMLParsingError as e:
            print(f"Error parsing rankings: {str(e)}")
            print(rankings_text)
            raise Exception(f"Failed to parse rankings: {str(e)}")

        ranking_entries: List[RankingEntry] = []
        for ranking in rankings:
            ranking_entries.append({
                "question_id": ranking.question_id,
                "thinking": ranking.thinking,
                "selection": ranking.selection
            })

        print("Parsed rankings:")
        for entry in ranking_entries:
            print(f"{entry['question_id']}: {entry['selection']}")
            print(f"Thinking: {entry['thinking']}\n")
        print("")

        overall_helpfulness_entry = next((
            entry for entry in ranking_entries if entry["question_id"] == "overall-helpfulness"
        ), None)
        if overall_helpfulness_entry is None:
            raise Exception("No overall-helpfulness entry found in rankings")
        comparison = [
            subfolder1,
            subfolder2,
            overall_helpfulness_entry["selection"],
            ranking_entries,
            {
                "model": model_for_rankings,
                "prompt_version": prompt_version,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }
        ]
        comparisons.append(comparison)

        # ensure directory exists
        os.makedirs(os.path.dirname(comparisons_fname), exist_ok=True)
        with open(comparisons_fname, 'w') as f:
            json.dump(comparisons, f)

        print(f'Compared {subfolder1} and {subfolder2}')
        print(f'Better for overall helpfulness: {overall_helpfulness_entry["selection"]}')

        print("")
        print("Ranked subfolders:")
        ranked_subfolders, stats = rank_subfolders(subfolder_names, comparisons)
        for i, subfolder in enumerate(ranked_subfolders):
            sf_stats = stats[subfolder]
            print(f"{i + 1}. {subfolder} (wins: {sf_stats['wins']}, losses: {sf_stats['losses']}, ties: {sf_stats['ties']})")

        print(f'Prompt tokens: {prompt_tokens}')
        print(f'Completion tokens: {completion_tokens}')

    print(f"\nTotal prompt tokens: {total_prompt_tokens}")
    print(f"Total completion tokens: {total_completion_tokens}")

if __name__ == "__main__":
    main()
