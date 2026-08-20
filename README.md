# PingSense

An AI-powered notification router for WhatsApp. PingSense reasons over incoming messages — text, image posters/screenshots, and voice notes — and decides whether each one deserves an immediate **notify**, a batched **digest**, or a silent **mute**.

## Why

WhatsApp is noisy. Family chats, society notices, school updates, co-worker messages, business promotions, image posters, voice notes, and the occasional scam all land in the same stream. Treating every message the same way creates two failure modes:

- **Important messages get buried** in the noise.
- **Low-value or risky messages interrupt** the user anyway.

PingSense uses message content, sender/group metadata, and a user's historical behavior to make that call automatically — and explains *why* for every decision.

## What It Does

For every message in the input dataset, PingSense outputs:

| Field | Description |
|---|---|
| `message_id` | ID of the incoming message |
| `action` | `notify`, `digest`, or `mute` |
| `message_type` | Best-fit category for the message |
| `reason` | Short, human-readable explanation for the decision |
| `confidence` | Score from `0` to `1` |
| `evidence_message_ids` | Historical messages used to support the decision (`none` if not applicable) |

Decisions are personalized per user, drawing on:

- Message content (text, OCR'd images, transcribed voice notes)
- Sender and group metadata
- Business account history
- Past user reactions to similar messages

## Google AI Models Powered

PingSense leverages cutting-edge **Google AI Models** to deliver real-time multimodal notification routing:

- **Gemini 2.5 Flash / Gemini 3.5 Flash** (`google-genai` SDK): Primary high-speed multimodal reasoning model for real-time text, voice transcript, and OCR image signal classification.
- **Gemini 1.5 Pro**: Heavyweight contextual model for complex multi-turn behavioral history and quiet hours reasoning.
- **Gemma 2B / Gemma 7B**: On-device Small Language Model (SLM) fallback for local offline processing without cloud latency.

```bash
# Set your Google Gemini API key to enable Gemini AI routing
export GEMINI_API_KEY="your-gemini-api-key"
export GEMINI_MODEL="gemini-2.5-flash"
```

## Repository Layout

```
.
├── code/                     # Solution source code
├── dataset/                  # Input data, context files, and media
│   ├── messages.csv
│   ├── sample_messages.csv
│   ├── users.csv
│   ├── groups.csv
│   ├── group_members.csv
│   ├── business_accounts.csv
│   ├── user_business_history.csv
│   ├── message_history.csv
│   ├── message_events.csv
│   ├── images.csv
│   ├── voice_notes.csv
│   ├── daily_notification_summary.csv
│   ├── output.csv            # Blank submission template
│   └── media/
│       ├── images/
│       └── audio/
├── web/                       # Supporting web assets
├── problem_statement.md       # Full challenge spec
├── AGENTS.md                  # Rules + transcript logging for AI coding tools
└── README.md
```

## How It Works

1. **Ingest** — load `messages.csv` alongside all relevant context files (users, groups, business accounts, history).
2. **Understand** — extract signal from each message: run OCR on images, transcribe voice notes, and parse text content.
3. **Retrieve** — pull relevant historical messages and past user reactions as evidence.
4. **Reason** — combine content, metadata, and behavioral history to decide `notify` / `digest` / `mute`, using an LLM, retrieval, rules, or a hybrid pipeline.
5. **Output** — write one row per message to `output.csv` with a reason and confidence score.

## Getting Started

```bash
# clone the repo
git clone https://github.com/10-Mohan/whatsapp-notification-router.git
cd whatsapp-notification-router

# install dependencies (adjust to whatever runtime you use)
pip install -r requirements.txt   # or: npm install

# set any required API keys as environment variables — never hardcode secrets
export OPENAI_API_KEY=...

# run the router
python code/run.py --input dataset/messages.csv --output dataset/output.csv
```

> Adjust the run command to match your actual entry point and language (Python, JavaScript, and TypeScript are all fair game).

## Requirements

Your solution must:

- Run from the terminal
- Read input from `dataset/`
- Produce a valid `output.csv` with one row per `message_id`
- Avoid organizer-only files or hardcoded labels
- Read secrets from environment variables, never hardcode them

## Evaluation

Predictions are scored against hidden ground-truth labels on:

- Correctness of `action`
- Correctness of `message_type`
- Usefulness and consistency of `reason`
- Relevance of `evidence_message_ids`
- Confidence calibration

Strong solutions typically combine retrieval, structured metadata, behavioral history, safety checks, OCR/ASR handling, and contextual reasoning.

## Submission Checklist

- [ ] `output.csv` has one row per row in `dataset/messages.csv`
- [ ] `output.csv` columns match the required schema exactly
- [ ] `code.zip` includes runnable code, prompts/configs, and setup instructions
- [ ] Chat transcript (`log.txt`, see `AGENTS.md`) is included
- [ ] No secrets committed to the repo

## License

MIT License
