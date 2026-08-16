# ContResAI

ContResAI is a continuous research workspace. You give it a question. It searches a reviewed set of websites, writes a research draft, checks every factual claim, and then builds a connected knowledge graph from the claims that passed.

The important rule is simple: **the browser agent cannot write trusted knowledge**. Browser text is treated like a note handed in by a stranger. A separate verifier must find the same words in an approved, freely accessible source before a claim is trusted.

## How information moves

```text
Your topic and existing confirmed facts
                 |
                 v
Groq Compound searches exact approved domains
                 |
                 v
Untrusted research draft, claims, links, and hypotheses
                 |
                 v
URL, redirect, DNS, file-size, and prompt-injection checks
                 |
                 v
The application downloads accessible evidence itself
                 |
                 v
Tool-free GPT-OSS verifier must return exact excerpts
                 |
        +--------+--------+----------+
        |                 |          |
    confirmed         contested   unverified
        |                 |          |
 trusted graph       conflict     research lead
```

A hypothesis never becomes a proven fact. Confirming its supporting claims only raises the hypothesis's confidence label.

## What is included

- A FastAPI API and restart-safe PostgreSQL worker.
- PostgreSQL with pgvector for the local knowledge graph.
- A React dashboard with an Obsidian-style graph, research drafts, citations, verification states, hypotheses, and a source-catalog drawer.
- 112 reviewed source rules across journals, governments, universities, standards bodies, public data, news, and business publications.
- Discovery-only rules for paywalled publications. Their text cannot be used as evidence.
- `groq/compound` with only the `web_search` tool and exact domain batches.
- Tool-free `openai/gpt-oss-20b` parsing and evidence verification.
- Local URL, DNS/SSRF, redirect, content, prompt-injection, excerpt, quota, and audit controls.
- Daily scheduling and manual research or verification runs.

## Start it locally

You need Docker, Python 3.13, `uv`, pnpm 10, and Node 24. The `.node-version` file tells Node version managers which Node version to use.

1. Copy the example settings:

   ```bash
   cp .env.example .env
   ```

2. Put your Groq key after `GROQ_API_KEY=` in `.env`. Never commit this file.

3. Install everything:

   ```bash
   pnpm run setup
   ```

   The word `run` matters because `pnpm setup` is a different pnpm command.

4. Start the database and create its tables:

   ```bash
   pnpm dev:db
   pnpm db:migrate
   ```

5. Start the API, worker, and dashboard together:

   ```bash
   pnpm dev
   ```

6. Open the React Dashboard.

Create a topic, choose a precise question, and press **Run research**. The first result is always a draft. Press **Verify draft** to run the independent evidence checks.

## Everyday development commands

```bash
pnpm test          # unit and safety tests
pnpm test:e2e      # real browser test
pnpm lint          # readability and correctness rules
pnpm typecheck     # Python and TypeScript type checks
```

Development is test-driven. Start with a test that describes the behavior, watch it fail, write the smallest readable solution, and then clean it up.

## Safety model, from first principles

- **Approved search space:** the model receives only exact hostnames from `config/source_catalog.yaml`. The catalog is split into small topic-relevant batches.
- **Small tool box:** Compound gets web search only. It receives no shell, code runner, database, secrets, source-control, or write tool.
- **Untrusted drafts:** reports, snippets, titles, connections, and insights remain outside the trusted graph.
- **Independent fetching:** the application checks HTTPS, credentials, ports, hostname, allowed path, every redirect, and every resolved IP address before reading a page.
- **Injection checks:** obvious instruction-shaped text is blocked locally, and downloaded evidence is checked again with Prompt Guard.
- **Exact evidence:** a verifier's quotation must literally exist inside the downloaded and cleaned document. A made-up quotation is discarded.
- **Corroboration:** an important conclusion needs at least two source hostnames or it remains only partially confirmed.
- **Visible disagreement:** supporting and conflicting excerpts are both saved. The result becomes contested.
- **No paywall shortcuts:** snippets and discovery-only pages can suggest a lead, but cannot confirm it.
- **Free-tier stop:** the quota manager reserves requests before network calls. When its hard limit is reached, the worker pauses instead of choosing a paid model.
- **Audit trail:** model calls, searches, rejections, drafts, confirmations, failures, and quota decisions are stored as events or ledgers.

These controls reduce risk; they do not make arbitrary internet browsing perfectly safe. Keep the source catalog narrow, review rule changes, and treat hypotheses as ideas to investigate—not answers that were proven.

## Main API routes

- `GET /api/topics/{topic_id}/research-drafts`
- `GET /api/research-drafts/{draft_id}`
- `POST /api/research-drafts/{draft_id}/verify`
- `GET /api/research-drafts/{draft_id}/verification`
- `GET /api/topics/{topic_id}/candidate-insights`
- `PATCH /api/candidate-insights/{insight_id}`
- `GET /api/topics/{topic_id}/graph`
- `GET /api/source-catalog`

Interactive API documentation is available at `http://127.0.0.1:8000/docs` while the server is running.

## Project map

- `backend/src/research_agent/` — API, worker, models, research, verification, and safety code.
- `backend/tests/` — isolated safety and behavior tests with no real model calls.
- `frontend/src/` — dashboard and graph interface.
- `config/source_catalog.yaml` — versioned source rules.
- `AGENTS.md` — simple conventions for future coding agents.
- `.context/` — the approved RPI plans and architecture diagram used to design this build.
