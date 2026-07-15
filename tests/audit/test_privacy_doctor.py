"""Redacted privacy scan behavior and current-tree release gate."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import privacy_doctor  # noqa: E402
from privacy_doctor import build_report  # noqa: E402


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def test_current_repository_tree_has_no_high_confidence_privacy_findings(repo_root):
    report = build_report(repo_root, history=False)

    assert report["status"] == "PASS"
    assert report["findings"] == []


def test_tree_finding_is_redacted_and_nonzero(tmp_path):
    _git(tmp_path, "init", "-q")
    token = "ghp_" + "A" * 36
    (tmp_path / "unsafe.txt").write_text(token, encoding="utf-8")

    report = build_report(tmp_path, history=False)
    serialized = json.dumps(report)

    assert report["status"] == "FAIL"
    assert report["findings"][0]["kind"] == "github-token"
    assert token not in serialized


def test_exact_synthetic_refresh_token_digest_can_be_allowlisted_without_raw_value(
    tmp_path, monkeypatch
):
    _git(tmp_path, "init", "-q")
    token = "1//" + "SyntheticRefreshFixture" + "9" * 12
    digest = hashlib.sha256(token.encode("ascii")).hexdigest()
    monkeypatch.setattr(privacy_doctor, "_SAFE_PLACEHOLDER_SHA256", {digest})
    (tmp_path / "fixture.txt").write_text(
        "refresh_token=" + token,
        encoding="utf-8",
    )

    report = build_report(tmp_path, history=False)

    assert report["status"] == "PASS"
    assert report["findings"] == []


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs Windows privileges")
def test_tree_scans_symlink_target_without_following_it(tmp_path):
    _git(tmp_path, "init", "-q")
    token = "ghp_" + "L" * 36
    home_path = "/" + "Users/private-person/" + token
    os.symlink(home_path, tmp_path / "leaked-link")

    report = build_report(tmp_path, history=False)
    serialized = json.dumps(report)
    kinds = {finding["kind"] for finding in report["findings"]}

    assert {"github-token", "mac-home-path"}.issubset(kinds)
    assert token not in serialized
    assert home_path not in serialized


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs Windows privileges")
def test_symlink_target_path_policy_blocks_private_workspace_reference(tmp_path):
    _git(tmp_path, "init", "-q")
    private_label = "private-client-label"
    target = f"../../workspaces/{private_label}/raw.csv"
    os.symlink(target, tmp_path / "workspace-link")

    report = build_report(tmp_path, history=False)
    serialized = json.dumps(report)

    assert any(
        finding["kind"] == "private-workspace-path" for finding in report["findings"]
    )
    assert private_label not in serialized


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs Windows privileges")
def test_history_does_not_cache_across_symlink_and_regular_file_modes(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "test")
    _git(tmp_path, "config", "user.email", "test@users.noreply.github.com")
    target = "workspaces/private-client-label/raw.csv"
    alias = tmp_path / "alias"
    os.symlink(target, alias)
    _git(tmp_path, "add", "alias")
    _git(tmp_path, "commit", "-qm", "symlink version")
    alias.unlink()
    alias.write_text(target, encoding="utf-8")
    _git(tmp_path, "add", "alias")
    _git(tmp_path, "commit", "-qm", "regular version")

    report = build_report(tmp_path, history=True)

    assert any(
        finding["kind"] == "private-workspace-path" for finding in report["findings"]
    )


def test_history_flags_identity_and_bytecode_without_printing_email(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "Anonymous Test")
    unsafe_email = "private" + "@" + "mail.invalid"
    _git(tmp_path, "config", "user.email", unsafe_email)
    cache = tmp_path / "scripts" / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "sample.pyc").write_bytes(b"compiled")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "fixture")

    report = build_report(tmp_path, history=True)
    serialized = json.dumps(report)
    kinds = {finding["kind"] for finding in report["findings"]}

    assert {"non-noreply-identity", "python-bytecode"}.issubset(kinds)
    assert unsafe_email not in serialized


def test_history_scans_commit_messages_without_echoing_values(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "test")
    _git(tmp_path, "config", "user.email", "test@users.noreply.github.com")
    (tmp_path / "safe.txt").write_text("safe\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    token = "ghp_" + "Z" * 36
    email = "private-person" + "@" + "mail.invalid"
    developer_token = "DevToken" + "9A" * 8
    refresh_token = "1//" + "RefreshToken9" * 3
    client_secret = "ClientSecret" + "9X" * 8
    access_token = "EAA" + "CommitMetaAccess9" * 2
    message = (
        f"remove {token} owned by {email}\n"
        + '{"'
        + "developer_token"
        + f'":"{developer_token}","'
        + "refresh_token"
        + f'":"{refresh_token}","'
        + "client_secret"
        + f'":"{client_secret}"}}\n'
        + f"GOOGLE_ADS_ACCESS_TOKEN={access_token}"
    )
    _git(tmp_path, "commit", "-qm", message)

    report = build_report(tmp_path, history=True)
    serialized = json.dumps(report)
    message_findings = {
        finding["kind"]
        for finding in report["findings"]
        if finding["path"] == "<commit-message>"
    }

    assert {
        "github-token",
        "non-placeholder-email",
        "google-ads-developer-token",
        "oauth-refresh-token",
        "oauth-client-secret",
        "access-token",
        "meta-access-token",
    }.issubset(message_findings)
    assert token not in serialized
    assert email not in serialized
    assert developer_token not in serialized
    assert refresh_token not in serialized
    assert client_secret not in serialized
    assert access_token not in serialized


def test_history_scans_annotated_tag_identity_and_message_without_echoing(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "test")
    _git(tmp_path, "config", "user.email", "test@users.noreply.github.com")
    (tmp_path / "safe.txt").write_text("safe\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "safe commit")
    private_email = "tag-owner" + "@" + "mail.invalid"
    _git(tmp_path, "config", "user.name", "Private Tag Owner")
    _git(tmp_path, "config", "user.email", private_email)
    token = "ghp_" + "T" * 36
    _git(tmp_path, "tag", "-a", "v1.0.0", "-m", f"release {token}")

    report = build_report(tmp_path, history=True)
    serialized = json.dumps(report)
    kinds_by_path = {finding["path"]: finding["kind"] for finding in report["findings"]}

    assert kinds_by_path["<tag-metadata>"] in {
        "non-noreply-identity",
        "non-placeholder-email",
    }
    assert any(
        finding["path"] == "<tag-message>" and finding["kind"] == "github-token"
        for finding in report["findings"]
    )
    assert private_email not in serialized
    assert token not in serialized


def test_history_recursively_scans_an_annotated_tag_pointing_to_a_tag(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "test")
    _git(tmp_path, "config", "user.email", "test@users.noreply.github.com")
    (tmp_path / "safe.txt").write_text("safe\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "safe commit")

    private_email = "nested-tag-owner" + "@" + "mail.invalid"
    token = "ghp_" + "N" * 36
    _git(tmp_path, "config", "user.name", "Nested Private Owner")
    _git(tmp_path, "config", "user.email", private_email)
    _git(tmp_path, "tag", "-a", "inner-private", "-m", f"inner {token}")
    _git(tmp_path, "config", "user.name", "test")
    _git(tmp_path, "config", "user.email", "test@users.noreply.github.com")
    _git(tmp_path, "tag", "-a", "v1.0.0", "inner-private", "-m", "safe outer")
    _git(tmp_path, "tag", "-d", "inner-private")

    report = build_report(tmp_path, history=True)
    serialized = json.dumps(report)

    assert any(
        finding["path"] == "<tag-message>" and finding["kind"] == "github-token"
        for finding in report["findings"]
    )
    assert any(
        finding["path"] == "<tag-metadata>"
        and finding["kind"] == "non-noreply-identity"
        for finding in report["findings"]
    )
    assert private_email not in serialized
    assert token not in serialized


def test_history_scans_tag_objects_reachable_only_from_a_custom_ref(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "test")
    _git(tmp_path, "config", "user.email", "test@users.noreply.github.com")
    (tmp_path / "safe.txt").write_text("safe\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "safe commit")
    token = "ghp_" + "R" * 36
    _git(tmp_path, "tag", "-a", "temporary-tag", "-m", f"private {token}")
    tag_object = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "temporary-tag^{tag}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    _git(tmp_path, "update-ref", "refs/archive/private-release", tag_object)
    _git(tmp_path, "tag", "-d", "temporary-tag")

    report = build_report(tmp_path, history=True)
    serialized = json.dumps(report)

    assert any(
        finding["path"] == "<tag-message>" and finding["kind"] == "github-token"
        for finding in report["findings"]
    )
    assert token not in serialized


def test_noreply_email_does_not_hide_a_real_identity_name(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "Private Person")
    _git(tmp_path, "config", "user.email", "safe-handle@users.noreply.github.com")
    (tmp_path / "safe.txt").write_text("safe\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "safe content")

    report = build_report(tmp_path, history=True)

    assert any(
        finding["kind"] == "non-pseudonymous-identity-name"
        and finding["path"] == "<commit-metadata>"
        for finding in report["findings"]
    )


@pytest.mark.parametrize(
    ("kind", "content_factory"),
    [
        ("openai-api-key", lambda value: f"OPENAI_API_KEY={value}\n"),
        ("bearer-token", lambda value: f"Authorization: Bearer {value}\n"),
        ("oauth-client-secret", lambda value: f"oauth_client_secret={value}\n"),
        (
            "google-ads-developer-token",
            lambda value: f"GOOGLE_ADS_DEVELOPER_TOKEN={value}\n",
        ),
        ("oauth-refresh-token", lambda value: f"OAUTH_REFRESH_TOKEN={value}\n"),
        ("access-token", lambda value: f"META_ACCESS_TOKEN={value}\n"),
        (
            "google-ads-customer-id",
            lambda value: f"GOOGLE_ADS_LOGIN_CUSTOMER_ID={value}\n",
        ),
        ("meta-ad-account-id", lambda value: f"META_AD_ACCOUNT_ID={value}\n"),
        ("mmp-token", lambda value: f"APPSFLYER_DEV_KEY={value}\n"),
    ],
)
def test_advertising_secrets_and_identifiers_are_redacted(
    tmp_path, kind, content_factory
):
    _git(tmp_path, "init", "-q")
    values = {
        "openai-api-key": "sk-proj-" + "aB9_" * 8,
        "bearer-token": "ey" + "Jprivate" * 6,
        "oauth-client-secret": "oauth" + "Secret9" * 4,
        "google-ads-developer-token": "DevToken" + "8B" * 8,
        "oauth-refresh-token": "1//" + "RefreshToken8" * 3,
        "access-token": "EAAB" + "MetaAccess8" * 3,
        "google-ads-customer-id": "-".join(("987", "654", "3210")),
        "meta-ad-account-id": "act_" + "9081726354",
        "mmp-token": "mmp" + "PrivateToken9" * 2,
    }
    value = values[kind]
    (tmp_path / "unsafe.txt").write_text(content_factory(value), encoding="utf-8")

    report = build_report(tmp_path, history=False)
    serialized = json.dumps(report)

    assert kind in {finding["kind"] for finding in report["findings"]}
    assert value not in serialized


def test_quoted_json_secret_keys_and_nonexact_placeholder_substrings_are_detected(
    tmp_path,
):
    _git(tmp_path, "init", "-q")
    secret_value = "example_live_secret_material_" + "9X" * 4
    customer_id = "-".join(("987", "654", "3210"))
    mmp_token = "MmpPrivate" + "9X" * 2
    developer_token = "Developer" + "7Y" * 2
    refresh_token = "1//" + "RefreshPrivate7" * 2
    access_value = "EAAB" + "MetaPrivate7" * 2
    payload = (
        '{"'
        + "client_secret"
        + f'":"{secret_value}","'
        + "login_customer_id"
        + f'":"{customer_id}","'
        + "appsflyer_dev_key"
        + f'":"{mmp_token}","'
        + "developer_token"
        + f'":"{developer_token}","'
        + "refresh_token"
        + f'":"{refresh_token}","'
        + "access_token"
        + f'":"{access_value}"}}'
    )
    (tmp_path / "unsafe.json").write_text(payload, encoding="utf-8")

    report = build_report(tmp_path, history=False)
    serialized = json.dumps(report)
    kinds = {finding["kind"] for finding in report["findings"]}

    assert {
        "oauth-client-secret",
        "google-ads-customer-id",
        "mmp-token",
        "google-ads-developer-token",
        "oauth-refresh-token",
        "access-token",
    }.issubset(kinds)
    for value in (
        secret_value,
        customer_id,
        mmp_token,
        developer_token,
        refresh_token,
        access_value,
    ):
        assert value not in serialized


@pytest.mark.parametrize(
    ("kind", "key"),
    [
        ("oauth-client-secret", "GOOGLE_ADS_CLIENT_SECRET"),
        ("oauth-refresh-token", "GOOGLE_ADS_REFRESH_TOKEN"),
        ("access-token", "GOOGLE_ADS_ACCESS_TOKEN"),
        ("access-token", "TIKTOK_ACCESS_TOKEN"),
    ],
)
def test_platform_prefixed_credential_keys_are_detected(tmp_path, kind, key):
    _git(tmp_path, "init", "-q")
    value = "PrivateCredential" + "8Z" * 8
    (tmp_path / "unsafe.env.txt").write_text(f"{key}={value}\n", encoding="utf-8")

    report = build_report(tmp_path, history=False)
    serialized = json.dumps(report)

    assert kind in {finding["kind"] for finding in report["findings"]}
    assert value not in serialized


@pytest.mark.parametrize(
    ("kind", "key", "value"),
    [
        ("oauth-client-secret", "client secret", "Private:Client|Secret" * 2),
        ("oauth-client-secret", "OAuth client secret", "OAuth:Private|Secret" * 2),
        ("oauth-client-secret", "Meta App Secret", "Meta:Private|Secret" * 2),
        ("access-token", "META_ACCESS_TOKEN", "EAAabc|Private:Access" * 2),
    ],
)
def test_spaced_secret_keys_and_opaque_token_characters_are_detected(
    tmp_path, kind, key, value
):
    _git(tmp_path, "init", "-q")
    (tmp_path / "unsafe.txt").write_text(f"{key}: {value}\n", encoding="utf-8")

    report = build_report(tmp_path, history=False)
    serialized = json.dumps(report)

    assert kind in {finding["kind"] for finding in report["findings"]}
    assert value not in serialized


def test_standalone_google_refresh_and_meta_access_tokens_are_detected(tmp_path):
    _git(tmp_path, "init", "-q")
    refresh_token = "1//" + "StandaloneRefresh8" * 2
    meta_token = "EAA" + "StandaloneMeta8" * 3
    (tmp_path / "unsafe.txt").write_text(
        f"{refresh_token}\n{meta_token}\n", encoding="utf-8"
    )

    report = build_report(tmp_path, history=False)
    serialized = json.dumps(report)
    kinds = {finding["kind"] for finding in report["findings"]}

    assert {"google-oauth-refresh-token", "meta-access-token"}.issubset(kinds)
    assert refresh_token not in serialized
    assert meta_token not in serialized


def test_payload_substring_does_not_allowlist_real_credential_shapes(tmp_path):
    _git(tmp_path, "init", "-q")
    bearer = "realprefix123.payload.realsuffix456789"
    secret_value = "clientprefix.payload.clientsuffix987654"
    access_value = "accessprefix.payload.accesssuffix987654"
    (tmp_path / "unsafe.txt").write_text(
        "\n".join(
            (
                f"Authorization: Bearer {bearer}",
                f"client_secret={secret_value}",
                f"META_ACCESS_TOKEN={access_value}",
            )
        ),
        encoding="utf-8",
    )

    report = build_report(tmp_path, history=False)
    serialized = json.dumps(report)
    kinds = {finding["kind"] for finding in report["findings"]}

    assert {"bearer-token", "oauth-client-secret", "access-token"}.issubset(kinds)
    for value in (bearer, secret_value, access_value):
        assert value not in serialized


@pytest.mark.parametrize(
    ("kind", "key"),
    [
        ("oauth-client-secret", "oauthClientSecret"),
        ("oauth-client-secret", "googleAdsClientSecret"),
        ("google-ads-developer-token", "googleAdsDeveloperToken"),
        ("oauth-refresh-token", "googleAdsRefreshToken"),
        ("access-token", "metaAccessToken"),
        ("access-token", "tiktokAccessToken"),
        ("mmp-token", "appsflyerDevKey"),
        ("mmp-token", "adjustAppToken"),
    ],
)
def test_camel_case_quoted_credential_keys_are_detected(tmp_path, kind, key):
    _git(tmp_path, "init", "-q")
    value = "CamelPrivateCredential" + "6Q" * 6
    payload = '{"' + key + f'":"{value}"}}'
    (tmp_path / "unsafe.json").write_text(payload, encoding="utf-8")

    report = build_report(tmp_path, history=False)
    serialized = json.dumps(report)

    assert kind in {finding["kind"] for finding in report["findings"]}
    assert value not in serialized


def test_common_private_key_headers_aws_sts_and_credentialed_urls_are_detected(
    tmp_path,
):
    _git(tmp_path, "init", "-q")
    aws_key = "ASIA" + "7A" * 8
    encrypted_pem = "-----BEGIN " + "ENCRYPTED PRIVATE KEY-----"
    pgp_pem = "-----BEGIN " + "PGP PRIVATE KEY BLOCK-----"
    userinfo = "private-user:private-pass"
    host = "db" + ".internal"
    database_url = "postgresql" + "://" + userinfo + "@" + host + "/app"
    (tmp_path / "unsafe.txt").write_text(
        "\n".join((aws_key, encrypted_pem, pgp_pem, database_url)),
        encoding="utf-8",
    )

    report = build_report(tmp_path, history=False)
    serialized = json.dumps(report)
    kinds = {finding["kind"] for finding in report["findings"]}

    assert {"aws-access-key", "private-key", "credentialed-url"}.issubset(kinds)
    for value in (aws_key, encrypted_pem, pgp_pem, database_url):
        assert value not in serialized


@pytest.mark.parametrize("platform", ["mac", "linux", "windows", "windows-json"])
def test_home_paths_without_trailing_separator_are_detected(tmp_path, platform):
    _git(tmp_path, "init", "-q")
    if platform == "mac":
        value = "/" + "Users/privateperson"
        expected_kind = "mac-home-path"
        content = f"HOME={value}"
    elif platform == "linux":
        value = "/" + "home/privateperson"
        expected_kind = "linux-home-path"
        content = f"HOME={value}"
    else:
        value = "C:" + "\\Users\\privateperson"
        expected_kind = "windows-home-path"
        content = json.dumps({"home": value}) if platform == "windows-json" else value
    (tmp_path / "unsafe.txt").write_text(content, encoding="utf-8")

    report = build_report(tmp_path, history=False)
    serialized = json.dumps(report)

    assert expected_kind in {finding["kind"] for finding in report["findings"]}
    assert value not in serialized


def test_placeholder_identifiers_and_explicit_synthetic_allowlist_do_not_fail(
    tmp_path,
):
    _git(tmp_path, "init", "-q")
    placeholder_customer = "-".join(("123", "456", "7890"))
    placeholder_meta = "act_" + "1234567890"
    allowlisted_customer = "-".join(("987", "654", "3210"))
    (tmp_path / "public-example.txt").write_text(
        "\n".join(
            (
                f"GOOGLE_ADS_LOGIN_CUSTOMER_ID={placeholder_customer}",
                f"META_AD_ACCOUNT_ID={placeholder_meta}",
                "MMP_TOKEN=your_token_here",
                f"GOOGLE_ADS_CUSTOMER_ID={allowlisted_customer} # privacy-doctor: allow",
            )
        ),
        encoding="utf-8",
    )

    report = build_report(tmp_path, history=False)

    assert report["status"] == "PASS"
    assert report["findings"] == []


def test_environment_and_private_workspace_paths_are_release_findings(tmp_path):
    _git(tmp_path, "init", "-q")
    workspace_file = tmp_path / "workspaces" / "client-a" / "input" / "raw.csv"
    workspace_file.parent.mkdir(parents=True)
    workspace_file.write_text("spend,installs\n10,2\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SAFE_TEST=1\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text("SAFE_TEST=1\n", encoding="utf-8")
    (tmp_path / ".env.production").write_text("SAFE_TEST=1\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("SAFE_TEST=placeholder\n", encoding="utf-8")
    (tmp_path / "UAC-INPUT.yaml").write_text("scope: {}\n", encoding="utf-8")

    report = build_report(tmp_path, history=False)
    kinds = {finding["kind"] for finding in report["findings"]}

    assert {
        "environment-file",
        "private-workspace-path",
        "root-private-project-file",
    }.issubset(kinds)
    environment_paths = {
        finding["path"]
        for finding in report["findings"]
        if finding["kind"] == "environment-file"
    }
    assert len(environment_paths) == 3
    assert all(path.startswith("<redacted-path:") for path in environment_paths)


def test_nested_private_paths_and_project_filenames_are_detected_and_redacted(
    tmp_path,
):
    _git(tmp_path, "init", "-q")
    private_label = "client-secret-name"
    raw = tmp_path / "archive" / "workspaces" / private_label / "raw.csv"
    raw.parent.mkdir(parents=True)
    raw.write_text("spend,installs\n10,2\n", encoding="utf-8")
    misplaced = tmp_path / "examples" / "client" / "UAC-INPUT.yaml"
    misplaced.parent.mkdir(parents=True)
    misplaced.write_text("scope: {}\n", encoding="utf-8")
    context = tmp_path / "client-copy" / "project-context.yaml"
    context.parent.mkdir()
    context.write_text("privacy: {}\n", encoding="utf-8")
    draft = context.parent / "UAC-INPUT.draft.yaml"
    draft.write_text("scope: {}\n", encoding="utf-8")

    report = build_report(tmp_path, history=False)
    serialized = json.dumps(report)

    assert private_label not in serialized
    assert any(
        finding["kind"] == "private-workspace-path"
        and finding["path"].startswith("<redacted-path:")
        for finding in report["findings"]
    )
    detected_project_files = [
        finding["path"]
        for finding in report["findings"]
        if finding["kind"] == "root-private-project-file"
    ]
    assert len(detected_project_files) == 3
    assert all(path.startswith("<redacted-path:") for path in detected_project_files)


def test_secret_in_filename_is_detected_but_the_path_is_redacted(tmp_path):
    _git(tmp_path, "init", "-q")
    token = "ghp_" + "P" * 36
    (tmp_path / token).write_text("safe content\n", encoding="utf-8")

    report = build_report(tmp_path, history=False)
    serialized = json.dumps(report)

    assert any(
        finding["kind"] == "github-token"
        and finding["path"].startswith("<redacted-path:")
        for finding in report["findings"]
    )
    assert token not in serialized


@pytest.mark.skipif(os.name == "nt", reason="angle brackets are invalid in filenames")
def test_angle_brackets_do_not_bypass_sensitive_filename_redaction(tmp_path):
    _git(tmp_path, "init", "-q")
    token = "ghp_" + "V" * 36
    (tmp_path / f"<{token}>").write_text("safe content\n", encoding="utf-8")

    report = build_report(tmp_path, history=False)
    serialized = json.dumps(report)

    assert any(
        finding["kind"] == "github-token"
        and finding["path"].startswith("<redacted-path:")
        for finding in report["findings"]
    )
    assert token not in serialized


@pytest.mark.parametrize(
    "filename",
    [
        "UAC-INPUT.yaml",
        "UAC-INPUT.yml",
        "UAC-INPUT.json",
        "ADS-EXPERIMENTS.yaml",
        "ADS-EXPERIMENTS.yml",
        "ADS-EXPERIMENTS.json",
    ],
)
def test_all_legacy_root_private_file_variants_are_detected(tmp_path, filename):
    _git(tmp_path, "init", "-q")
    (tmp_path / filename).write_text("{}\n", encoding="utf-8")

    report = build_report(tmp_path, history=False)

    assert any(
        finding["kind"] == "root-private-project-file"
        and finding["path"].startswith("<redacted-path:")
        for finding in report["findings"]
    )


def test_public_replay_requires_explicit_anonymized_synthetic_markers(tmp_path):
    _git(tmp_path, "init", "-q")
    snapshot = tmp_path / "examples" / "replays" / "candidate" / "snapshot-before.yaml"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text("schema_version: '1.0'\n", encoding="utf-8")

    unsafe = build_report(tmp_path, history=False)

    assert "public-replay-anonymization-missing" in {
        finding["kind"] for finding in unsafe["findings"]
    }

    snapshot.write_text(
        """schema_version: "1.0"
