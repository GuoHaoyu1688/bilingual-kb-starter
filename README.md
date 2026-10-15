# Bilingual Knowledge Base Starter

An English-first MkDocs Material template with two locale routes, a searchable glossary, an interactive timeline, citations, and a mandatory sensitive-content gate. Python 3.11+. All sample prose is English and fictional. The Chinese locale remains a clearly marked translation slot; Chinese glossary terms exercise the bilingual search capability.

Code: **MIT**. Documentation and sample content: **[CC BY 4.0](LICENSE-CONTENT.md)**.

## Quick start

```sh
python3 -m pip install -r requirements.txt
kbtool check --json
mkdocs serve
```

Open `http://127.0.0.1:8000/bilingual-kb-starter/` (MkDocs redirects the root there). Installation downloads dependencies; building, previewing and searching the installed site need no API key or external service. Fonts and search assets are hosted with the site. The source-link template disables Material's automatic GitHub statistics requests. Use the language selector to open the secondary `/zh/` route; the interface remains English.

The template topic is **industrial water treatment (placeholder)**. Principles, equipment, operations and diagnostics contain structure only, without real technical data or operating instructions. Replace placeholders with reviewed, public, cited material.

## Content workflow

```sh
kbtool new-page example-concept --section principles --json
kbtool missing-translations --json
kbtool build --json
```

Add new pages to `nav` in `mkdocs.yml`. `new-page` refuses to overwrite either locale. It creates a complete English slot and a secondary slot with `translation_status: pending`. Change that field to `complete` only after replacing the placeholder. A missing secondary page falls back to English and receives the same pending banner. `missing-translations` reports both absent and pending pages.

Edit these source files; build generates matching pages in both locale directories:

| File | Format and result |
| --- | --- |
| `data/glossary.csv` | `zh,en,abbr,definition_zh,definition_en`; searchable glossary, compatible with bilingual-glossary exports. |
| `data/timeline.yaml` | List of `date`, `title`, `description`; filterable, expandable timeline. |
| `data/references.yaml` | List of unique `id`, `author`, `year`, `title`, optional HTTP(S) `url`; reference list. |

Cite a reference as `[@example-handbook]`. Unknown citation keys stop the build. The plugin links the first body-text occurrence of a term, abbreviation or Chinese equivalent on each page; headings, existing links and code are excluded. Set `auto_link: false` under `kb-gate` to disable automatic term linking. Glossary definitions are not automatically linked to themselves.

Material's built-in search uses English and Chinese language support. The installed `jieba` tokenizer segments Chinese index text. Search for `示例` to exercise the fictional sample. All custom timeline/glossary JavaScript has no external dependencies.

## Publication gate

`kbtool check` scans textual files under `docs/` and `data/`. The configured rules in `sensitive.yaml` match keywords, phone-shaped strings, email addresses, identity-shaped numbers and internal-code patterns. It reports relative file paths, line numbers and rule names. It does not echo matched line content. A hit exits with code 1.

The gate runs in **the CLI, the MkDocs plugin, and CI**. Calling `mkdocs build` directly still enforces it. A reviewed same-line `<!-- kb-allow -->` comment permits an intentional exception and records it in `allowed_lines`. Tests create fictional blocked values only inside temporary directories.

The scanner rejects symbolic links. It scans Markdown, text, YAML, CSV, JSON, HTML, BibTeX, JavaScript and CSS; it does not OCR images or inspect arbitrary binary attachments. Runtime `data/backups/` is excluded. Configured patterns are a review aid, not a proof that content is public. Inspect attached files and citations before sharing.

## Commands and storage

| Command | Behavior |
| --- | --- |
| `check` | Scan configured text sources; nonzero on findings. |
| `missing-translations` | List missing/pending locale pages. |
| `new-page SLUG --section PATH --title TITLE` | Create a safe paired page without overwriting. |
| `build --out DIRECTORY` | Gate and strict static build. |
| `serve --host 127.0.0.1 --port 8000` | Gate and local development server. |
| `export --format json\|csv --out FILE` | Export all three structured data tables. |
| `import FILE --yes` | Validate, back up, replace structured data; reject and roll back gated content. |
| `backup` | Dated ZIP of docs, structured data, theme overrides, config and rules. |

Global options work before or after commands: `--config PATH` (default `mkdocs.yml`), `--data-dir PATH` (then `KBTOOL_DATA_DIR`, then configured data directory), `--json`, `--quiet`, `--version`. Paths inside MkDocs configuration resolve relative to that file. An explicit data directory resolves relative to the current shell directory. This file-based template does not need a database or MCP server.

With `--json`, stdout contains one `{ "ok": true, "data": ..., "warnings": [] }` envelope. Failures contain `{ "ok": false, "error": { "code": "...", "message": "..." } }`; gate failures also include findings. Build logs go to stderr. Exit codes: 0 success, 1 operation/gate failure, 2 invalid input or missing confirmation, 3 missing required configuration. The long-running `serve` command emits its final envelope when it exits.

JSON exports use schema version 1. CSV snapshots use `table,row_json` rows, UTF-8 BOM by default (`--no-bom` disables it); this snapshot format is distinct from the direct five-column glossary source. Backups use Asia/Shanghai timestamps and omit earlier backups. Import requires `--yes`, validates before replacing, and restores original files after an ordinary write/gate failure. It is not crash-atomic across three files. Restore a backup into an empty checkout after inspecting its paths.

## GitHub Pages

Fork the repository and update `site_url` and `repo_url` in `mkdocs.yml`. In repository **Settings → Pages → Build and deployment**, choose **GitHub Actions**. The Pages workflow runs checks, tests and a gated strict build on `main`, then deploys the artifact. Pull requests run CI only. You can also trigger deployment manually.

For a non-`main` default branch, update the workflow branch filter or merge the reviewed branch into `main`. The site is static: no comments, CMS or authentication are provided. Public deployment makes every generated page and copied attachment publicly readable.

## Development and verification

```sh
python3 -m pip install -e '.[dev]'
ruff check .
ruff format --check .
pytest -q --cov=bilingual_kb_starter
kbtool build --json
```

Tests exercise all five gate categories, reviewed exceptions, symlink rejection, paired page safety, JSON/CSV roundtrips, backup integrity, rollback, escaped generated HTML, first-use links, unknown references, locale fallback and segmented Chinese search-index content. Both `kbtool build` and direct `mkdocs build` are tested for gate enforcement. CI runs Python 3.11/3.12 on Ubuntu.

See [AGENTS.md](AGENTS.md) for noninteractive operation and [CHANGELOG.md](CHANGELOG.md) for changes. Supported versions deliberately stay on MkDocs 1.x and static-i18n 1.x. Future work: BibTeX import, per-locale editorial review metadata and optional binary attachment scanning. Current references accept YAML only.

Implementation references: [MkDocs plugins](https://www.mkdocs.org/dev-guide/plugins/), [static-i18n folder structure](https://ultrabug.github.io/mkdocs-static-i18n/setup/choosing-the-structure/), and [Material search](https://squidfunk.github.io/mkdocs-material/setup/setting-up-site-search/).
