import json
import hashlib
from collections import defaultdict
from typing import List, Dict, Any

def load_notebook_grades(filepath: str) -> List[Dict[str, Any]]:
    """Load and process notebook gradings from JSON file."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    return data

def get_notebook_score(notebook: Dict[str, Any]) -> int:
    """Calculate total score for a notebook (sum of positive grades)."""
    return sum(max(0, grade_info['grade'])
              for grade_info in notebook['gradings']['grades'])

def get_question_grade_ranges(notebooks: List[Dict[str, Any]]) -> Dict[str, set]:
    """Get the range of possible grades for each question."""
    question_grades = defaultdict(set)
    for nb in notebooks:
        for grade_info in nb['gradings']['grades']:
            question_grades[grade_info['question_id']].add(grade_info['grade'])
    return question_grades

def get_covered_grades(notebooks: List[Dict[str, Any]]) -> Dict[str, set]:
    """Get the grades covered by a set of notebooks for each question."""
    covered_grades = defaultdict(set)
    for nb in notebooks:
        for grade_info in nb['gradings']['grades']:
            covered_grades[grade_info['question_id']].add(grade_info['grade'])
    return covered_grades

def calculate_coverage_score(selected: List[Dict[str, Any]], question_grades: Dict[str, set]) -> float:
    """
    Calculate how well the selected notebooks distribute grades across questions using entropy.

    The function uses entropy to measure the evenness of grade distribution for each question.
    For example, if a question has possible grades [0,1,2] and our selected notebooks have:
    - Five notebooks with grade 0
    - One notebook with grade 1
    - One notebook with grade 2
    This would have lower entropy (more uneven) than:
    - Two notebooks with grade 0
    - Two notebooks with grade 1
    - Three notebooks with grade 2

    Steps:
    1. For each question:
       - Count frequency of each possible grade in selected notebooks
       - Calculate probability distribution (normalize frequencies)
       - Calculate entropy of this distribution
       - Normalize by maximum possible entropy (uniform distribution)
    2. Average the normalized entropies across all questions

    Returns a score between 0 and 1, where:
    - 1.0 means perfectly even distribution of grades for all questions
    - 0.0 means all notebooks have the same grade for each question
    """
    import math
    from collections import Counter

    def calculate_entropy(grade_counts: Counter, total: int) -> float:
        """Calculate entropy for a single question's grade distribution."""
        entropy = 0
        for count in grade_counts.values():
            if count > 0:
                p = count / total
                entropy -= p * math.log2(p)
        return entropy

    def get_max_entropy(num_possible_grades: int) -> float:
        """Calculate maximum possible entropy (uniform distribution)."""
        if num_possible_grades <= 0:
            return 0
        p = 1.0 / num_possible_grades
        return -num_possible_grades * p * math.log2(p)

    # Get grade frequencies for each question
    question_grades_freq = defaultdict(Counter)
    for nb in selected:
        for grade_info in nb['gradings']['grades']:
            question_grades_freq[grade_info['question_id']][grade_info['grade']] += 1

    # Calculate normalized entropy for each question
    entropy_scores = []
    for question_id, possible_grades in question_grades.items():
        grade_counts = question_grades_freq[question_id]
        total_grades = sum(grade_counts.values())

        if total_grades > 0:
            # Calculate actual entropy
            entropy = calculate_entropy(grade_counts, total_grades)
            # Calculate maximum possible entropy
            max_entropy = get_max_entropy(len(possible_grades))
            # Normalize entropy score
            if max_entropy > 0:
                normalized_entropy = entropy / max_entropy
                entropy_scores.append(normalized_entropy)
            else:
                entropy_scores.append(0)
        else:
            entropy_scores.append(0)

    # Return average normalized entropy across all questions
    return sum(entropy_scores) / len(entropy_scores) if entropy_scores else 0