# public_example: true
# synthetic_values: true
# contains_real_account_data: false
""",
        encoding="utf-8",
    )

    commented_only = build_report(tmp_path, history=False)

    assert "public-replay-anonymization-missing" in {
        finding["kind"] for finding in commented_only["findings"]
    }

    snapshot.write_text(
        """schema_version: "1.0"
notes: |
  public_example: true
  synthetic_values: true
  contains_real_account_data: false
""",
        encoding="utf-8",
    )

    literal_block = build_report(tmp_path, history=False)

    assert "public-replay-anonymization-missing" in {
        finding["kind"] for finding in literal_block["findings"]
    }

    snapshot.write_text(
        """schema_version: "1.0"
anonymization:
  public_example: true
  public_example: false
  synthetic_values: true
  contains_real_account_data: false
""",
        encoding="utf-8",
    )

    duplicate_key = build_report(tmp_path, history=False)

    assert "public-replay-anonymization-missing" in {
        finding["kind"] for finding in duplicate_key["findings"]
    }

    snapshot.write_text(
        """schema_version: "1.0"
anonymization:
  public_example: true
  synthetic_values: true
  contains_real_account_data: false
anonymization: {public_example: false, synthetic_values: false, contains_real_account_data: true}
""",
        encoding="utf-8",
    )

    duplicate_top_level = build_report(tmp_path, history=False)

    assert "public-replay-anonymization-missing" in {
        finding["kind"] for finding in duplicate_top_level["findings"]
    }

    snapshot.write_text(
        """schema_version: "1.0"
anonymization:
  public_example: true
  synthetic_values: true
  contains_real_account_data: false
""",
        encoding="utf-8",
    )

    safe = build_report(tmp_path, history=False)

    assert safe["status"] == "PASS"


def test_noncanonical_or_private_replay_paths_are_not_publicly_allowlisted(tmp_path):
    _git(tmp_path, "init", "-q")
    private_label = "private-client-label"
    for relative in (
        Path("archive") / "replays" / private_label / "snapshot-before.yaml",
        Path("Examples") / "Replays" / private_label / "snapshot-before.yaml",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True)
        path.write_text("schema_version: '1.0'\n", encoding="utf-8")

    report = build_report(tmp_path, history=False)
    serialized = json.dumps(report)

    assert "private-replay-outside-workspace" in {
        finding["kind"] for finding in report["findings"]
    }
    assert private_label not in serialized
