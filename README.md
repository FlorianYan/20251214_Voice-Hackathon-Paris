# EchoMind — Voice AI Assistant

A voice AI assistant built with [LiveKit Agents](https://github.com/livekit/agents) and [LiveKit Cloud](https://cloud.livekit.io/). EchoMind can read and write to a connected Notion page and manage tasks in a Notion database.

**Stack:** Gradium STT · OpenAI GPT-4.1-mini · Hume TTS · LiveKit turn detection + noise cancellation

## Setup

```console
uv sync
```

Copy `.env.example` to `.env.local` and fill in:

```
LIVEKIT_URL
LIVEKIT_API_KEY
LIVEKIT_API_SECRET
NOTION_API_KEY
NOTION_PAGE_ID
NOTION_DATABASE_ID
```

## Run

```console
# First run only — download VAD and turn detector models
uv run python src/agent.py download-files

# Talk to the agent in your terminal
uv run python src/agent.py console

# Run for use with a frontend or telephony
uv run python src/agent.py dev

# Production
uv run python src/agent.py start
```

## Test

```console
uv run pytest
```

## Deploy

Includes a production-ready `Dockerfile`. See the [deployment guide](https://docs.livekit.io/agents/ops/deployment/).

## License

MIT — see [LICENSE](LICENSE).
