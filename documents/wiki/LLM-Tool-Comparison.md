# LLM Tool Specification Comparison

This page compares how different AI coding tools handle the configuration categories managed by `ai-adapter`.

---

## Overview

| Feature | GitHub Copilot (Codex) | Claude Code | OpenCode | OpenAI Codex CLI | Cursor | Continue | Orca | **Agent Plugins 1.0.0** |
|---------|----------------------|-------------|----------|-----------------|--------|----------|------|--------------------------|
| **Vendor** | Microsoft (GitHub) | Anthropic | Community / Anomaly | OpenAI | Anysphere | Continue.dev | Anomaly | AWS, Microsoft, OpenAI, Anysphere, Vercel, Google |
| **Config directory** | `.github/` | Project root | `.opencode/` or `.github/` via symlink | `.codex/` or project root | `.cursor/` | `.continue/` | `~/.orca/` (or OS app data dir) | Plugin root (`./`) |
| **Config format** | Markdown + YAML frontmatter | Markdown (`CLAUDE.md`) | JSON (`opencode.json`) | Markdown (`AGENTS.md`) + YAML | Markdown (`*.mdc`) with YAML frontmatter | JSON (`.continuerc.json`) | JSON | JSON (`plugin.json` + `mcp.json`) |
| **Tool type** | VS Code extension | CLI tool (Anthropic) | Terminal AI agent | Terminal AI agent | AI-first IDE | VS Code + JetBrains extension | Desktop app (AI orchestrator) | Vendor-neutral standard |
| **Instruction files** | `.github/instructions/*.md`, `.github/agents/*.agent.md` | `CLAUDE.md` | `opencode.json` → `instructions` | `AGENTS.md` (hierarchical) | `.cursor/rules/*.mdc` | `.continuerc.json` → `rules` array | Hook-based orchestration / agent delegation | `skills/` directory with `SKILL.md` |
| **ai-adapter support** | ✅ Full | ✅ Via `.github/` Fallback | ✅ Full (opencode subcommand) | ✅ Full (codex subcommand + agent) | ❌ Planned | ❌ Planned | ✅ Partial (skills + MCP export via `--format openclaw`) | ✅ Full (plugin subcommand) |

---

## Skill / Rules

| Aspect | GitHub Copilot | Claude Code | OpenCode | OpenAI Codex CLI | Cursor | Continue | Orca |
|--------|---------------|-------------|----------|-----------------|--------|----------|------|
| **Directory** | `.github/skills/` | N/A (uses `CLAUDE.md`) | `.opencode/rules/` | `~/.codex/skills/` or project-local | `.cursor/rules/` | N/A | `~/.claude/skills/` (shared with Claude Code) |
| **File format** | `SKILL.md` with YAML frontmatter | Single `CLAUDE.md` | Markdown files in `rules/` | `SKILL.md` with YAML frontmatter | `*.mdc` with YAML frontmatter | `.continuerc.json` → `rules` array | `SKILL.md` with YAML frontmatter |
| **Metadata** | ✅ `name`, `description`, `tags`, `agent`, `env` | No structured metadata | File-name based | ✅ `agents/openai.yaml` | ✅ `description`, `globs` in frontmatter | Plain text rules | ✅ `name`, `description`, `tags` |
| **File globbing** | ❌ | ❌ | ❌ | ❌ | ✅ `globs` field controls which files the rule applies to | ❌ | ❌ |
| **Agent binding** | ✅ `agent` field links skill to an agent | N/A | N/A | ✅ Via `agents/openai.yaml` | ❌ (rules auto-matched by globs) | ❌ | ✅ Via hook events (SessionStart, SubagentStart, etc.) |
| **Bundled resources** | ❌ | ❌ | ❌ | ✅ `scripts/`, `references/`, `assets/` | ❌ | ❌ | ✅ |
| **MCP dependencies** | ❌ | ❌ | ❌ | ✅ Declared in `agents/openai.yaml` | ❌ | ❌ | ✅ |
| **ai-adapter commands** | `skill add/list/get/remove/search/link-agent/get-all` (all support `--env`) | — | — | — | — | — | — |

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

