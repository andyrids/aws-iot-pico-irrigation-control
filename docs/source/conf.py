"""Configuration file for the Sphinx documentation builder.

For the full list of built-in configuration values, see the documentation @
https://www.sphinx-doc.org/en/master/usage/configuration.html
"""

import pathlib
import sys

docs_dir = pathlib.Path(__file__).parent.parent
package_dir = docs_dir.parent / "src" / "micropython_default"
sys.path.insert(0, package_dir.as_posix())
print(sys.path)

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "micropython-default"
copyright = "2024, Andrew Ridyard"
author = "Andrew Ridyard"
release = "0.0.1"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",  # include documentation from docstrings
    "sphinx.ext.napoleon",  # supports for Google & NumPy style docstrings
    "sphinx.ext.viewcode",  # add links to highlighted source code
    "sphinx.ext.githubpages",  # create .nojekyll file for GitHub Pages
]

templates_path = ["_templates"]
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# theme settings
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

autodoc_mock_imports = [
    "asyncio",
    "machine",
    "micropython",
    "network",
    "ntptime",
    "rp2",
    "umqtt",
]
