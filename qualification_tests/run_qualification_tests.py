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

model_for_qualification_tests = "anthropic/claude-3.7-sonnet"
prompt_version = "5"

class XMLParsingError(Exception):
    """Custom exception for XML parsing errors."""
    pass

@dataclass
class GradeBlock:
    question_id: str
    thinking: str
    passing: bool

    @classmethod
    def from_xml_element(cls, element: ET.Element) -> 'GradeBlock':
        """Parse a grade block from an XML element."""
        if element.tag != 'grade':
            raise ValueError(f"Expected 'grade' element, got '{element.tag}'")

        question_id = ''
        thinking = ''
        grade_str = ""

        for child in element:
            if child.tag == 'question_id':
                question_id = child.text.strip() if child.text else ''
            elif child.tag == 'thinking':
                thinking = child.text.strip() if child.text else ''
            elif child.tag == 'grade':
                grade_str = child.text.strip().upper() if child.text else ''

        if not question_id:
            raise ValueError("Missing question_id")
        if not thinking:
            raise ValueError("Missing thinking")

        return cls(question_id=question_id, thinking=thinking, passing=(grade_str == "PASS"))

class GradeEntry(TypedDict):
    question_id: str
    passing: bool
    thinking: str

def escape_xml_chars(xml_text: str) -> str:
    """
    Escape '<' and '>' everywhere *except* inside our whitelisted tags.
    """
    _ALLOWED_TAGS = [
        '<grade>', '</grade>',
        '<question_id>', '</question_id>',
        '<thinking>', '</thinking>',
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

def parse_grades_xml(xml_text: str, *, question_ids: List[str]) -> List[GradeBlock]:
    """Parse grades from XML text into a list of GradeBlock objects.

    Args:
        xml_text: String containing XML grade blocks

    Returns:
        List of parsed GradeBlock objects

    Raises:
        XMLParsingError: If XML is malformed or missing required elements
    """
    try:
        # Escape < and > characters not part of our tags before wrapping
        escaped_xml = escape_xml_chars(xml_text)
        # Wrap in root element for parsing multiple grade blocks
        wrapped_xml = f"<grades>{escaped_xml}</grades>"
        root = ET.fromstring(wrapped_xml)

        grades: List[GradeBlock] = []
        for grade_elem in root.findall('grade'):
            try:
                grade_block = GradeBlock.from_xml_element(grade_elem)
                grades.append(grade_block)
            except ValueError as e:
                raise XMLParsingError(f"Failed to parse grade block: {str(e)}")

        # check that the number of grades equals the number of questions
        if len(grades) != len(question_ids):
            raise XMLParsingError(f"Number of grades ({len(grades)}) does not match number of questions ({len(question_ids)})")
        # check that the question IDs match
        for i, grade in enumerate(grades):
            q = grade.question_id
            if not q in question_ids:
                raise XMLParsingError(f"Question ID {q} not found in expected question IDs")

        return grades

    except ET.ParseError as e:
        raise XMLParsingError(f"Invalid XML format: {str(e)}")

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

def get_question_ids() -> List[str]:
    p = read_template_prompt("qualification_tests_user_message_rubric_with_questions.txt")
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

def get_qualification_tests_for_notebook(notebook_obj: dict) -> Tuple[str, str, int, int]:
    total_prompt_tokens = 0
    total_completion_tokens = 0
    system_prompt = read_template_prompt("qualification_tests_system_message_1.txt")

    messages: List[Dict[str, Any]] = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]
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

    user_message_1 = read_template_prompt("qualification_tests_user_message_1.txt")
    messages.append(
        {
            "role": "user",
            "content": user_message_1,
        }
    )

    image_descriptions, new_messages, prompt_tokens, completion_tokens = (
        run_completion(messages=messages, model=model_for_qualification_tests)
    )
    total_prompt_tokens += prompt_tokens
    total_completion_tokens += completion_tokens
    messages = new_messages # very important to update messages with the new messages from the model

    user_message_2 = read_template_prompt("qualification_tests_user_message_rubric_with_questions.txt")
    messages.append(
        {
            "role": "user",
            "content": user_message_2,
        }
    )
    assistant_qualification_tests, new_messages, prompt_tokens, completion_tokens = (
        run_completion(messages=messages, model=model_for_qualification_tests)
    )
    total_prompt_tokens += prompt_tokens
    total_completion_tokens += completion_tokens
    messages = new_messages

    return assistant_qualification_tests, image_descriptions, total_prompt_tokens, total_completion_tokens