| Aspect | GitHub Copilot | Claude Code | OpenCode | OpenAI Codex CLI | Cursor | Continue | Orca |
|--------|---------------|-------------|----------|-----------------|--------|----------|------|
| **Primary mechanism** | `.github/agents/*.agent.md` | `CLAUDE.md` (single file) | `opencode.json` → `instructions` array | `AGENTS.md` (hierarchical, multiple files) | `.cursor/rules/*.mdc` | `.continuerc.json` → `rules` array | Hook-based orchestration / agent delegation |
| **File format** | `.agent.md` with YAML frontmatter | Plain Markdown | N/A | Plain Markdown (no frontmatter) | Markdown with YAML frontmatter | JSON string array | JSON (hooks config) |
| **File extensions** | `*.agent.md`, `*.md` | `CLAUDE.md` | Any referenced files | `AGENTS.md` (exact name) | `*.mdc` | `.continuerc.json` | `.json` |
| **Fallback files** | `.github/copilot-instructions.md` | `.github/copilot-instructions.md` | `CLAUDE.md`, `.github/copilot-instructions.md` | Configurable fallbacks (e.g. `EXAMPLE.md`) | `.cursorrules` (legacy) | ❌ | Delegates to the spawned agent's fallback chain |
| **Scoping** | Agent-level (via `@agent` mention) | Global (root only) | Global | ✅ **Directory-scoped**: each `AGENTS.md` applies to its sub-tree | ✅ **Glob-based**: per-rule file pattern matching | Global | ✅ Worktree-level |
| **Name resolution** | Frontmatter `name` > filename | N/A | N/A | File-path based | Filename (displayed in UI) | N/A | N/A |
| **Override support** | N/A | N/A | N/A | ✅ `AGENTS.override.md` | ✅ Deeper rules override shallower ones | N/A | ✅ Worktree-level hooks override global hooks |
| **ai-adapter commands** | `sub-agent add/list/get/remove/get-all/remove-all/add-all-rec` (all support `--env`)  `agent add/list/get/remove/get-all/remove-all` (root-level) | — | — | — | — | — | — |

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

| Aspect | GitHub Copilot | Claude Code | OpenCode | OpenAI Codex CLI | Cursor | Continue | Orca |
|--------|---------------|-------------|----------|-----------------|--------|----------|------|
| **Directory** | `.github/commands/` | N/A | N/A | N/A | N/A | N/A | N/A |
| **File format** | Any executable/script files | N/A | N/A | N/A | N/A | N/A | N/A |
| **Purpose** | Custom slash commands for Copilot | — | — | — | — | — | Uses agent hooks (PreToolUse, PostToolUse) |
| **ai-adapter commands** | `command add/list/get/remove/add-rec/get-all/remove-all` (all support `--env`) | — | — | — | — | — | — |

> **Note:** Custom commands are a GitHub Copilot-specific concept. None of the other tools have an equivalent feature.

---

## MCP (Model Context Protocol)

| Aspect | GitHub Copilot | Claude Code | OpenCode | OpenAI Codex CLI | Cursor | Continue | Orca |
|--------|---------------|-------------|----------|-----------------|--------|----------|------|
| **Config file** | `.mcp.json` | `.mcp.json` | `.mcp.json` | `.mcp.json` | `.cursor/mcp.json` | `~/.continue/config.json` | `.mcp.json` (shared with OpenCode/Claude Code) |
| **File format** | JSON | JSON | JSON | JSON | JSON | JSON | JSON |
| **Structure** | `{ "mcpServers": { "<name>": { ... } } }` | Same | Same | Same (standard MCP format) | Same | Integrated in config.json | Same |
| **Multi-tool support** | ✅ Per-server `tools` field | ✅ Native | ✅ Via `opencode.json` | ✅ Via `agents/openai.yaml` deps | ✅ Native | ✅ Via Continue config | ✅ Via OpenCode plugin |
| **Environment binding** | ✅ `env` field per server | N/A | N/A | N/A | N/A | N/A | N/A |
| **Enable/disable** | ✅ `enabled` flag per server | N/A | N/A | N/A | N/A | ✅ Per-server via config | ✅ Per-worktree via Orca UI |
| **ai-adapter commands** | `mcp add/list/remove/get/remove-all` (all support `--env`) | — | — | — | — | — | — |

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

