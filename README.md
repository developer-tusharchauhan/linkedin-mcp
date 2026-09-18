# LinkedIn MCP Server

A custom [Model Context Protocol](https://modelcontextprotocol.io/) server that gives AI assistants control of your LinkedIn account through your own logged-in browser session.

Publish posts, read and edit your profile, search jobs, and apply via Easy Apply — all from a chat conversation with any MCP-compatible client (opencode, Claude, Cursor, and more).

> ⚠️ **Disclaimer:** This project automates your real LinkedIn account in a browser. LinkedIn's User Agreement (§8.2) prohibits bots, scraping, and automation. Use at your own risk; aggressive or mass automation can lead to account restriction. All browser actions run locally on your machine.

## Quick Start (first-timers)

The 5-minute path from nothing to your first LinkedIn post via AI. Requires only [uv](https://docs.astral.sh/uv/), a terminal, and a LinkedIn account.

**1. Install uv** (skip if you already have it)

```bash
# Windows (PowerShell)
irm https://astral.sh/uv/install.ps1 | iex

# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**2. Clone and install**

```bash
git clone https://github.com/developer-tusharchauhan/linkedin-mcp.git
cd linkedin-mcp

uv sync
uv run patchright install chromium
```

**3. Register with your MCP client** — put your absolute path to `linkedin-mcp` in place of `YOUR_PATH`:

<details>
<summary>opencode — add to <code>opencode.json</code></summary>

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "linkedin": {
      "type": "local",
      "command": ["uv", "--directory", "YOUR_PATH/linkedin-mcp", "run", "python", "-m", "linkedin_mcp.server"],
      "enabled": true
    }
  }
}
```
</details>

<details>
<summary>Claude Desktop / Cursor / Claude Code — add to your MCP config</summary>

```json
{
  "mcpServers": {
    "linkedin": {
      "command": "uv",
      "args": ["--directory", "YOUR_PATH/linkedin-mcp", "run", "python", "-m", "linkedin_mcp.server"]
    }
  }
}
```
</details>

<details>
<summary>VS Code — add to <code>.vscode/mcp.json</code></summary>

```json
{
  "servers": {
    "linkedin": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "YOUR_PATH/linkedin-mcp", "run", "python", "-m", "linkedin_mcp.server"]
    }
  }
}
```
</details>

> On Windows, wrap the command in `cmd /c` if your client does not resolve `uv` directly.

**4. Restart your MCP client**, then in the chat:

```
Run the login tool.
```

A Chromium window opens — sign in to LinkedIn there (complete 2FA/captcha if asked). After that, session is saved and you can say things like:

- "Read my LinkedIn profile"
- "Publish this post on LinkedIn: I just shipped my first MCP server!"
- "Search for Data Engineer jobs posted this week, remote"
- "Check this job and dry-run the Easy Apply form: <job URL>"

> Seeing `Failed to spawn` on a Windows machine? Your security policy blocks uv's script shims — the `python -m` commands above already work around it. Just restart the client.

## Features

- **Posting** — publish posts to your LinkedIn feed
- **Profile** — read your full profile, edit headline / About, add experience & education entries
- **Jobs** — search jobs with keyword, location, date, and type filters; fetch full job details
- **Easy Apply** — dry-run form inspection first, consent-gated submission
- **Session persistence** — sign in once, reuse the session indefinitely

## Tools

| Tool | Description |
|------|-------------|
| `login` | Open a headed browser window to sign in to LinkedIn and save the session |
| `check_session` | Check whether the persisted session is still valid |
| `create_post` | Publish a post to your feed |
| `get_my_profile` | Read name, headline, about, experience, education, skills |
| `update_headline` | Replace your profile headline |
| `update_about` | Replace your About / Summary section |
| `update_experience` | Add a new experience (job) entry |
| `update_education` | Add a new education entry |
| `search_jobs` | Search LinkedIn jobs with filters |
| `get_job_details` | Fetch full details for a job URL |
| `easy_apply` | Inspect (dry-run) or submit an Easy Apply form |

## Requirements

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- A LinkedIn account

## Installation

```bash
git clone https://github.com/developer-tusharchauhan/linkedin-mcp.git
cd linkedin-mcp

uv sync
uv run patchright install chromium
```

## First run — sign in

The server ships with no credentials. On first use, call the `login` tool:

1. A Chromium window opens.
2. Sign in to LinkedIn (including 2FA / captcha if prompted).
3. The session is saved to `~/.linkedin-mcp/profile` and reused automatically.

## Easy Apply auto-fill

Before submitting applications, create `~/.linkedin-mcp/answers.json` mapping question labels to your answers. Keys are matched case-insensitively against form labels:

```json
{
  "phone": "+44 7xxx xxx xxxx",
  "city": "London",
  "years of python experience": "3",
  "willing to relocate": "yes"
}
```

## Registering with an MCP client

Use the local (stdio) server. The command below works from any directory:

```json
{
  "mcpServers": {
    "linkedin": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/linkedin-mcp", "run", "python", "-m", "linkedin_mcp.server"]
    }
  }
}
```

For opencode (`opencode.json`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "linkedin": {
      "type": "local",
      "command": ["uv", "--directory", "/absolute/path/to/linkedin-mcp", "run", "python", "-m", "linkedin_mcp.server"],
      "enabled": true
    }
  }
}
```

> **Windows / corporate machines:** some security policies (App Control / AppLocker) block uv's generated `.exe` shims. If you see `Failed to spawn`, use the `python -m` form shown above instead of the `linkedin-mcp` script, and restart your MCP client.

## Example usage

Once connected, just ask your assistant:

- "Publish a post on LinkedIn about my new project"
- "Read my LinkedIn profile"
- "Update my headline to: Software Engineer | AI & Data"
- "Search for Senior Data Engineer jobs posted this week, remote"
- "Check this job and dry-run the Easy Apply form: https://www.linkedin.com/jobs/view/1234567890"

It is recommended to inspect (`dry_run`) before submitting any application.

## How it works

- Patchright (a stealth-patched Playwright fork) drives a persistent Chromium profile.
- A process-wide lock serializes tool calls — one browser at a time.
- LinkedIn selectors are matched against the current DOM; if LinkedIn changes markup, some tools may need a selector refresh.

## Project layout

```
linkedin-mcp/
├── pyproject.toml          # dependencies + entrypoint
├── src/linkedin_mcp/
│   ├── server.py           # MCP server: registers all tools
│   ├── browser.py          # persistent browser session management
│   └── linkedin.py         # automation routines
└── README.md
```

## License

MIT