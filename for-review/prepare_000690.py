import base64
import hashlib

# Base GitHub URL prefix
GITHUB_URL_PREFIX = 'https://github.com/dandi-ai-notebooks/000690/blob/main/2025-04-28-'

# Models to generate links for
models = [
    'gemini-2.0-flash-001-prompt-a-8',
    'gemini-2.0-flash-001-prompt-b-8',
    'gemini-2.0-flash-001-prompt-d-8',
    'gemini-2.5-pro-preview-03-25-prompt-a-8',
    'gemini-2.5-pro-preview-03-25-prompt-b-8',
    'gemini-2.5-pro-preview-03-25-prompt-d-8'
]

def generate_review_link(model):
    # Create the GitHub URL
    github_url = f'{GITHUB_URL_PREFIX}{model}/000690.ipynb'

    # Base64 encode the URL
    b64url = base64.b64encode(github_url.encode()).decode()

    # Create the review link
    review_link = f'https://dandi-ai-notebooks.github.io/dandi-notebook-review/review?url={b64url}'

    # Calculate SHA1 of base64 URL
    sha1 = hashlib.sha1(b64url.encode()).hexdigest()

    return review_link, b64url, sha1

# Generate all links and sort by SHA1 of base64 encoding
links_with_sha1 = [generate_review_link(model) for model in models]
sorted_links = sorted(links_with_sha1, key=lambda x: x[2])  # Sort by SHA1

# Create the markdown content
md_content = '''Please review the following notebooks. You will need an API key, which you can get from Jeremy.

:warning: If the notebooks do not show up in your browser, try using a different browser.

'''

# Add sorted links as markdown links with notebook numbers
for i, (link, _, _) in enumerate(sorted_links, 1):
    md_content += f'- [notebook {i}]({link})\n\n'

# Write to file
with open('for-review/000690.md', 'w') as f:
    f.write(md_content)
