import shutil
from pathlib import Path

import pytest

from bilingual_kb_starter.core.content import KnowledgeBase

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def kb(tmp_path):
    for name in ["mkdocs.yml", "sensitive.yaml"]:
        shutil.copy2(ROOT / name, tmp_path / name)
    for name in ["docs", "data", "overrides"]:
        shutil.copytree(
            ROOT / name,
            tmp_path / name,
            ignore=shutil.ignore_patterns("backups", "RELEASE.md", "*.zip"),
        )
    return KnowledgeBase(tmp_path / "mkdocs.yml")
