# Sphinx configuration for certbot-dns-azure-modern.
#
# The user documentation lives in the .rst files next to this file; the changelog
# page includes ../CHANGELOG.md through myst-parser. Built and published to GitHub
# Pages by .github/workflows/docs.yml.

import re
from importlib import metadata
from pathlib import Path

project = 'certbot-dns-azure-modern'
author = 'Christoph Vollmann'
copyright = '2017 Certbot Project and Terri Cain, 2026 Christoph Vollmann'


def _version() -> str:
    """Version of the installed package, falling back to setup.py."""
    try:
        return metadata.version(project)
    except metadata.PackageNotFoundError:
        setup_py = Path(__file__).resolve().parent.parent / 'setup.py'
        match = re.search(r"^version\s*=\s*'([^']+)'", setup_py.read_text(), re.MULTILINE)
        return match.group(1) if match else '0'


release = _version()
version = release

extensions = [
    'sphinx.ext.intersphinx',
    'myst_parser',
]

source_suffix = '.rst'
master_doc = 'index'
language = 'en'
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
default_role = 'py:obj'
pygments_style = 'sphinx'

html_theme = 'sphinx_rtd_theme'
html_title = f'{project} {release}'
html_static_path = ['_static']
html_css_files = ['custom.css']
html_context = {
    'display_github': True,
    'github_user': 'cloudchristoph',
    'github_repo': 'certbot-dns-azure-modern',
    'github_version': 'main',
    'conf_py_path': '/docs/',
}

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'acme': ('https://acme-python.readthedocs.io/en/latest/', None),
    'certbot': ('https://eff-certbot.readthedocs.io/en/stable/', None),
}
