import json
import os

def read_file(path):
    with open(path, 'r') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w') as f:
        f.write(content)

def format_question(question):
    output = []
    output.append(f'question_id: {question["id"]}')
    output.append(question['text'])

    # Sort options by value in descending order
    options = sorted(question['options'], key=lambda x: x['value'], reverse=True)
    for option in options:
        output.append(f'{option["value"]}: {option["label"]}')

    return '\n'.join(output)

def main():
    base_prompt = read_file('gradings2/templates/gradings_user_message_rubric.txt')

    # Split at the first question_id to separate the introductory text
    parts = base_prompt.split('question_id:', 1)
    intro_text = parts[0]

    # Read and parse the questions JSON
    with open('gradings2/templates/questions.json', 'r') as f:
        questions_data = json.load(f)

    # Filter out reviewer questions and format the remaining ones
    formatted_questions = []
    for question in questions_data['questions']:
        if not question.get('about_reviewer', False):
            formatted_questions.append(format_question(question))

    # Combine everything
    final_content = intro_text + '\n' + '\n\n'.join(formatted_questions)

    # Write the output
    write_file('gradings2/templates/gradings_user_message_rubric_with_questions.txt', final_content)

if __name__ == '__main__':
    main()
