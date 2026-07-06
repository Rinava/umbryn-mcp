# Client configuration examples

`umbryn-mcp` is a stdio MCP server: point your client at the installed
`umbryn-mcp` command. Install it first:

```bash
pip install umbryn-mcp
# or, isolated, run without installing:  uvx umbryn-mcp
```

Then use one of the configs below. All optional tuning is via `env` (see the
[README](../README.md#configuration)).

## Claude Desktop / Claude Code

`claude_desktop_config.json` — see [`claude_desktop_config.json`](claude_desktop_config.json).
Or from the CLI:

```bash
claude mcp add umbryn-mcp -- umbryn-mcp
```

## Cursor

`.cursor/mcp.json` — see [`cursor_mcp.json`](cursor_mcp.json).

## VS Code

`.vscode/mcp.json` — see [`vscode_mcp.json`](vscode_mcp.json).

## Calling the tools

- `redact(text)` → `{ redacted_text, token_map, entities }` — send only
  `redacted_text` onward; keep `token_map` local.
- `restore(redacted_text, token_map)` → `{ text }`.
- `detect(text)` → `{ entities, count }`.
