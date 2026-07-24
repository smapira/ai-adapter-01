# LLM Tool Specification Comparison

This page compares how different AI coding tools handle the configuration categories managed by `ai-adapter`.

---

## Overview

| Feature | GitHub Copilot (Codex) | Claude Code | OpenCode | OpenAI Codex CLI |
|---------|----------------------|-------------|----------|-----------------|
| **Vendor** | Microsoft (GitHub) | Anthropic | Community | OpenAI |
| **Config directory** | `.github/` | Project root | `.opencode/` or `.github/` via symlink | `.codex/` or project root |
| **Config format** | Markdown + YAML frontmatter | Markdown (`CLAUDE.md`) | JSON (`opencode.json`) | Markdown (`AGENTS.md`) + YAML |
| **Tool type** | VS Code extension | CLI tool (Anthropic) | Terminal AI agent | Terminal AI agent |
| **Instruction files** | `.github/instructions/*.md`, `.github/agents/*.agent.md` | `CLAUDE.md` | `opencode.json` → `instructions` | `AGENTS.md` (hierarchical) |
| **ai-adapter support** | ✅ Full | ✅ Via `.github/` Fallback | ✅ Full (opencode subcommand) | ❌ Planned |

---

## Skill

| Aspect | GitHub Copilot | Claude Code | OpenCode | OpenAI Codex CLI |
|--------|---------------|-------------|----------|-----------------|
| **Directory** | `.github/skills/` | N/A (uses `CLAUDE.md`) | `.opencode/rules/` | `~/.codex/skills/` or project-local |
| **File format** | `SKILL.md` with YAML frontmatter | Single `CLAUDE.md` | Markdown files in `rules/` | `SKILL.md` with YAML frontmatter |
| **Agents metadata** | ✅ `name`, `description`, `tags`, `agent` | No structured metadata | File-name based | ✅ `agents/openai.yaml` (display_name, short_description, etc.) |
| **Agent binding** | ✅ `agent` field links skill to an agent | N/A | N/A | ✅ Via `agents/openai.yaml` |
| **Bundled resources** | ❌ | ❌ | ❌ | ✅ `scripts/`, `references/`, `assets/` directories |
| **MCP dependencies** | ❌ | ❌ | ❌ | ✅ Declared in `agents/openai.yaml` |
| **ai-adapter commands** | `skill add/list/get/remove/search/link-agent/get-all` | — | — | — |

### Skill Example: SKILL.md

**GitHub Copilot / ai-adapter:**
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

**OpenAI Codex CLI (with agents/openai.yaml):**
```markdown
---
name: database-schema
description: Database schema design knowledge
argument-hint: "[topic]"
---
# Database Schema
Design and review database schemas using best practices.
```

```yaml
# agents/openai.yaml
interface:
  display_name: "Database Schema"
  short_description: "Design and review database schemas"
  default_prompt: "Help me design a database schema for..."
dependencies:
  tools:
    - type: mcp
      value: "github"
      description: "GitHub MCP server"
      transport: streamable_http
      url: "https://api.githubcopilot.com/mcp/"
```

---

## Agent / Instructions

| Aspect | GitHub Copilot | Claude Code | OpenCode | OpenAI Codex CLI |
|--------|---------------|-------------|----------|-----------------|
| **Primary mechanism** | `.github/agents/*.agent.md` | `CLAUDE.md` (single file) | `opencode.json` → `instructions` array | `AGENTS.md` (hierarchical, multiple files) |
| **File format** | `.agent.md` with YAML frontmatter | Plain Markdown | N/A | Plain Markdown (no frontmatter) |
| **File extensions** | `*.agent.md`, `*.md` | `CLAUDE.md` | Any referenced files | `AGENTS.md` (exact name) |
| **Fallback files** | `.github/copilot-instructions.md` | `.github/copilot-instructions.md` | `CLAUDE.md`, `.github/copilot-instructions.md` | Configurable fallbacks (e.g. `EXAMPLE.md`) |
| **Scoping** | Agent-level (via `@agent` mention) | Global (root only) | Global | ✅ **Directory-scoped**: each `AGENTS.md` applies to its sub-tree |
| **Name resolution** | Frontmatter `name` > filename | N/A | N/A | File-path based |
| **Override support** | N/A | N/A | N/A | ✅ `AGENTS.override.md` for local overrides |
| **ai-adapter commands** | `agent add/list/get/remove/get-all/remove-all/add-all-rec` | — | — | — |

### Agent/Instructions Example

**GitHub Copilot (.agent.md):**
```markdown
---
name: reviewer
description: Code review specialist agent
---
You are a code reviewer.
Review code from the perspectives of security, performance, and readability.
```