| Aspect | GitHub Copilot | Claude Code | OpenCode | OpenAI Codex CLI | Cursor | Continue | Orca |
|--------|---------------|-------------|----------|-----------------|--------|----------|------|
| **Directory** | `.github/prompts/` | N/A | N/A | N/A | N/A | N/A | N/A |
| **File format** | Any text/markdown files | N/A | N/A | N/A | N/A | N/A | N/A |
| **Purpose** | Reusable prompt templates | — | — | — | — | — | Delegates to the spawned agent's prompt system |
| **ai-adapter commands** | `prompt add/list/get/remove/add-rec/get-all/remove-all` (all support `--env`) | — | — | — | — | — | — |

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

| Feature | GitHub Copilot | Claude Code | OpenCode | OpenAI Codex CLI | Cursor | Continue | Orca | Agent Plugins |
|---------|---------------|-------------|----------|-----------------|--------|----------|------|---------------|
| `AGENTS.md` | ❌ | ❌ | ❌ | ✅ **Primary** (hierarchical) | ❌ | ❌ | ❌ | ❌ |
| `CLAUDE.md` | ❌ (uses `.github/copilot-instructions.md`) | ✅ Primary | ✅ Fallback | ✅ Import compatible | ❌ | ❌ | ❌ | ❌ |
| `.github/copilot-instructions.md` | ✅ Primary | ✅ Fallback | ✅ Fallback | ❌ | ❌ | ❌ | ❌ | ❌ |
| `.github/instructions/*.md` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `.github/agents/*.agent.md` | ✅ Custom agents | ❌ | ✅ Via `opencode.json` | ❌ | ❌ | ❌ | ❌ | ❌ |
| `.github/skills/SKILL.md` | ✅ | ❌ | ❌ | ❌ (uses own SKILL.md) | ❌ | ❌ | ✅ Via shared `~/.claude/skills/` | ❌ (uses `skills/`) |
| `.github/bin/*` | ✅ Executable scripts | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `.mcp.json` | ✅ MCP servers | ✅ MCP servers | ✅ MCP servers | ✅ MCP servers | ✅ `.cursor/mcp.json` | ✅ Via `config.json` | ✅ MCP servers | ❌ (uses `mcp.json`) |
| `opencode.json` | ❌ | ❌ | ✅ Primary config | ❌ | ❌ | ❌ | ✅ Via OpenCode integration | ❌ |
| `agents/openai.yaml` | ❌ | ❌ | ❌ | ✅ Skill metadata + MCP deps | ❌ | ❌ | ❌ | ❌ |
| `.cursor/rules/*.mdc` | ❌ | ❌ | ❌ | ❌ | ✅ **Primary** (glob-scoped rules) | ❌ | ❌ | ❌ |
| `.cursorrules` | ❌ | ❌ | ❌ | ❌ | ✅ Legacy fallback | ❌ | ❌ | ❌ |
| `.continuerc.json` | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ **Primary** (rules + model config) | ❌ | ❌ |
| `plugin.json` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ **Required** |
| `mcp.json` (Agent Plugins) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ **Primary** |
| `skills/*/SKILL.md` (Agent Plugins) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ **Primary** |

---

## Summary

- **GitHub Copilot** has the richest configuration ecosystem with agents, skills, commands, prompts, bins, and MCP — all managed under `.github/`.
- **Claude Code** relies primarily on `CLAUDE.md` and native `.mcp.json` support. It falls back to `.github/copilot-instructions.md`.
- **OpenCode** uses `opencode.json` for configuration with a `rules/` directory, and can symlink to `.github/` for compatibility.
- **OpenAI Codex CLI** uses a hierarchical `AGENTS.md` system (directory-scoped), supports `SKILL.md` with `agents/openai.yaml` metadata, and standard `.mcp.json`.
- **Cursor** uses `.cursor/rules/*.mdc` with YAML frontmatter and `globs` for file-scoped rules, plus `.cursor/mcp.json` for MCP. Legacy `.cursorrules` format is also supported.
- **Continue** uses `.continuerc.json` with a `rules` array for project instructions and model configuration.
- **Orca** is a desktop app (multi-agent orchestrator) from Anomaly that manages AI agent sessions with worktree-scoped hooks, shared `~/.claude/skills/` support, and standard `.mcp.json` MCP configuration. It delegates instruction/agent management to the underlying spawned agent (OpenCode, Claude Code, etc.).
- **ai-adapter** unifies these tools by managing `.github/` as the single source of truth and providing bridging commands (e.g., `opencode install`) for tool-specific formats. All entity types (skill, command, prompt, sub-agent, bin, mcp) support `--env` for environment-scoped registration and filtering.