def select_representative_notebooks(notebooks: List[Dict[str, Any]], num_select: int = 10) -> List[Dict[str, Any]]:
    """Select notebooks that maximize grade coverage across questions."""
    question_grades = get_question_grade_ranges(notebooks)

    # Start with the notebook that has the highest score
    notebooks_with_scores = [(nb, get_notebook_score(nb)) for nb in notebooks]
    notebooks_with_scores.sort(key=lambda x: (-x[1], x[0]['dandiset_id'], x[0]['subfolder']))  # Sort by score (desc) then ID/subfolder
    selected = [notebooks_with_scores[0][0]]
    remaining = [nb for nb, _ in notebooks_with_scores[1:]]

    # Iteratively add notebooks that provide the best improvement in coverage
    while len(selected) < num_select and remaining:
        best_score = -1
        best_notebook = None

        for candidate in remaining:
            # Temporarily add this notebook and calculate coverage
            temp_selected = selected + [candidate]
            score = calculate_coverage_score(temp_selected, question_grades)

            if score > best_score:
                best_score = score
                best_notebook = candidate

        if best_notebook:
            selected.append(best_notebook)
            remaining.remove(best_notebook)
        else:
            break

    return selected

def format_notebook_grades(notebook: Dict[str, Any]) -> str:
    """Format grades for display."""
    grades = {grade['question_id']: grade['grade']
             for grade in notebook['gradings']['grades']}
    return ' '.join(f"{k}:{v}" for k, v in sorted(grades.items()))

def print_coverage_analysis(selected: List[Dict[str, Any]], question_grades: Dict[str, set]):
    """Print detailed coverage analysis for each question."""
    covered_grades = get_covered_grades(selected)

    print("\nDetailed Coverage Analysis:")
    print("Question | Covered Grades | Possible Grades | Coverage")
    print("-" * 65)

    for question_id in sorted(question_grades.keys()):
        possible = sorted(question_grades[question_id])
        covered = sorted(covered_grades[question_id])
        coverage_pct = len(covered) / len(possible) * 100
        print(f"{question_id:<30} | {covered} | {possible} | {coverage_pct:.0f}%")

def print_score_distribution(notebooks: List[Dict[str, Any]]):
    """Print distribution of total scores for selected notebooks."""
    scores = [get_notebook_score(nb) for nb in notebooks]
    scores.sort()

    print("\nScore Distribution of Selected Notebooks:")
    print("Sorted list of scores:")
    print(scores)

    if scores:
        print(f"\nMin score: {min(scores)}")
        print(f"Max score: {max(scores)}")
        print(f"Mean score: {sum(scores)/len(scores):.1f}")
        print(f"Median score: {scores[len(scores)//2]}")
        print(f"Number of notebooks: {len(scores)}")

def main():
    # Load and process notebooks
    notebooks = load_notebook_grades('notebook_gradings.json')

    # Get possible grades for each question
    question_grades = get_question_grade_ranges(notebooks)
    print("Question grade ranges:")
    for question, grades in sorted(question_grades.items()):
        print(f"{question}: {sorted(grades)}")
    print()

    # Select representative notebooks
    selected = select_representative_notebooks(notebooks)

    # Print results
    print(f"\nSelected {len(selected)} notebooks for review:")
    for nb in selected:
        score = get_notebook_score(nb)
        print(f"{nb['dandiset_id']}/{nb['subfolder']}: {score}")
    print("")

    # Print coverage analysis
    coverage = calculate_coverage_score(selected, question_grades)
    print(f"\nOverall grade coverage: {coverage:.1%}")

    # Print detailed coverage analysis
    print_coverage_analysis(selected, question_grades)

    # Print score distribution for selected notebooks
    print_score_distribution(selected)

    print("")

    for i, nb in enumerate(selected):
        dandiset_id = nb['dandiset_id']
        subfolder = nb['subfolder']
        sha1_of_subfolder = hashlib.sha1(subfolder.encode()).hexdigest()
        path = f"for-review/dandisets/{dandiset_id}/{sha1_of_subfolder}/{dandiset_id}.ipynb"
        url = f"https://github.com/dandi-ai-notebooks/dandi-ai-notebooks-3/blob/main/{path}"
        review_url = f"https://dandi-ai-notebooks.github.io/dandi-notebook-review/review?url={url}"
        print(f"* {i + 1}. [{path}]({review_url})")

if __name__ == '__main__':
    main()
