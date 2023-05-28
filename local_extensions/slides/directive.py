from sphinx.util.docutils import SphinxDirective
from docutils import nodes


class CellMetaNode(nodes.Element):
    def html(self):
        metadata = self["metadata"]
        return f'<script type="application/json" data-cell-meta="">{metadata}</script>'


class CellMetaDirective(SphinxDirective):
    has_content = True

    def run(self):
        joined = "".join(self.content)
        return [CellMetaNode(metadata=joined)]