---

## Agent Plugins 1.0.0 — Industry Standard

[Agent Plugins 1.0.0](https://agent-plugins.org/) is an open, vendor-neutral standard for packaging reusable components (skills + MCP servers) into portable plugins that work across different AI agent clients.

### Key Characteristics

| Aspect | Agent Plugins 1.0.0 |
|--------|---------------------|
| **Purpose** | Cross-client portability for skills and MCP servers |
| **Governance** | Technical Steering Committee (AWS, Cursor, Microsoft, OpenAI, Vercel) |
| **Components** | Skills (`skills/`) + MCP servers (`mcp.json`) |
| **Manifest** | `plugin.json` with `$schema` and `name` required |
| **MCP format** | `mcp.json` with `type: "stdio"` (or `"streamable-http"`, `"sse"`) |
| **Path variables** | `${PLUGIN_ROOT}`, `${PLUGIN_DATA}` for portable paths |
| **Client extensions** | Reverse-domain namespace (e.g., `com.cursor.client`) |

### Supported Clients (as of 2026-08-10)

| Client | Status |
|--------|--------|
| GitHub Copilot (VS Code, CLI) | ✅ Supported |
| Cursor | ✅ Supported |
| ChatGPT / Codex | ✅ Supported |
| AWS Kiro | ✅ Supported |
| VS Code (Microsoft) | ✅ Supported |
| Google (AI agents) | ✅ Announced |
| Claude Code (Anthropic) | ❌ Not announced |

### Package Structure

```
my-plugin/
├── plugin.json              # Required manifest
├── skills/                  # Agent Skills directory
│   └── skill-name/
│       ├── SKILL.md
│       ├── scripts/
│       └── references/
├── mcp.json                 # MCP server configuration
└── com.example.client/      # Client extension (optional)
    └── hooks/
```

### plugin.json Example

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
  "name": "ai-adapter-plugin",
  "version": "1.0.0",
  "description": "AI agent skills and MCP servers",
  "author": {
    "name": "smapira"
  },
  "license": "MIT"
}
```

### mcp.json Example

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
  "mcpServers": {
    "github": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    },
    "database": {
      "type": "stdio",
      "command": "./bin/db-server",
      "args": ["--config", "${PLUGIN_ROOT}/config/db.json"],
      "cwd": "${PLUGIN_ROOT}"
    }
  }
}
```

### Comparison with Existing Formats

| Aspect | `.mcp.json` (Current) | Agent Plugins `mcp.json` |
|--------|----------------------|--------------------------|
| Schema | None | `$schema` required |
| Server type | Implicit (stdio only) | `type: "stdio"` required |
| Command | Array or string | Single token (string) |
| Path variables | None | `${PLUGIN_ROOT}`, `${PLUGIN_DATA}` |
| File name | `.mcp.json` | `mcp.json` |

### ai-adapter Integration Status

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1** | Create `plugin.json` template, MCP conversion utility | ✅ Done (`plugin build`) |
| **Phase 2** | Add `ai-adapter plugin build/validate` commands | ✅ Done (0.21.0) |
| **Phase 3** | Add `--format agent-plugins` to `mcp get` and `skill get-all` | 🔄 Planned |
| **Phase 4** | Test with Cursor, VS Code, and other supporting clients | ⏳ Pending |

`ai-adapter plugin validate` checks `plugin.json` (required `$schema`/`name`, name
rules, `author`, field types), `mcp.json` (`type` per server, single-token
`command`, `${PLUGIN_ROOT}` refs, reserved env keys, HTTPS for non-loopback URLs),
and `skills/` (`SKILL.md` frontmatter). Exit code reflects validity for CI use.

For detailed implementation guide, see: `documents/dev/plans/20260810_agent_plugins_1.0.0_compliance.md`

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
| **Orca** | GitHub repository | <https://github.com/anomalyco/orca> |
| | Orca app | <https://anoma.ly> |
| **Agent Plugins** | Official site | <https://agent-plugins.org/> |
| | Specification | <https://agent-plugins.org/specification> |
| | JSON Schemas | <https://agent-plugins.org/schemas> |
| | GitHub repository | <https://github.com/agentplugins/agent-plugins-spec> |
| | Agent Skills spec | <https://agentskills.io/specification> |
