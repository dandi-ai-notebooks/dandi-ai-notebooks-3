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

class XMLParsingError(Exception):
    """Custom exception for XML parsing errors."""
    pass

@dataclass
class GradeBlock:
    question_id: str
    thinking: str
    grade: int

    @classmethod
    def from_xml_element(cls, element: ET.Element) -> 'GradeBlock':
        """Parse a grade block from an XML element."""
        if element.tag != 'grade':
            raise ValueError(f"Expected 'grade' element, got '{element.tag}'")

        question_id = ''
        thinking = ''
        grade = 0

        for child in element:
            if child.tag == 'question_id':
                question_id = child.text.strip() if child.text else ''
            elif child.tag == 'thinking':
                thinking = child.text.strip() if child.text else ''
            elif child.tag == 'grade':
                try:
                    grade = int(child.text.strip()) if child.text else 0
                except ValueError:
                    raise ValueError(f"Invalid grade value: {child.text}")

        if not question_id:
            raise ValueError("Missing question_id")
        if not thinking:
            raise ValueError("Missing thinking")

        return cls(question_id=question_id, thinking=thinking, grade=grade)

class GradingEntry(TypedDict):
    question_id: str
    grade: int
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

def parse_grades_xml(xml_text: str) -> List[GradeBlock]:
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

        if len(grades) != 10:
            raise XMLParsingError(f"Expected 10 grade blocks, found {len(grades)}")

        return grades

    except ET.ParseError as e:
        raise XMLParsingError(f"Invalid XML format: {str(e)}")

model_for_gradings = "anthropic/claude-3.7-sonnet"
prompt_version = "2"

def find_critiqued_notebooks(base_dir: str) -> List[Tuple[str, str, str]]:
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

            # Check for cells critique
            cells_critique_path = os.path.join(subfolder_path, "cells_critique.txt")
            if os.path.isfile(cells_critique_path):
                notebook_paths.append((dandiset_id, subfolder, cells_critique_path))

    return notebook_paths

def read_gradings_system_prompt() -> str:
    template_path = (
        Path(__file__).parent / "templates" / "gradings_system_prompt.txt"
    )
    with open(template_path, "r") as f:
        content = f.read()
    return content

def get_gradings_for_notebook(cell_critiques_text: str) -> Tuple[str, int, int]:
    """Get rankings for a dandiset based on critiques."""
    system_prompt = read_gradings_system_prompt()

    messages: List[Dict[str, Any]] = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Please provide grades based on the following critique of the notebook, as explained in the system prompt."},
                {"type": "text", "text": cell_critiques_text}
            ]
        }
    ]

    assistant_response, _, prompt_tokens, completion_tokens = (
        run_completion(messages=messages, model=model_for_gradings)
    )

    return assistant_response, prompt_tokens, completion_tokens

def main():
    critiques_base_dir = Path(__file__).parent.parent / "critiques" / "dandisets"
    gradings_base_dir = Path(__file__).parent / "dandisets"
    notebooks = find_critiqued_notebooks(str(critiques_base_dir))
    print(f"Found {len(notebooks)} critiqued notebooks to process")

    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0

    # Process each dandiset
    for ii, a in enumerate(notebooks):
        dandiset_id, subfolder, cells_critique_path = a
        print(f"\n[{ii + 1}/{len(notebooks)}] Processing {dandiset_id}/{subfolder}")

        # Check if gradings already exist
        output_dir = gradings_base_dir / dandiset_id / subfolder
        output_file = output_dir / "grades.json"
        if output_file.exists():
            with open(output_file, "r") as f:
                existing_grades = json.load(f)
            if existing_grades.get("prompt_version") == prompt_version:
                print(f"Grades for {dandiset_id}/{subfolder} already exist.")
                continue
            print(f"Deleting existing grades for {dandiset_id}/{subfolder} to regenerate.")
            os.remove(output_file)

        with open(cells_critique_path, "r") as f:
            critiques = f.read()

        gradings_text, prompt_tokens, completion_tokens = get_gradings_for_notebook(critiques)
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens
        # Parse rankings text into structured format
        try:
            grades = parse_grades_xml(gradings_text)
        except XMLParsingError as e:
            print(gradings_text)
            raise Exception(f"Failed to parse grades: {str(e)}")

        gradings_entries: List[GradingEntry] = []
        for grade in grades:
            gradings_entries.append({
                "question_id": grade.question_id,
                "thinking": grade.thinking,
                "grade": grade.grade
            })

        print("Parsed grades:")
        for entry in gradings_entries:
            print(f"{entry['question_id']}: {entry['grade']}")
            print(f"Thinking: {entry['thinking']}\n")

        # Create output directory if needed
        os.makedirs(output_dir, exist_ok=True)

        # Save rankings to both JSON and text files
        result = {
            "prompt_version": prompt_version,
            "grades": [
                {
                    "question_id": entry["question_id"],
                    "grade": entry["grade"],
                    "thinking": entry["thinking"]
                }
                for entry in gradings_entries
            ],
            "metadata": {
                "total_prompt_tokens": prompt_tokens,
                "total_completion_tokens": completion_tokens,
                "model": model_for_gradings,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "system_info": {"platform": platform.platform(), "hostname": platform.node()}
            }
        }

        print(f"Writing gradings to {output_file}")
        # Save JSON format
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)

    print(f"\nTotal prompt tokens: {total_prompt_tokens}")
    print(f"Total completion tokens: {total_completion_tokens}")

if __name__ == "__main__":
    main()
