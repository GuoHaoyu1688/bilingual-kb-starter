# Version 0.1.0

English-first bilingual MkDocs knowledge base with glossary, timeline and a publication content gate.

Local verification: 20 tests passed; 92% measured coverage; Ruff lint and formatting checks passed. README quick start was exercised with fictional data.

## Known limitations

The Chinese locale contains English placeholders with pending-translation banners. The gate checks configured text patterns, not binary attachments or factual accuracy. References use YAML only. Structured-data import rolls back ordinary errors but is not crash-atomic across files. MkDocs 1.x is required.

See README and AGENTS.md for installation, configuration, machine-readable CLI/MCP interfaces and operational boundaries.
