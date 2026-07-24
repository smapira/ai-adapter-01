# LLM Tool Specification Comparison

This page compares how different AI coding tools handle the configuration categories managed by `ai-adapter`.

---

## Overview

| Feature | GitHub Copilot (Codex) | Claude Code | OpenCode | OpenAI Codex CLI | Cursor | Continue |
|---------|----------------------|-------------|----------|-----------------|--------|----------|
| **Vendor** | Microsoft (GitHub) | Anthropic | Community | OpenAI | Anysphere | Continue.dev |
| **Config directory** | `.github/` | Project root | `.opencode/` or `.github/` via symlink | `.codex/` or project root | `.cursor/` | `.continue/` |
| **Config format** | Markdown + YAML frontmatter | Markdown (`CLAUDE.md`) | JSON (`opencode.json`) | Markdown (`AGENTS.md`) + YAML | Markdown (`*.mdc`) with YAML frontmatter | JSON (`.continuerc.json`) |
| **Tool type** | VS Code extension | CLI tool (Anthropic) | Terminal AI agent | Terminal AI agent | AI-first IDE | VS Code + JetBrains extension |
| **Instruction files** | `.github/instructions/*.md`, `.github/agents/*.agent.md` | `CLAUDE.md` | `opencode.json` → `instructions` | `AGENTS.md` (hierarchical) | `.cursor/rules/*.mdc` | `.continuerc.json` → `rules` array |
| **ai-adapter support** | ✅ Full | ✅ Via `.github/` Fallback | ✅ Full (opencode subcommand) | ❌ Planned | ❌ Planned | ❌ Planned |

---

## Skill / Rules

| Aspect | GitHub Copilot | Claude Code | OpenCode | OpenAI Codex CLI | Cursor | Continue |
|--------|---------------|-------------|----------|-----------------|--------|----------|
| **Directory** | `.github/skills/` | N/A (uses `CLAUDE.md`) | `.opencode/rules/` | `~/.codex/skills/` or project-local | `.cursor/rules/` | N/A |
| **File format** | `SKILL.md` with YAML frontmatter | Single `CLAUDE.md` | Markdown files in `rules/` | `SKILL.md` with YAML frontmatter | `*.mdc` with YAML frontmatter | `.continuerc.json` → `rules` array |
| **Metadata** | ✅ `name`, `description`, `tags`, `agent` | No structured metadata | File-name based | ✅ `agents/openai.yaml` | ✅ `description`, `globs` in frontmatter | Plain text rules |
| **File globbing** | ❌ | ❌ | ❌ | ❌ | ✅ `globs` field controls which files the rule applies to | ❌ |
| **Agent binding** | ✅ `agent` field links skill to an agent | N/A | N/A | ✅ Via `agents/openai.yaml` | ❌ (rules auto-matched by globs) | ❌ |
| **Bundled resources** | ❌ | ❌ | ❌ | ✅ `scripts/`, `references/`, `assets/` | ❌ | ❌ |
| **MCP dependencies** | ❌ | ❌ | ❌ | ✅ Declared in `agents/openai.yaml` | ❌ | ❌ |
| **ai-adapter commands** | `skill add/list/get/remove/search/link-agent/get-all` | — | — | — | — | — |

### Rules File Example