**OpenAI Codex CLI (AGENTS.md, placed at any directory level):**
```markdown
# AGENTS.md
## Coding conventions
- Use TypeScript with strict mode
- Functions must have JSDoc comments
- Follow the existing error handling patterns in this directory

## Testing
- Run `npm test` before submitting changes
- Maintain 80%+ test coverage
```

---

## Command

| Aspect | GitHub Copilot | Claude Code | OpenCode | OpenAI Codex CLI |
|--------|---------------|-------------|----------|-----------------|
| **Directory** | `.github/commands/` | N/A | N/A | N/A |
| **File format** | Any executable/script files | N/A | N/A | N/A |
| **Purpose** | Custom slash commands for Copilot | — | — | — |
| **ai-adapter commands** | `command add/list/get/remove/add-rec/get-all/remove-all` | — | — | — |

> **Note:** Custom commands are a GitHub Copilot-specific concept. None of the other tools have an equivalent feature.

---

## MCP (Model Context Protocol)

| Aspect | GitHub Copilot | Claude Code | OpenCode | OpenAI Codex CLI |
|--------|---------------|-------------|----------|-----------------|
| **Config file** | `.mcp.json` | `.mcp.json` | `.mcp.json` | `.mcp.json` |
| **File format** | JSON | JSON | JSON | JSON |
| **Structure** | `{ "mcpServers": { "<name>": { ... } } }` | Same | Same | Same (standard MCP format) |
| **Multi-tool support** | ✅ Per-server `tools` field | ✅ Native | ✅ Via `opencode.json` | ✅ Via `agents/openai.yaml` deps |
| **Environment binding** | ✅ `env` field per server | N/A | N/A | N/A |
| **Enable/disable** | ✅ `enabled` flag per server | N/A | N/A | N/A |
| **ai-adapter commands** | `mcp add/list/remove/export load/remove-all` | — | — | — |

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

| Aspect | GitHub Copilot | Claude Code | OpenCode | OpenAI Codex CLI |
|--------|---------------|-------------|----------|-----------------|
| **Directory** | `.github/prompts/` | N/A | N/A | N/A |
| **File format** | Any text/markdown files | N/A | N/A | N/A |
| **Purpose** | Reusable prompt templates | — | — | — |
| **ai-adapter commands** | `prompt add/list/get/remove/add-rec/get-all/remove-all` | — | — | — |

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

| Feature | GitHub Copilot | Claude Code | OpenCode | OpenAI Codex CLI |
|---------|---------------|-------------|----------|-----------------|
| `AGENTS.md` | ❌ | ❌ | ❌ | ✅ **Primary** (hierarchical) |
| `CLAUDE.md` | ❌ (uses `.github/copilot-instructions.md`) | ✅ Primary | ✅ Fallback | ✅ Import compatible |
| `.github/copilot-instructions.md` | ✅ Primary | ✅ Fallback | ✅ Fallback | ❌ |
| `.github/instructions/*.md` | ✅ | ❌ | ❌ | ❌ |
| `.github/agents/*.agent.md` | ✅ Custom agents | ❌ | ✅ Via `opencode.json` | ❌ |
| `.github/skills/SKILL.md` | ✅ | ❌ | ❌ | ❌ (uses own SKILL.md format) |
| `.github/bin/*` | ✅ Executable scripts | ❌ | ❌ | ❌ |
| `.mcp.json` | ✅ MCP servers | ✅ MCP servers | ✅ MCP servers | ✅ MCP servers |
| `opencode.json` | ❌ | ❌ | ✅ Primary config | ❌ |
| `agents/openai.yaml` | ❌ | ❌ | ❌ | ✅ Skill metadata + MCP deps |

---

## Summary

- **GitHub Copilot** has the richest configuration ecosystem with agents, skills, commands, prompts, bins, and MCP — all managed under `.github/`.
- **Claude Code** relies primarily on `CLAUDE.md` and native `.mcp.json` support. It falls back to `.github/copilot-instructions.md`.
- **OpenCode** uses `opencode.json` for configuration with a `rules/` directory, and can symlink to `.github/` for compatibility.
- **OpenAI Codex CLI** uses a hierarchical `AGENTS.md` system (directory-scoped), supports `SKILL.md` with `agents/openai.yaml` metadata, and standard `.mcp.json`. It has built-in migration compatibility with Claude Code configurations.
- **ai-adapter** unifies these tools by managing `.github/` as the single source of truth and providing bridging commands (e.g., `opencode install`) for tool-specific formats.