def main():
    dandiset_notebooks_base_dir = Path(__file__).parent.parent / "dandisets"
    qualification_tests_base_dir = Path(__file__).parent / "dandisets"
    notebooks = find_notebooks(str(dandiset_notebooks_base_dir))
    print(f"Found {len(notebooks)} notebooks to process")

    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0

    # Process each dandiset
    for ii, a in enumerate(notebooks):
        dandiset_id, subfolder, notebook_path = a
        print(f"\n[{ii + 1}/{len(notebooks)}] Processing {dandiset_id}/{subfolder}")

        # Check if qualification_tests already exist
        output_dir = qualification_tests_base_dir / dandiset_id / subfolder
        output_file = output_dir / "grades.json"
        if output_file.exists():
            with open(output_file, "r") as f:
                existing_grades = json.load(f)
            if existing_grades.get("prompt_version") == prompt_version:
                print(f"Grades for {dandiset_id}/{subfolder} already exist.")
                continue
            print(f"Deleting existing grades for {dandiset_id}/{subfolder} to regenerate.")
            os.remove(output_file)

        with open(notebook_path, "r") as f:
            notebook_obj = json.load(f)

        qualification_tests_text, image_descriptions, prompt_tokens, completion_tokens = get_qualification_tests_for_notebook(notebook_obj)
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens

        # Parse rankings text into structured format
        try:
            grades = parse_grades_xml(qualification_tests_text, question_ids=get_question_ids())
        except XMLParsingError as e:
            print(f"Error parsing grades: {str(e)}")
            print(qualification_tests_text)
            raise Exception(f"Failed to parse grades: {str(e)}")

        qualification_tests_entries: List[GradeEntry] = []
        for grade in grades:
            qualification_tests_entries.append({
                "question_id": grade.question_id,
                "thinking": grade.thinking,
                "passing": grade.passing
            })

        print("Image descriptions:")
        print(image_descriptions)
        print("")

        print("Parsed grades:")
        for entry in qualification_tests_entries:
            grade_str = "PASS" if entry["passing"] else "FAIL"
            print(f"{entry['question_id']}: {grade_str}")
            print(f"Thinking: {entry['thinking']}\n")
        print("")

        print(f'Prompt tokens: {prompt_tokens}')
        print(f'Completion tokens: {completion_tokens}')

        # Create output directory if needed
        os.makedirs(output_dir, exist_ok=True)

        # Save rankings to both JSON and text files
        result = {
            "prompt_version": prompt_version,
            "grades": [
                {
                    "question_id": entry["question_id"],
                    "passing": entry["passing"],
                    "thinking": entry["thinking"]
                }
                for entry in qualification_tests_entries
            ],
            "image_descriptions": image_descriptions,
            "metadata": {
                "total_prompt_tokens": prompt_tokens,
                "total_completion_tokens": completion_tokens,
                "model": model_for_qualification_tests,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "system_info": {"platform": platform.platform(), "hostname": platform.node()}
            }
        }

        print(f"Writing qualification tests to {output_file}")
        # Save JSON format
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)

    print(f"\nTotal prompt tokens: {total_prompt_tokens}")
    print(f"Total completion tokens: {total_completion_tokens}")

if __name__ == "__main__":
    main()