**Cursor (.cursor/rules/*.mdc):**
```markdown
---
description: Frontend development rules
globs: src/**/*.{ts,tsx}
---
Follow React + TypeScript best practices.
- Use functional components with Hooks
- Style with Tailwind CSS
- Add JSDoc comments to all exported functions
```

**Continue (.continuerc.json):**
```json
{
  "rules": [
    "Project is written in TypeScript",
    "Testing uses Vitest",
    "API is built with Express + Prisma"
  ],
  "tabAutocompleteModel": {
    "title": "Tab Autocomplete",
    "provider": "anthropic",
    "model": "claude-sonnet-4"
  }
}
```

---

## Agent / Instructions

| Aspect | GitHub Copilot | Claude Code | OpenCode | OpenAI Codex CLI | Cursor | Continue |
|--------|---------------|-------------|----------|-----------------|--------|----------|
| **Primary mechanism** | `.github/agents/*.agent.md` | `CLAUDE.md` (single file) | `opencode.json` → `instructions` array | `AGENTS.md` (hierarchical, multiple files) | `.cursor/rules/*.mdc` | `.continuerc.json` → `rules` array |
| **File format** | `.agent.md` with YAML frontmatter | Plain Markdown | N/A | Plain Markdown (no frontmatter) | Markdown with YAML frontmatter | JSON string array |
| **File extensions** | `*.agent.md`, `*.md` | `CLAUDE.md` | Any referenced files | `AGENTS.md` (exact name) | `*.mdc` | `.continuerc.json` |
| **Fallback files** | `.github/copilot-instructions.md` | `.github/copilot-instructions.md` | `CLAUDE.md`, `.github/copilot-instructions.md` | Configurable fallbacks (e.g. `EXAMPLE.md`) | `.cursorrules` (legacy) | ❌ |
| **Scoping** | Agent-level (via `@agent` mention) | Global (root only) | Global | ✅ **Directory-scoped**: each `AGENTS.md` applies to its sub-tree | ✅ **Glob-based**: per-rule file pattern matching | Global |
| **Name resolution** | Frontmatter `name` > filename | N/A | N/A | File-path based | Filename (displayed in UI) | N/A |
| **Override support** | N/A | N/A | N/A | ✅ `AGENTS.override.md` | ✅ Deeper rules override shallower ones | N/A |
| **ai-adapter commands** | `agent add/list/get/remove/get-all/remove-all/add-all-rec` | — | — | — | — | — |

### Instructions Example

**Cursor (.cursor/rules/*.mdc with globs):**
```markdown
---
description: Backend API conventions
globs: server/**/*.ts
---
- Use Express async route handlers with error wrapping
- Validate request bodies with Zod schemas
- Return consistent JSON envelope: { ok, data, error }
```

**Continue (.continuerc.json):**
```json
{
  "rules": [
    "Use TypeScript with strict mode enabled",
    "All functions must have JSDoc comments",
    "Async operations must use async/await, not raw promises"
  ]
}
```

---

## Command

| Aspect | GitHub Copilot | Claude Code | OpenCode | OpenAI Codex CLI | Cursor | Continue |
|--------|---------------|-------------|----------|-----------------|--------|----------|
| **Directory** | `.github/commands/` | N/A | N/A | N/A | N/A | N/A |
| **File format** | Any executable/script files | N/A | N/A | N/A | N/A | N/A |
| **Purpose** | Custom slash commands for Copilot | — | — | — | — | — |
| **ai-adapter commands** | `command add/list/get/remove/add-rec/get-all/remove-all` | — | — | — | — | — |

> **Note:** Custom commands are a GitHub Copilot-specific concept. None of the other tools have an equivalent feature.

---

## MCP (Model Context Protocol)

| Aspect | GitHub Copilot | Claude Code | OpenCode | OpenAI Codex CLI | Cursor | Continue |
|--------|---------------|-------------|----------|-----------------|--------|----------|
| **Config file** | `.mcp.json` | `.mcp.json` | `.mcp.json` | `.mcp.json` | `.cursor/mcp.json` | `~/.continue/config.json` |
| **File format** | JSON | JSON | JSON | JSON | JSON | JSON |
| **Structure** | `{ "mcpServers": { "<name>": { ... } } }` | Same | Same | Same (standard MCP format) | Same | Integrated in config.json |
| **Multi-tool support** | ✅ Per-server `tools` field | ✅ Native | ✅ Via `opencode.json` | ✅ Via `agents/openai.yaml` deps | ✅ Native | ✅ Via Continue config |
| **Environment binding** | ✅ `env` field per server | N/A | N/A | N/A | N/A | N/A |
| **Enable/disable** | ✅ `enabled` flag per server | N/A | N/A | N/A | N/A | ✅ Per-server via config |
| **ai-adapter commands** | `mcp add/list/remove/export load/remove-all` | — | — | — | — | — |

### MCP Example

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-github"],
      "env": { "GITHUB_TOKEN": "${GITHUB_TOKEN}" }
    }
  }
}
```

---

## Prompt

| Aspect | GitHub Copilot | Claude Code | OpenCode | OpenAI Codex CLI | Cursor | Continue |
|--------|---------------|-------------|----------|-----------------|--------|----------|
| **Directory** | `.github/prompts/` | N/A | N/A | N/A | N/A | N/A |
| **File format** | Any text/markdown files | N/A | N/A | N/A | N/A | N/A |
| **Purpose** | Reusable prompt templates | — | — | — | — | — |
| **ai-adapter commands** | `prompt add/list/get/remove/add-rec/get-all/remove-all` | — | — | — | — | — |

> **Note:** Prompts are an ai-adapter managed concept for storing reusable prompt templates. They are not a native feature of any LLM tool.

---

## OpenCode Integration (via ai-adapter)

The `opencode` subcommand bridges `ai-adapter` with OpenCode:

| Command | Description |
|---------|-------------|
| `opencode alias` | Create `.opencode` symlink → `.github/` |
| `opencode install` | Generate `opencode.json` referencing `.github/agents/*.agent.md` |
| `opencode uninstall` | Remove `opencode.json` |

### Generated opencode.json

```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [
    ".github/copilot-instructions.md",
    ".github/agents/*.agent.md"
  ],
  "permission": {
    "execute": "ask",
    "read": "ask",
    "edit": "ask",
    "search": "ask",
    "agent": "ask",
    "browser": "ask",
    "web": "ask",
    "todo": "ask"
  }
}
```

---

## File Type Support Matrix

| Feature | GitHub Copilot | Claude Code | OpenCode | OpenAI Codex CLI | Cursor | Continue |
|---------|---------------|-------------|----------|-----------------|--------|----------|
| `AGENTS.md` | ❌ | ❌ | ❌ | ✅ **Primary** (hierarchical) | ❌ | ❌ |
| `CLAUDE.md` | ❌ (uses `.github/copilot-instructions.md`) | ✅ Primary | ✅ Fallback | ✅ Import compatible | ❌ | ❌ |
| `.github/copilot-instructions.md` | ✅ Primary | ✅ Fallback | ✅ Fallback | ❌ | ❌ | ❌ |
| `.github/instructions/*.md` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `.github/agents/*.agent.md` | ✅ Custom agents | ❌ | ✅ Via `opencode.json` | ❌ | ❌ | ❌ |
| `.github/skills/SKILL.md` | ✅ | ❌ | ❌ | ❌ (uses own SKILL.md) | ❌ | ❌ |
| `.github/bin/*` | ✅ Executable scripts | ❌ | ❌ | ❌ | ❌ | ❌ |
| `.mcp.json` | ✅ MCP servers | ✅ MCP servers | ✅ MCP servers | ✅ MCP servers | ✅ `.cursor/mcp.json` | ✅ Via `config.json` |
| `opencode.json` | ❌ | ❌ | ✅ Primary config | ❌ | ❌ | ❌ |
| `agents/openai.yaml` | ❌ | ❌ | ❌ | ✅ Skill metadata + MCP deps | ❌ | ❌ |
| `.cursor/rules/*.mdc` | ❌ | ❌ | ❌ | ❌ | ✅ **Primary** (glob-scoped rules) | ❌ |
| `.cursorrules` | ❌ | ❌ | ❌ | ❌ | ✅ Legacy fallback | ❌ |
| `.continuerc.json` | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ **Primary** (rules + model config) |

---

## Summary

- **GitHub Copilot** has the richest configuration ecosystem with agents, skills, commands, prompts, bins, and MCP — all managed under `.github/`.
- **Claude Code** relies primarily on `CLAUDE.md` and native `.mcp.json` support. It falls back to `.github/copilot-instructions.md`.
- **OpenCode** uses `opencode.json` for configuration with a `rules/` directory, and can symlink to `.github/` for compatibility.
- **OpenAI Codex CLI** uses a hierarchical `AGENTS.md` system (directory-scoped), supports `SKILL.md` with `agents/openai.yaml` metadata, and standard `.mcp.json`.
- **Cursor** uses `.cursor/rules/*.mdc` with YAML frontmatter and `globs` for file-scoped rules, plus `.cursor/mcp.json` for MCP. Legacy `.cursorrules` format is also supported.
- **Continue** uses `.continuerc.json` with a `rules` array for project instructions and model configuration.
- **ai-adapter** unifies these tools by managing `.github/` as the single source of truth and providing bridging commands (e.g., `opencode install`) for tool-specific formats.

---

## Reference / Official Documentation

All URLs below were verified as reachable (HTTP 200).

| Tool | Topic | URL |
|------|-------|-----|
| **GitHub Copilot** | Official docs | <https://docs.github.com/en/copilot/customizing-copilot> |
| | Custom instructions (`.github/instructions/*.md`) | <https://docs.github.com/en/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot> |
| | Agents overview | <https://docs.github.com/en/copilot/how-tos/copilot-on-github/use-copilot-agents/overview> |
| | Custom agents (SDK) | <https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/custom-agents> |
| | Skills (SDK) | <https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/skills> |
| | MCP (SDK) | <https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/mcp> |
| **Claude Code** | Official docs | <https://docs.anthropic.com/en/docs/claude-code/overview> |
| **OpenCode** | GitHub repository | <https://github.com/opencode-ai/opencode> |
| | Configuration | <https://github.com/opencode-ai/opencode?tab=readme-ov-file#configuration> |
| **OpenAI Codex CLI** | GitHub repository | <https://github.com/openai/codex> |
| | AGENTS.md spec | <https://github.com/openai/codex/blob/main/docs/agents_md.md> |
| **Cursor** | Official docs | <https://docs.cursor.com/get-started/welcome> |
| | Rules (`.cursor/rules/*.mdc`) | <https://docs.cursor.com/context/rules-for-ai> |
| | MCP | <https://docs.cursor.com/advanced/mcp> |
| **Continue** | Official docs | <https://docs.continue.dev/intro> |
| | Configuration (`.continuerc.json`) | <https://docs.continue.dev/reference/config> |
| | Tools / MCP | <https://docs.continue.dev/customize/tools> |
