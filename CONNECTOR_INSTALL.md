# Installing this repository as a connector

**Draw Me a Fact Studio** is a Model Context Protocol (MCP) connector that wraps
the `@drawmeafact` production engine. Once registered, a model can ask the studio
to plan, render, QA and publish episodes — and gets real files back, not advice.

| | |
|---|---|
| **Connector id** | `draw-me-a-fact-studio` |
| **Version** | 1.1.0 |
| **Transport** | streamable HTTP (also `stdio` and legacy `sse`) |
| **MCP endpoint** | `POST /mcp` |
| **Manifest** | `GET /.well-known/ai-connector.json` |
| **Tools** | 8 (`describe_studio`, `list_episodes`, `get_episode`, `plan_script`, `produce_episode`, `run_qa`, `list_assets`, `score_info`) |
| **Auth** | none for read-only tools and dry runs; publishing reads server-side secrets |
| **Repository** | https://github.com/drawmeafact-auto/draw-me-a-fact-auto |

---

## 0. The honest bit first

Arena's **connected-apps list** (Notion, Slack, GitHub, …) is a server-side
catalog on Arena's side. A repository cannot add itself to that list; only the
Arena team can index a new connector. What this repo now ships is everything
that registration needs:

1. a working MCP server and a stable endpoint,
2. a machine-readable manifest at `/.well-known/ai-connector.json`,
3. a JSON tool API for clients that cannot speak MCP,
4. tests that prove both surfaces work (`Connector CI`).

Two ways to get it in front of a model today:

- **Custom MCP connector** — paste the endpoint into Arena (or any MCP client)
  and the tools appear immediately. This is the path that works right now.
- **Catalog listing** — send the manifest URL and repository to Arena support
  so the connector gets indexed in the connected-apps list.

Everything below covers both.

---

## 1. Run the connector

```bash
git clone https://github.com/drawmeafact-auto/draw-me-a-fact-auto
cd draw-me-a-fact-auto
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-connector.txt

# hosted connector (manifest + JSON tools + MCP on one port)
python -m connector.http_server --host 0.0.0.0 --port 8765
```

Check it is alive:

```bash
curl -s localhost:8765/healthz
curl -s localhost:8765/.well-known/ai-connector.json | head -c 300
curl -s -X POST localhost:8765/tools/list_episodes -H 'content-type: application/json' -d '{}'
```

Expected tools on `/tools`: `describe_studio`, `list_episodes`, `get_episode`,
`plan_script`, `produce_episode`, `run_qa`, `list_assets`, `score_info`.

Local clients that launch processes can skip HTTP entirely:

```bash
python -m connector.server            # stdio transport
```

---

## 2. Register it in Arena

**2a. As a custom MCP connector (works today)**

1. Start the server (§1) somewhere the model can reach — a public host, a
   tunnel, or the sandbox preview URL shown next to the running process.
2. In the conversation, connect the apps panel → *custom connector / MCP server*.
3. Give it:
   - **Name:** Draw Me a Fact Studio
   - **URL:** `https://<your-host>/mcp`
   - **Manifest (optional):** `https://<your-host>/.well-known/ai-connector.json`
   - **Auth:** none
4. Save. The eight tools appear in the tool picker. Ask: *"List the episode
   slate and tell me what ships next."*

**2b. For the connected-apps catalog**

Send the Arena team these two URLs and the one-line pitch:

- Manifest: `https://<your-host>/.well-known/ai-connector.json`
- Repository: `https://github.com/drawmeafact-auto/draw-me-a-fact-auto`
- Pitch: *"Autonomous production studio for a YouTube Shorts channel — writes the
  script, voices it, animates the film, runs a QA gate and prepares the upload
  package."*

They can exercise the connector with the CI job in
`.github/workflows/connector_ci.yml`, which boots the server, reads the manifest
and calls a tool over MCP.

---

## 3. Register it anywhere else

**Claude Desktop / Cursor / any MCP client**

```json
{
  "mcpServers": {
    "draw-me-a-fact": {
      "command": "python",
      "args": ["-m", "connector.server"],
      "cwd": "/abs/path/to/draw-me-a-fact-auto"
    }
  }
}
```

Remote variant:

```json
{
  "mcpServers": {
    "draw-me-a-fact": {
      "type": "http",
      "url": "https://<your-host>/mcp"
    }
  }
}
```

**Custom GPT / OpenAPI-style actions or n8n**

Use the JSON façade; every tool is `POST /tools/{name}` with a JSON body:

```bash
curl -s -X POST https://<your-host>/tools/get_episode \
  -H 'content-type: application/json' -d '{"identifier":"11"}'

curl -s -X POST https://<your-host>/tools/produce_episode \
  -H 'content-type: application/json' \
  -d '{"episode":"11","publish_mode":"dry_run","render":true}'
```

`GET /tools` returns the exact input schema for each tool.

---

## 4. What the tools do

| Tool | Cost | What it returns |
|---|---|---|
| `describe_studio` | free | What the studio is, which integrations are configured |
| `list_episodes` | free | The pre-verified slate + what already shipped |
| `get_episode` | free | Script, scenes, sourced accuracy table, word count |
| `plan_script` | free (needs an LLM key) | A drafted script checked against the five-sentence contract |
| `produce_episode` | 1–2 min CPU | MP4, SRT, `youtube_pack.md`, contact sheet, QA table |
| `run_qa` | seconds | The QA gate re-run on an existing film |
| `list_assets` | free | Every deliverable on disk with byte sizes |
| `score_info` | free | The locked audio chain and timing constants |

`produce_episode` defaults to `publish_mode: "dry_run"` — it renders and gates,
and never uploads unless you explicitly ask for `private`, `unlisted`,
`public_now` or `schedule_target`. It refuses to report success when the QA gate
fails.

---

## 5. Secrets the connector reads

Set these on the **server**, never in the client:

| Variable | Needed for |
|---|---|
| `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` | uploading to YouTube Shorts |
| `IG_USER_ID`, `IG_ACCESS_TOKEN`, `PUBLIC_VIDEO_URL` | Instagram Reels |
| `GEMINI_API_KEY` or `GROQ_API_KEY` | drafting scripts for new topics |
| `DMAF_VOICE`, `DMAF_VOICE_RATE`, `DMAF_VOICE_PITCH` | overriding the locked narrator |

Without them the connector still runs: read-only tools work, `dry_run` renders
and gates a film, and publishing returns a clear `skipped` status instead of an
exception.

---

## 6. Verify it yourself

```bash
python -m pytest -q                     # 34 spec tests
python -m connector.server --manifest   # the registration manifest
python draw_me_a_fact.py --list-slate   # what is queued
python draw_me_a_fact.py --episode 11 --publish-mode dry_run
```

The last command writes `output/latest_episode.mp4`, `output/latest_episode.srt`,
`output/youtube_pack.md` and `output/qa_sheet.png`, and prints the QA table.
