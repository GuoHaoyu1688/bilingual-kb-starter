"""Content scanning, locale coverage, structured data and generated pages."""

from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import re
import zipfile
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml


class ContentError(Exception):
    def __init__(self, message: str, code="INVALID_INPUT", exit_code=2):
        super().__init__(message)
        self.code, self.exit_code = code, exit_code


class KnowledgeBase:
    def __init__(self, config="mkdocs.yml", data_dir=None):
        self.config_path = Path(config).resolve()
        if not self.config_path.is_file():
            raise ContentError("MkDocs configuration not found", "NOT_FOUND", 3)
        self.root = self.config_path.parent
        self.config = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        if not isinstance(self.config, dict):
            raise ContentError("MkDocs configuration must be a mapping")
        self.docs = (self.root / self.config.get("docs_dir", "docs")).resolve()
        plugin = next(
            (
                p["kb-gate"] or {}
                for p in self.config.get("plugins", [])
                if isinstance(p, dict) and "kb-gate" in p
            ),
            {},
        )
        self.data = (
            Path(data_dir).resolve()
            if data_dir
            else (self.root / plugin.get("data_dir", "data")).resolve()
        )
        self.rules_path = (self.root / plugin.get("rules_file", "sensitive.yaml")).resolve()
        if not self.rules_path.is_file():
            raise ContentError("Sensitive-content rules file not found", "NOT_FOUND", 3)
        self.rules = yaml.safe_load(self.rules_path.read_text(encoding="utf-8")) or {}
        if not isinstance(self.rules, dict):
            raise ContentError("Sensitive-content rules must be a mapping")

    def check(self) -> dict:
        findings, ignored, scanned = [], [], 0
        patterns = {
            name: re.compile(pattern) for name, pattern in self.rules.get("patterns", {}).items()
        }
        for base in (self.docs, self.data):
            if not base.is_dir():
                raise ContentError(f"Content directory is missing: {base.name}", "NOT_FOUND", 3)
            for path in sorted(base.rglob("*")):
                if path.is_symlink():
                    raise ContentError(
                        "Symbolic links are not allowed in published content", "UNSAFE_PATH"
                    )
                if not path.is_file() or path.suffix.lower() not in {
                    ".md",
                    ".txt",
                    ".yaml",
                    ".yml",
                    ".csv",
                    ".json",
                    ".html",
                    ".bib",
                    ".js",
                    ".css",
                }:
                    continue
                if base == self.data and path.relative_to(base).parts[0] == "backups":
                    continue
                scanned += 1
                for line_no, line in enumerate(
                    path.read_text(encoding="utf-8-sig").splitlines(), 1
                ):
                    rules = [
                        f"keyword:{word}"
                        for word in self.rules.get("keywords", [])
                        if word.casefold() in line.casefold()
                    ]
                    rules += [name for name, pattern in patterns.items() if pattern.search(line)]
                    for rule in rules:
                        item = {
                            "file": str(path.relative_to(base)),
                            "root": "docs" if base == self.docs else "data",
                            "line": line_no,
                            "rule": rule,
                        }
                        (ignored if "<!-- kb-allow -->" in line else findings).append(item)
        return {
            "files_scanned": scanned,
            "findings": findings,
            "allowed_lines": ignored,
            "passed": not findings,
        }

    def missing(self) -> list[dict]:
        en = {
            p.relative_to(self.docs / "en").as_posix(): p for p in (self.docs / "en").rglob("*.md")
        }
        zh = {
            p.relative_to(self.docs / "zh").as_posix(): p for p in (self.docs / "zh").rglob("*.md")
        }
        results = []
        for name in sorted(en.keys() | zh.keys()):
            for locale, pages in (("en", en), ("zh", zh)):
                if name not in pages:
                    results.append({"page": name, "locale": locale, "reason": "missing"})
                elif re.search(
                    r"^translation_status:\s*pending\s*$",
                    pages[name].read_text(encoding="utf-8"),
                    re.MULTILINE,
                ):
                    results.append({"page": name, "locale": locale, "reason": "pending"})
        return results

    def new_page(self, slug: str, section: str = "", title: str | None = None) -> dict:
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise ContentError("Slug must use lowercase kebab-case")
        if section and not all(
            re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", part) for part in section.split("/")
        ):
            raise ContentError("Section must contain safe lowercase path components")
        paths = [self.docs / locale / section / f"{slug}.md" for locale in ("en", "zh")]
        if any(path.exists() for path in paths):
            raise ContentError(
                "A locale page already exists; no files were changed", "ALREADY_EXISTS"
            )
        title = title or slug.replace("-", " ").title()
        for locale, path in zip(("en", "zh"), paths, strict=True):
            if not path.resolve().is_relative_to(self.docs):
                raise ContentError("Page path escapes docs", "UNSAFE_PATH")
            path.parent.mkdir(parents=True, exist_ok=True)
            front = yaml.safe_dump(
                {"title": title, "translation_status": "complete" if locale == "en" else "pending"},
                sort_keys=False,
            )
            path.write_text(
                f"---\n{front}---\n\n# {title}\n\nPlaceholder content. Add only public, cited information.\n",
                encoding="utf-8",
            )
        return {"paths": [str(p) for p in paths]}

    def data_tables(self) -> dict[str, list[dict]]:
        with (self.data / "glossary.csv").open(encoding="utf-8-sig", newline="") as stream:
            glossary = list(csv.DictReader(stream))
        tables = {"glossary": glossary}
        for name in ("timeline", "references"):
            tables[name] = (
                yaml.safe_load((self.data / f"{name}.yaml").read_text(encoding="utf-8")) or []
            )
        self.validate_tables(tables)
        return tables

    @staticmethod
    def validate_tables(tables: dict) -> None:
        if not isinstance(tables, dict) or set(tables) != {"glossary", "timeline", "references"}:
            raise ContentError("Expected glossary, timeline and references tables")
        for name, rows in tables.items():
            if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
                raise ContentError(f"{name} must be a list of objects")
        for row in tables["glossary"]:
            if not all(
                key in row for key in ("zh", "en", "abbr", "definition_zh", "definition_en")
            ):
                raise ContentError("Glossary fields are incomplete")
            if not row["en"] or not row["zh"]:
                raise ContentError("Glossary terms cannot be blank")
        for row in tables["timeline"]:
            date.fromisoformat(str(row["date"]))
            if not row.get("title"):
                raise ContentError("Timeline title is required")
        ids = [str(row.get("id", "")) for row in tables["references"]]
        if any(not re.fullmatch(r"[a-z0-9-]+", key) for key in ids) or len(ids) != len(set(ids)):
            raise ContentError("Reference identifiers must be unique lowercase slugs")
        for row in tables["references"]:
            if row.get("url") and not re.match(r"^https?://", row["url"]):
                raise ContentError("Reference URL must use HTTP or HTTPS")

    @staticmethod
    def term_id(row: dict) -> str:
        return "term-" + hashlib.sha256(row["en"].encode()).hexdigest()[:12]

    def generate(self) -> dict:
        tables = self.data_tables()
        glossary = [
            "# Glossary",
            "",
            '<label for="glossary-filter">Find a term</label>',
            '<input id="glossary-filter" type="search" placeholder="Term, abbreviation or definition">',
            "",
            '<div id="glossary-entries">',
        ]
        for row in tables["glossary"]:
            glossary += [
                f'<section class="glossary-entry" id="{self.term_id(row)}"><h2>{html.escape(row["en"])} <small>{html.escape(row["abbr"])}</small></h2><p>{html.escape(row["zh"])}</p><p>{html.escape(row["definition_en"])}</p><p>{html.escape(row["definition_zh"])}</p></section>'
            ]
        glossary += ["</div>", ""]
        timeline = [
            "# Technical timeline",
            "",
            "All events below are fictional placeholders.",
            "",
            '<label for="timeline-filter">Filter milestones</label>',
            '<input id="timeline-filter" type="search" placeholder="Year or keyword">',
            "",
            '<div id="timeline-entries">',
        ]
        for item in sorted(tables["timeline"], key=lambda row: str(row["date"])):
            timeline += [
                f'<details class="timeline-entry" open><summary><time>{html.escape(str(item["date"]))}</time> {html.escape(item["title"])}</summary><p>{html.escape(item.get("description", ""))}</p></details>'
            ]
        timeline += ["</div>", ""]
        references = [
            "# References",
            "",
            "Replace fictional entries with verified public sources before adding real technical content.",
            "",
        ]
        for i, row in enumerate(tables["references"], 1):
            body = html.escape(
                f"{row.get('author', '')} ({row.get('year', '')}). {row.get('title', '')}"
            )
            if row.get("url"):
                body += f' <a href="{html.escape(row["url"], quote=True)}">Source</a>'
            references += [f'<p id="ref-{row["id"]}">[{i}] {body}</p>', ""]
        for locale in ("en", "zh"):
            for name, lines in (
                ("glossary", glossary),
                ("timeline", timeline),
                ("references", references),
            ):
                path = self.docs / locale / f"{name}.md"
                path.parent.mkdir(parents=True, exist_ok=True)
                body = (
                    "---\ntranslation_status: pending\n---\n\n" if locale == "zh" else ""
                ) + "\n".join(lines)
                if not path.exists() or path.read_text(encoding="utf-8") != body:
                    path.write_text(body, encoding="utf-8")
        return tables

    def export(self, output: str | Path, format: str = "json", bom: bool = True) -> dict:
        tables = self.data_tables()
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        if format == "json":
            path.write_text(
                json.dumps({"schema_version": 1, "tables": tables}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        elif format == "csv":
            with path.open("w", encoding="utf-8-sig" if bom else "utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["table", "row_json"])
                for table, rows in tables.items():
                    for row in rows:
                        writer.writerow([table, json.dumps(row, ensure_ascii=False)])
        else:
            raise ContentError("Format must be csv or json")
        return {"path": str(path.resolve()), "rows": sum(map(len, tables.values()))}

    def import_data(self, path: str | Path, confirm: bool = False) -> dict:
        if not confirm:
            raise ContentError(
                "Import replaces template data; pass --yes after reviewing the file",
                "CONFIRM_REQUIRED",
            )
        path = Path(path)
        if path.suffix == ".csv":
            tables = {name: [] for name in ("glossary", "timeline", "references")}
            with path.open(encoding="utf-8-sig", newline="") as stream:
                for row in csv.DictReader(stream):
                    if row["table"] not in tables:
                        raise ContentError("Unknown table in CSV")
                    tables[row["table"]].append(json.loads(row["row_json"]))
        else:
            document = json.loads(path.read_text(encoding="utf-8-sig"))
            if document.get("schema_version") != 1:
                raise ContentError("Unsupported export schema")
            tables = document["tables"]
        self.validate_tables(tables)
        saved = self.backup()
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(
            buffer, fieldnames=["zh", "en", "abbr", "definition_zh", "definition_en"]
        )
        writer.writeheader()
        writer.writerows(tables["glossary"])
        payloads = {
            "glossary.csv": buffer.getvalue(),
            **{
                f"{name}.yaml": yaml.safe_dump(tables[name], allow_unicode=True, sort_keys=False)
                for name in ("timeline", "references")
            },
        }
        originals = {name: (self.data / name).read_bytes() for name in payloads}
        try:
            for name, text in payloads.items():
                (self.data / name).write_text(text, encoding="utf-8")
            result = self.check()
            if not result["passed"]:
                raise ContentError(
                    "Imported content failed the sensitive-content gate", "SENSITIVE_CONTENT"
                )
        except Exception:
            for name, content in originals.items():
                (self.data / name).write_bytes(content)
            raise
        return {"rows_imported": sum(map(len, tables.values())), "backup": saved["path"]}

    def backup(self) -> dict:
        directory = self.data / "backups"
        directory.mkdir(exist_ok=True, parents=True)
        stamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d_%H%M%S_%f")
        path = directory / f"knowledge_{stamp}.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for base, prefix in ((self.docs, "docs"), (self.data, "data")):
                for file in sorted(base.rglob("*")):
                    rel = file.relative_to(base)
                    if file.is_file() and not file.is_symlink() and "backups" not in rel.parts:
                        archive.write(file, str(Path(prefix) / rel))
            override = self.config.get("theme", {}).get("custom_dir")
            if override:
                directory = (self.root / override).resolve()
                for file in sorted(directory.rglob("*")):
                    if file.is_file() and not file.is_symlink():
                        archive.write(file, str(Path(override) / file.relative_to(directory)))
            archive.write(self.config_path, "mkdocs.yml")
            archive.write(self.rules_path, "sensitive.yaml")
        return {"path": str(path)}
