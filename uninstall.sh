#!/usr/bin/env bash
set -euo pipefail

# Codex Ads Uninstaller (multi-host)
#
# Usage:
#   bash uninstall.sh                  # default: --target=codex
#   bash uninstall.sh --target=codex
#
# Removes every directory under <SKILL_BASE>/ads-* plus the orchestrator at
# <SKILL_BASE>/ads, plus the bundled audit + creative agents under <AGENT_DIR>.
# Uses glob discovery so new sub-skills don't require uninstaller updates.

resolve_target_paths() {
    local target="$1"
    case "$target" in
        codex)    SKILL_BASE="${HOME}/.codex/skills";                                    AGENT_DIR="${HOME}/.codex/agents" ;;
        cursor)   SKILL_BASE="${HOME}/.cursor/extensions/codex-ads/skills";             AGENT_DIR="${HOME}/.cursor/extensions/codex-ads/agents" ;;
        windsurf) SKILL_BASE="${HOME}/.windsurf/skills";                                 AGENT_DIR="${HOME}/.windsurf/agents" ;;
        gemini)   SKILL_BASE="${HOME}/.gemini/extensions/codex-ads/skills";             AGENT_DIR="${HOME}/.gemini/extensions/codex-ads/agents" ;;
        goose)    SKILL_BASE="${HOME}/.config/goose/skills";                             AGENT_DIR="${HOME}/.config/goose/agents" ;;
        *)        return 1 ;;
    esac
    return 0
}

main() {
    local TARGET="codex"

    while [ $# -gt 0 ]; do
        case "$1" in
            --target=*) TARGET="${1#*=}" ;;
            --target)   shift; [ $# -eq 0 ] && { echo "✗ --target requires a value" >&2; exit 1; }; TARGET="$1" ;;
            --help|-h)
                echo "Usage: bash uninstall.sh [--target=<codex|cursor|windsurf|gemini|goose>]"
                exit 0
                ;;
            *) echo "✗ Unknown argument: $1" >&2; exit 1 ;;
        esac
        shift
    done

    if ! resolve_target_paths "$TARGET"; then
        echo "✗ Unknown target: $TARGET" >&2
        echo "  Valid targets: codex, cursor, windsurf, gemini, goose" >&2
        exit 1
    fi

    echo "→ Uninstalling Codex Ads from ${SKILL_BASE} and ${AGENT_DIR}..."

    # Remove orchestrator (with references + scripts)
    rm -rf "${SKILL_BASE}/ads"

    # Remove all ads-* sub-skills via glob (no hardcoded list — new sub-skills
    # don't require an uninstaller update)
    if [ -d "${SKILL_BASE}" ]; then
        for d in "${SKILL_BASE}"/ads-*/; do
            [ -d "$d" ] && rm -rf "$d"
        done
    fi

    # Remove bundled audit + creative agents.
    # ⚠ Keep this list in sync with the contents of `agents/` in the repo. The
    # installer uses `cp agents/*.md` so any new agent file added there must
    # also be appended below. The previous list contained non-existent
    # entries (audit-amazon, audit-attribution, audit-server-side) and missed
    # the actual shipped agents — fixed in v1.7.1.
    for agent in \
        audit-budget audit-compliance audit-creative audit-google audit-meta audit-tracking \
        copy-writer creative-strategist format-adapter visual-designer; do
        rm -f "${AGENT_DIR}/${agent}.md"
    done

    echo "✓ Codex Ads uninstalled."
}

main "$@"
