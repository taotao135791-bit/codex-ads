"""Regression tests for optimizer style-learning safety rules."""

from __future__ import annotations


def _read(repo_root, relative_path: str) -> str:
    return (repo_root / relative_path).read_text(encoding="utf-8").lower()


def test_main_skill_documents_style_learning_modes(repo_root):
    text = (
        _read(repo_root, "ads/SKILL.md")
        + "\n"
        + _read(repo_root, "ads/references/orchestrator.md")
    )

    required = [
        "experience-based style learning",
        "style_learning_mode",
        "suggest_only",
        "auto_append_anonymized",
        "do not overwrite",
        "manual rules win",
        "learned style rules",
        "never store real client names",
    ]

    missing = [phrase for phrase in required if phrase not in text]
    assert not missing, "missing optimizer style-learning rules: " + ", ".join(missing)


def test_chinese_docs_explain_style_learning_safety(repo_root):
    readme = _read(repo_root, "README.md")
    quickstart = _read(repo_root, "QUICKSTART.zh-CN.md")
    combined = readme + "\n" + quickstart

    required = [
        "投手风格学习模式",
        "suggest_only",
        "auto_append_anonymized",
        "手动填写的规则永远优先",
        "不能覆盖我手动填写的规则",
        "不保存客户名",
        "账号 id",
        "具体消耗",
    ]

    missing = [phrase for phrase in required if phrase not in combined]
    assert not missing, "missing Chinese style-learning guidance: " + ", ".join(missing)
