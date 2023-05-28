import json

from myst_nb.parser import *

SPHINX_LOGGER = logging.getLogger(__name__)

# Mostly taken and slightly adapted from https://github.com/executablebooks/MyST-NB/blob/v0.13.2/myst_nb/parser.py


class PatchedNotebookParser(MystParser):
    """Docutils parser for Markedly Structured Text (MyST) and Jupyter Notebooks."""

    supported = ("myst-nb",)
    translate_section_name = None

    config_section = "myst-nb parser"
    config_section_dependencies = ("parsers",)

    def parse(
        self, inputstring: str, document: nodes.document, renderer: str = "sphinx"
    ) -> None:
        self.reporter = document.reporter
        self.env = document.settings.env  # type: BuildEnvironment

        converter = get_nb_converter(
            self.env.doc2path(self.env.docname, True),
            self.env,
            inputstring.splitlines(keepends=True),
        )

        if converter is None:
            # Read the notebook as a text-document
            super().parse(inputstring, document=document)
            return

        try:
            ntbk = converter.func(inputstring)
        except Exception as error:
            SPHINX_LOGGER.error(
                "MyST-NB: Conversion to notebook failed: %s",
                error,
                # exc_info=True,
                location=(self.env.docname, 1),
            )
            return

        # add outputs to notebook from the cache
        if self.env.config["jupyter_execute_notebooks"] != "off":
            ntbk = generate_notebook_outputs(
                self.env, ntbk, show_traceback=self.env.config["execution_show_tb"]
            )

        # Parse the notebook content to a list of syntax tokens and an env
        # containing global data like reference definitions
        md_parser, env, tokens = patched_nb_to_tokens(  # <-- patched here
            ntbk,
            (
                self.env.myst_config  # type: ignore[attr-defined]
                if converter is None
                else converter.config
            ),
            self.env.config["nb_render_plugin"],
        )

        # Write the notebook's output to disk
        path_doc = nb_output_to_disc(ntbk, document)

        # Update our glue key list with new ones defined in this page
        glue_domain = NbGlueDomain.from_env(self.env)
        glue_domain.add_notebook(ntbk, path_doc)

        # Render the Markdown tokens to docutils AST.
        tokens_to_docutils(md_parser, env, tokens, document)


def patched_nb_to_tokens(
    ntbk: nbf.NotebookNode, config: MdParserConfig, renderer_plugin: str
) -> Tuple[MarkdownIt, Dict[str, Any], List[Token]]:
    """Parse the notebook content to a list of syntax tokens and an env,
    containing global data like reference definitions.
    """
    md = default_parser(config)
    # setup the markdown parser
    # Note we disable front matter parsing,
    # because this is taken from the actual notebook metadata
    md.disable("front_matter", ignoreInvalid=True)
    md.renderer = SphinxNBRenderer(md)
    # make a sandbox where all the parsing global data,
    # like reference definitions will be stored
    env: Dict[str, Any] = {}
    rules = md.core.ruler.get_active_rules()

    # First only run pre-inline chains
    # so we can collect all reference definitions, etc, before assessing references
    def parse_block(src, start_line):
        with md.reset_rules():
            # enable only rules up to block
            md.core.ruler.enableOnly(rules[: rules.index("inline")])
            tokens = md.parse(src, env)
        for token in tokens:
            if token.map:
                token.map = [start_line + token.map[0], start_line + token.map[1]]
        for dup_ref in env.get("duplicate_refs", []):
            if "fixed" not in dup_ref:
                dup_ref["map"] = [
                    start_line + dup_ref["map"][0],
                    start_line + dup_ref["map"][1],
                ]
                dup_ref["fixed"] = True
        return tokens

    block_tokens = []
    source_map = ntbk.metadata.get("source_map", None)

    # get language lexer name
    langinfo = ntbk.metadata.get("language_info", {})
    lexer = langinfo.get("pygments_lexer", langinfo.get("name", None))
    if lexer is None:
        ntbk.metadata.get("kernelspec", {}).get("language", None)
    # TODO log warning if lexer is still None

    for cell_index, nb_cell in enumerate(ntbk.cells):
        # if the the source_map has been stored (for text-based notebooks),
        # we use that do define the starting line for each cell
        # otherwise, we set a pseudo base that represents the cell index
        start_line = source_map[cell_index] if source_map else (cell_index + 1) * 10000
        start_line += 1  # use base 1 rather than 0

        # Skip empty cells
        if len(nb_cell["source"].strip()) == 0:
            continue

        # skip cells tagged for removal
        # TODO this logic should be deferred to a transform
        tags = nb_cell.metadata.get("tags", [])
        if ("remove_cell" in tags) or ("remove-cell" in tags):
            continue

        ### Patched here

        # Add a Token with a cell_meta directive, i.e.:
        #
        # ```cell_meta
        # {"slideshow": {"slide_type": "slide"}}
        # ```

        block_tokens.append(
            Token(
                type="fence",
                tag="code",
                nesting=0,
                attrs={},
                map=[start_line, start_line],
                level=0,
                children=None,
                content=json.dumps(nb_cell.metadata),
                markup="```",
                info="{cell_meta}",
                meta={},
                block=True,
                hidden=False,
            )
        )

        ### / Patched here

        if nb_cell["cell_type"] == "markdown":
            # we add the cell index to tokens,
            # so they can be included in the error logging,
            block_tokens.extend(parse_block(nb_cell["source"], start_line))

        elif nb_cell["cell_type"] == "code":
            # here we do nothing but store the cell as a custom token
            block_tokens.append(
                Token(
                    "nb_code_cell",
                    "",
                    0,
                    meta={"cell": nb_cell, "lexer": lexer, "renderer": renderer_plugin},
                    map=[start_line, start_line],
                )
            )

    # Now all definitions have been gathered,
    # we run inline and post-inline chains, to expand the text.
    # Note we assume here that these rules never require the actual source text,
    # only acting on the existing tokens
    state = StateCore("", md, env, block_tokens)
    with md.reset_rules():
        md.core.ruler.enableOnly(rules[rules.index("inline") :])
        md.core.process(state)

    # Add the front matter.
    # Note that myst_parser serialises dict/list like keys, when rendering to
    # docutils docinfo. These could be read back with `json.loads`.
    state.tokens = [
        Token(
            "front_matter",
            "",
            0,
            map=[0, 0],
            content=({k: v for k, v in ntbk.metadata.items()}),  # type: ignore[arg-type]
        )
    ] + state.tokens

    # If there are widgets, this will embed the state of all widgets in a script
    if contains_widgets(ntbk):
        state.tokens.append(
            Token(
                "jupyter_widget_state",
                "",
                0,
                map=[0, 0],
                meta={"state": get_widgets(ntbk)},
            )
        )

    return md, env, state.tokens
