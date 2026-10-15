"""MkDocs plugin enforcing the gate even when users call mkdocs directly."""

import html
import os
import re
from html.parser import HTMLParser

from mkdocs.config import config_options
from mkdocs.exceptions import PluginError
from mkdocs.plugins import BasePlugin, event_priority
from mkdocs.utils import get_relative_url

from .core.content import KnowledgeBase


class TermLinker(HTMLParser):
    """Link first body-text terminology occurrences without touching links or code."""

    def __init__(self, terms, references, glossary_url, references_url):
        super().__init__(convert_charrefs=False)
        self.output = []
        self.stack = []
        self.used = set()
        self.terms = {}
        for term in terms:
            for word in (term["en"], term["zh"], term["abbr"]):
                if word:
                    self.terms[word.casefold()] = KnowledgeBase.term_id(term)
        patterns = []
        for term in sorted(self.terms, key=len, reverse=True):
            patterns.append(
                (r"(?<!\w)" + re.escape(term) + r"(?!\w)") if term.isascii() else re.escape(term)
            )
        self.pattern = re.compile(
            r"\[@([a-z0-9-]+)\]" + ("|" + "|".join(patterns) if patterns else ""), re.IGNORECASE
        )
        self.references = {row["id"]: i for i, row in enumerate(references, 1)}
        self.glossary_url, self.references_url = glossary_url, references_url

    def handle_starttag(self, tag, attrs):
        self.output.append(self.get_starttag_text())
        if tag not in {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.output.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        self.output.append(f"</{tag}>")
        if tag in self.stack:
            self.stack = self.stack[: len(self.stack) - self.stack[::-1].index(tag) - 1]

    def handle_data(self, data):
        if any(
            tag in {"a", "code", "pre", "script", "style", "h1", "h2", "h3", "h4", "h5", "h6"}
            for tag in self.stack
        ):
            self.output.append(html.escape(data, quote=False))
            return
        last = 0
        for match in self.pattern.finditer(data):
            self.output.append(html.escape(data[last : match.start()], quote=False))
            value = match.group(0)
            if value.startswith("[@"):
                key = match.group(1)
                if key not in self.references:
                    raise PluginError(f"Unknown reference: {key}")
                self.output.append(
                    f'<a class="citation" href="{self.references_url}#ref-{key}">[{self.references[key]}]</a>'
                )
            else:
                identifier = self.terms[value.casefold()]
                if identifier not in self.used:
                    self.output.append(
                        f'<a class="term-link" href="{self.glossary_url}#{identifier}">{html.escape(value)}</a>'
                    )
                    self.used.add(identifier)
                else:
                    self.output.append(html.escape(value))
            last = match.end()
        self.output.append(html.escape(data[last:], quote=False))

    def handle_entityref(self, name):
        self.output.append(f"&{name};")

    def handle_charref(self, name):
        self.output.append(f"&#{name};")

    def handle_comment(self, data):
        self.output.append(f"<!--{data}-->")


class KnowledgePlugin(BasePlugin):
    config_scheme = (
        ("data_dir", config_options.Type(str, default="data")),
        ("rules_file", config_options.Type(str, default="sensitive.yaml")),
        ("auto_link", config_options.Type(bool, default=True)),
    )

    @event_priority(100)
    def on_pre_build(self, config):
        self.kb = KnowledgeBase(config.config_file_path, os.getenv("KBTOOL_DATA_DIR"))
        result = self.kb.check()
        if not result["passed"]:
            details = "; ".join(
                f"{f['root']}/{f['file']}:{f['line']} ({f['rule']})" for f in result["findings"]
            )
            raise PluginError("Sensitive-content gate blocked this build: " + details)
        self.tables = self.kb.generate()
        self.pending = self.kb.missing()

    @event_priority(-10)
    def on_page_markdown(self, markdown, page, config, files):
        locale = getattr(page.file, "locale_alternate_of", getattr(page.file, "locale", "en"))
        source = getattr(page.file, "src_uri", "")
        missing = page.meta.get("translation_status") == "pending"
        if locale == "zh":
            # The i18n plugin records a source locale when falling back to English.
            missing = (
                missing
                or getattr(page.file, "locale", locale) != locale
                or source.startswith("en/")
            )
        if missing:
            return (
                '!!! warning "Translation pending"\n    This locale slot currently contains English placeholder content.\n\n'
                + markdown
            )
        return markdown

    def on_page_content(self, html_text, page, config, files):
        locale = getattr(page.file, "locale_alternate_of", getattr(page.file, "locale", "en"))
        prefix = "zh/" if locale == "zh" else ""
        url = page.file.url
        is_glossary = url.rstrip("/").endswith("glossary")
        linker = TermLinker(
            self.tables["glossary"] if self.config["auto_link"] and not is_glossary else [],
            self.tables["references"],
            get_relative_url(prefix + "glossary/", url),
            get_relative_url(prefix + "references/", url),
        )
        linker.feed(html_text)
        return "".join(linker.output)
