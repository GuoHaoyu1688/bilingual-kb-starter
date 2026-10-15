import json
import os
import subprocess
import sys


def run(kb, *args):
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "bilingual_kb_starter.cli",
            "--config",
            str(kb.config_path),
            *args,
            "--json",
        ],
        capture_output=True,
        text=True,
    )


def test_cli_output_and_errors(kb):
    for command in ["check", "missing-translations", "--version", "backup"]:
        result = run(kb, command)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["ok"]
    result = run(kb, "wrong")
    assert result.returncode == 2 and json.loads(result.stdout)["error"]["code"] == "ARGUMENT_ERROR"
    result = run(kb, "check", "--config", "/does/not/exist")
    assert result.returncode == 3


def test_build_locale_links_and_search(kb, tmp_path):
    (kb.docs / "zh/principles.md").unlink()  # exercise English fallback
    out = tmp_path / "output"
    result = run(kb, "build", "--out", str(out))
    assert result.returncode == 0, result.stderr
    for name in [
        "index.html",
        "zh/index.html",
        "timeline/index.html",
        "glossary/index.html",
        "zh/principles/index.html",
    ]:
        assert (out / name).exists()
    home = (out / "index.html").read_text()
    assert 'class="term-link"' in home
    assert 'data-md-component="source"' not in home
    fallback = (out / "zh/principles/index.html").read_text()
    assert "Translation pending" in fallback
    assert 'href="../glossary/#term-' in fallback
    search = json.loads((out / "search/search_index.json").read_text())
    assert any("示例" in row.get("text", "") for row in search["docs"])
    assert "\u200b" in json.dumps(search, ensure_ascii=False)


def test_direct_mkdocs_build_cannot_bypass_gate(kb, tmp_path):
    (kb.docs / "en/blocked.md").write_text("EXAMPLE-CONFIDENTIAL-ABC")
    cli = run(kb, "check")
    assert cli.returncode == 1 and not json.loads(cli.stdout)["ok"]
    build = run(kb, "build")
    assert build.returncode == 1
    direct = subprocess.run(
        [
            sys.executable,
            "-m",
            "mkdocs",
            "build",
            "-f",
            str(kb.config_path),
            "-d",
            str(tmp_path / "blocked-site"),
        ],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    assert direct.returncode != 0 and "Sensitive-content gate" in direct.stderr
