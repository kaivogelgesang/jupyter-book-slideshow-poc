import json
from pathlib import Path

from sphinx.util import logging
from docutils import nodes

from .parser import PatchedNotebookParser
from .directive import CellMetaDirective, CellMetaNode

__version__ = "0.1"


# Used to render an element node as HTML
# see https://github.com/executablebooks/sphinx-thebe/blob/v0.2.1/sphinx_thebe/__init__.py#L219
def visit_element_html(self, node):
    self.body.append(node.html())
    raise nodes.SkipNode


# Used for nodes that do not need to be rendered
def skip(self, node):
    raise nodes.SkipNode


def add_static_sources(app):
    static_path = Path(__file__).parent / "static"
    app.config.html_static_path.append(static_path.as_posix())


def enable_presentation_mode(app, pagename, templatename, context, doctree):
    if not doctree or not (meta_nodes := doctree.traverse(CellMetaNode)):
        # page has no cell metadata -> no slideshow
        return

    if not any(
        "slideshow" in json.loads(node["metadata"])
        for node in meta_nodes
    ):
        # notebook was not configured to be a slideshow
        return

    context["header_buttons"].append(
        {
            "type": "javascript",
            "javascript": "startPresentation()",
            "tooltip": "Start presenting",
            "icon": "fas fa-chart-bar",
        }
    )

    app.add_css_file("vendor/reveal.css")
    app.add_css_file("vendor/simple.css")  # theme
    app.add_css_file("fix-theme.css")
    app.add_js_file("vendor/reveal.js")
    app.add_js_file("present.js")


def setup(app):
    # override the MyST-NB NotebookParser with our patched version
    app.add_source_parser(PatchedNotebookParser, override=True)

    # register directive and node required to process the added metadata
    app.add_directive("cell_meta", CellMetaDirective)
    app.add_node(
        CellMetaNode,
        html=(visit_element_html, None),
        latex=(skip, None),
        textinfo=(skip, None),
        text=(skip, None),
        man=(skip, None),
        override=True,
    )

    # include sources for static js / css content
    app.connect("builder-inited", add_static_sources)

    # add the button and js / css files
    # set priority so this runs before the download button is added
    app.connect("html-page-context", enable_presentation_mode, priority=500)

    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
