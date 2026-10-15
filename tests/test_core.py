import json
import zipfile

import pytest

from bilingual_kb_starter.core.content import ContentError, KnowledgeBase
from bilingual_kb_starter.plugin import TermLinker


def test_clean_gate_and_pending(kb):
    assert kb.check()["passed"]
    assert any(x["page"] == "index.md" and x["locale"] == "zh" for x in kb.missing())
    (kb.docs / "zh/principles.md").unlink()
    assert {"page": "principles.md", "locale": "zh", "reason": "missing"} in kb.missing()


@pytest.mark.parametrize(
    "value,rule",
    [
        ("EXAMPLE-CONFIDENTIAL-ABC", "keyword:EXAMPLE-CONFIDENTIAL-ABC"),
        ("13800000000", "phone"),
        ("sample@example.invalid", "email"),
        ("123456789012345678", "identity_number"),
        ("INTERNAL-1234", "internal_code"),
    ],
)
def test_sensitive_rules_and_whitelist(kb, value, rule):
    page = kb.docs / "en/temporary.md"
    page.write_text("Safe\n" + value + "\n")
    result = kb.check()
    assert not result["passed"]
    assert any(
        x["file"] == "en/temporary.md" and x["line"] == 2 and x["rule"] == rule
        for x in result["findings"]
    )
    page.write_text(value + " <!-- kb-allow -->\n")
    assert kb.check()["passed"] and kb.check()["allowed_lines"]


def test_gate_does_not_skip_docs_named_backups(kb):
    path = kb.docs / "backups"
    path.mkdir()
    (path / "leak.txt").write_text("EXAMPLE-CONFIDENTIAL-ABC")
    assert not kb.check()["passed"]


def test_symlinks_rejected(kb, tmp_path):
    (kb.docs / "linked.md").symlink_to(tmp_path / "outside.md")
    with pytest.raises(ContentError, match="Symbolic"):
        kb.check()


def test_new_page_safe_and_never_overwrites(kb):
    result = kb.new_page("example-page", "principles", "Example page")
    assert len(result["paths"]) == 2
    assert (kb.docs / "zh/principles/example-page.md").is_file()
    with pytest.raises(ContentError, match="already exists"):
        kb.new_page("example-page", "principles")
    for slug, section in [("../outside", ""), ("valid", "../outside"), ("Bad", "")]:
        with pytest.raises(ContentError):
            kb.new_page(slug, section)


def test_generated_pages_and_deterministic_content(kb):
    tables = kb.generate()
    path = kb.docs / "en/glossary.md"
    before = path.read_bytes()
    mtime = path.stat().st_mtime_ns
    kb.generate()
    assert path.read_bytes() == before and path.stat().st_mtime_ns == mtime
    assert KnowledgeBase.term_id(tables["glossary"][0]) in before.decode()
    assert "timeline-entry" in (kb.docs / "en/timeline.md").read_text()
    assert "ref-example-handbook" in (kb.docs / "en/references.md").read_text()


def test_autolinks_first_use_skip_code_links_headings(kb):
    tables = kb.data_tables()
    linker = TermLinker(tables["glossary"], tables["references"], "../glossary/", "../references/")
    linker.feed(
        '<h1>Example term</h1><p>Example term and Example term <code>Example process</code> <a href="x">Example process</a> Example process [@example-handbook]</p>'
    )
    output = "".join(linker.output)
    assert output.count('class="term-link"') == 2
    assert "<h1>Example term</h1>" in output and "<code>Example process</code>" in output
    assert 'href="../references/#ref-example-handbook">[1]</a>' in output


def test_unknown_citation_is_build_error(kb):
    from mkdocs.exceptions import PluginError

    with pytest.raises(PluginError, match="Unknown reference"):
        TermLinker([], [], "", "").feed("See [@missing]")


@pytest.mark.parametrize("format", ["json", "csv"])
def test_export_import_backup_roundtrip(kb, tmp_path, format):
    source = kb.data_tables()
    out = tmp_path / f"export.{format}"
    kb.export(out, format)
    if format == "csv":
        assert out.read_bytes().startswith(b"\xef\xbb\xbf")
    with pytest.raises(ContentError, match="--yes"):
        kb.import_data(out)
    result = kb.import_data(out, True)
    assert kb.data_tables() == source
    with zipfile.ZipFile(result["backup"]) as archive:
        assert archive.testzip() is None
        assert "overrides/partials/source.html" in archive.namelist()
        assert (
            "data/glossary.csv" in archive.namelist() and "docs/en/index.md" in archive.namelist()
        )
        assert not any("/backups/" in x for x in archive.namelist())


def test_sensitive_import_rolls_back(kb, tmp_path):
    before = kb.data_tables()
    bad = json.loads(json.dumps(before))
    bad["timeline"][0]["title"] = "EXAMPLE-CONFIDENTIAL-ABC"
    source = tmp_path / "bad.json"
    source.write_text(json.dumps({"schema_version": 1, "tables": bad}))
    with pytest.raises(ContentError, match="gate"):
        kb.import_data(source, True)
    assert kb.data_tables() == before


def test_data_validation_rejects_active_urls(kb):
    tables = kb.data_tables()
    tables["references"][0]["url"] = "javascript:alert(1)"
    with pytest.raises(ContentError, match="HTTP"):
        kb.validate_tables(tables)


def test_generated_html_escapes_data(kb):
    data = kb.data_tables()
    data["timeline"][0]["title"] = "<script>alert(1)</script>"
    import yaml

    (kb.data / "timeline.yaml").write_text(yaml.safe_dump(data["timeline"]))
    kb.generate()
    assert "&lt;script&gt;" in (kb.docs / "en/timeline.md").read_text()
