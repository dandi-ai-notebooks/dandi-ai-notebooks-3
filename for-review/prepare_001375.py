import base64

# Base GitHub URL prefix
GITHUB_URL_PREFIX = 'https://github.com/dandi-ai-notebooks/001375/blob/main/2025-04-25-'

# Models to generate links for
models = [
    'gemini-2.0flash-001-a-7',
    'gemini-2.0flash-001-b-7',
    'gemini-2.0flash-001-d-7',
    'claude-3.7-sonnet-prompt-a-7',
    'claude-3.7-sonnet-prompt-b-7',
    'claude-3.7-sonnet-prompt-d-7',
    'gpt-4o-a-7',
    'gpt-4o-b-7',
    'gpt-4o-d-7'
]

def generate_review_link(model):
    # Create the GitHub URL
    github_url = f'{GITHUB_URL_PREFIX}{model}/001375.ipynb'

    # Base64 encode the URL
    b64url = base64.b64encode(github_url.encode()).decode()

    # Create the review link
    review_link = f'https://dandi-ai-notebooks.github.io/dandi-notebook-review/review?url={b64url}'

    return review_link, b64url

# Generate all links and sort by base64 encoding
links_with_b64 = [generate_review_link(model) for model in models]
sorted_links = sorted(links_with_b64, key=lambda x: x[1])

# Create the markdown content
md_content = '''Please review the following notebooks. You will need an API key, which you can get from Jeremy.

:warning: If the notebooks do not show up in your browser, try using a different browser.

'''

# Add sorted links as markdown links with notebook numbers
for i, (link, _) in enumerate(sorted_links, 1):
    md_content += f'- [notebook {i}]({link})\n\n'

# Write to file
with open('for-review/001375.md', 'w') as f:
    f.write(md_content)
