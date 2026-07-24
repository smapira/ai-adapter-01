# LLM Tool Specification Comparison

This page compares how different AI coding tools (GitHub Copilot / Codex, Claude Code, OpenCode) handle the configuration categories managed by `ai-adapter`.

> **Publish to Wiki**: To publish this page to the GitHub Wiki, copy the content and create a new wiki page at:
> `https://github.com/smapira/ai-adapter-01/wiki/LLM-Tool-Comparison`

---

## Overview

| Feature | GitHub Copilot (Codex) | Claude Code | OpenCode |
|---------|----------------------|-------------|----------|
| **Config directory** | `.github/` | Project root | `.opencode/` or `.github/` via symlink |
| **Config format** | Markdown + YAML frontmatter | Markdown (`CLAUDE.md`) | JSON (`opencode.json`) |
| **Tool type** | VS Code extension | CLI tool (Anthropic) | Terminal AI agent |
| **ai-adapter support** | ✅ Full | ✅ Via `.github/` Fallback | ✅ Full (opencode subcommand) |

---

## Skill

| Aspect | GitHub Copilot | Claude Code | OpenCode |
|--------|---------------|-------------|----------|
| **Directory** | `.github/skills/` | N/A (uses `CLAUDE.md`) | `.opencode/rules/` |
| **File format** | `SKILL.md` with YAML frontmatter | Single `CLAUDE.md` | Markdown files in `rules/` |
| **Metadata** | `name`, `description`, `tags`, `agent` in frontmatter | No structured metadata | File-name based |
| **Agent binding** | ✅ `agent` field links skill to an agent | N/A | N/A |
| **ai-adapter commands** | `skill add`, `skill list`, `skill get`, `skill remove`, `skill search`, `skill link-agent`, `skill get-all` | — | — |

### Skill Example: `SKILL.md`

```markdown
---
name: database-schema
description: Database schema design knowledge
tags: [database, prisma, schema]
agent: reviewer
---
# Database Schema
Expert knowledge for designing and reviewing database schemas.
```

---

## Agent

| Aspect | GitHub Copilot | Claude Code | OpenCode |
|--------|---------------|-------------|----------|
| **Directory** | `.github/agents/` | N/A | N/A (uses `instructions` in config) |
| **File format** | `.agent.md` with YAML frontmatter | N/A | N/A |
| **File extension** | `*.agent.md`, `*.md` | — | — |
| **Frontmatter required** | ✅ `name` field required for `.agent.md` | — | — |
| **Name resolution** | Frontmatter `name` > filename (stripped extensions) | — | — |
| **Custom instructions** | ✅ Full agent definition in body | `CLAUDE.md` (single global) | `opencode.json` → `instructions` array |
| **ai-adapter commands** | `agent add`, `agent list`, `agent get`, `agent remove`, `agent get-all`, `agent remove-all`, `add-all-rec` | — | — |

### Agent Example: `.agent.md`

```markdown
---
name: reviewer
description: Code review specialist agent
---
You are a code reviewer.
Review code from the perspectives of security, performance, and readability.
```

---

## Command

| Aspect | GitHub Copilot | Claude Code | OpenCode |
|--------|---------------|-------------|----------|
| **Directory** | `.github/commands/` | N/A | N/A |
| **File format** | Any executable/script files | N/A | N/A |
| **Purpose** | Custom slash commands for Copilot | — | — |
| **ai-adapter commands** | `command add`, `command list`, `command get`, `command remove`, `command add-rec`, `command get-all`, `command remove-all` | — | — |

> **Note:** Custom commands are a GitHub Copilot-specific concept. Claude Code and OpenCode do not have an equivalent feature.

---

## MCP (Model Context Protocol)

| Aspect | GitHub Copilot | Claude Code | OpenCode |
|--------|---------------|-------------|----------|
| **Config file** | `.mcp.json` | `.mcp.json` | `.mcp.json` |
| **File format** | JSON | JSON | JSON |
| **Structure** | `{ "mcpServers": { "<name>": { "command": "...", "args": [...], "env": {...} } } }` | Same | Same |
| **Multi-tool support** | ✅ Per-server `tools` field (`vscode`, `claude`, `cursor`) | ✅ Native | ✅ Via `opencode.json` |
| **Environment binding** | ✅ `env` field per server | N/A | N/A |
| **Enable/disable** | ✅ `enabled` flag per server | N/A | N/A |
| **ai-adapter commands** | `mcp add`, `mcp list`, `mcp remove`, `mcp export`, `mcp load`, `mcp remove-all` | — | — |

### MCP Example: `.mcp.json`

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

| Aspect | GitHub Copilot | Claude Code | OpenCode |
|--------|---------------|-------------|----------|
| **Directory** | `.github/prompts/` | N/A | N/A |
| **File format** | Any text/markdown files | N/A | N/A |
| **Purpose** | Reusable prompt templates | — | — |
| **ai-adapter commands** | `prompt add`, `prompt list`, `prompt get`, `prompt remove`, `prompt add-rec`, `prompt get-all`, `prompt remove-all` | — | — |

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

| Feature | GitHub Copilot | Claude Code | OpenCode |
|---------|---------------|-------------|----------|
| `CLAUDE.md` | ❌ (uses `.github/copilot-instructions.md`) | ✅ Primary | ✅ Fallback |
| `.github/copilot-instructions.md` | ✅ Primary | ✅ Fallback | ✅ Fallback |
| `.github/instructions/*.md` | ✅ | ❌ | ❌ |
| `.github/agents/*.agent.md` | ✅ Custom agents | ❌ | ✅ Via `opencode.json` |
| `.github/skills/SKILL.md` | ✅ | ❌ | ❌ |
| `.github/bin/*` | ✅ Executable scripts | ❌ | ❌ |
| `.mcp.json` | ✅ MCP servers | ✅ MCP servers | ✅ MCP servers |
| `opencode.json` | ❌ | ❌ | ✅ Primary config |

---

## Summary

- **GitHub Copilot** has the richest configuration ecosystem with agents, skills, commands, prompts, bins, and MCP — all managed under `.github/`.
- **Claude Code** relies primarily on `CLAUDE.md` and native `.mcp.json` support. It falls back to `.github/copilot-instructions.md`.
- **OpenCode** uses `opencode.json` for configuration with a `rules/` directory, and can symlink to `.github/` for compatibility.
- **ai-adapter** unifies all three by managing `.github/` as the single source of truth and providing bridging commands (e.g., `opencode install`) for tool-specific formats.
