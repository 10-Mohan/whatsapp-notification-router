# HackerRank Orchestrate — Message Notification Router

An AI-powered multimodal system for WhatsApp that evaluates incoming text, voice notes, image posters/screenshots, sender authority, quiet hours, business security, and user history to make personalized routing decisions (`notify`, `digest`, `mute`).

---

## 🛠️ Environment Setup & Installation

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.13)
- `pip` package manager

### 2. Install Dependencies
Install all required libraries including PyTorch, OpenAI Whisper, EasyOCR, and imageio-ffmpeg:

```bash
pip install -r requirements.txt
```

---

## 🚀 Running the System

### 1. Generate Prediction File (`dataset/output.csv`)
To run the full end-to-end routing pipeline across all incoming messages in `dataset/messages.csv`:

```bash
python code/main.py
```

This script:
- Loads multimodal media (Whisper ASR for audio voice notes, EasyOCR for image posters).
- Builds relational graph features (`users.csv`, `groups.csv`, `group_members.csv`, `business_accounts.csv`, `user_business_history.csv`, `message_history.csv`, `message_events.csv`).
- Evaluates scam risk, domain integrity, prompt injection attacks, quiet hours (`do_not_disturb_window`), and admin authority.
- Outputs `dataset/output.csv` matching the required schema contract.

### 2. Evaluate Accuracy Benchmark
To test accuracy against solved sample cases in `dataset/sample_messages.csv`:

```bash
python code/evaluation/main.py
```

### 3. Create Submission Package (`code.zip`)
To package the solution into a submission-ready archive:

```bash
python code/package.py
```

---

## 🌐 Interactive Web Dashboard Application

An interactive web application & live simulator is available under `web/`:

### Launching Locally
Start a local HTTP server:
```bash
python -m http.server 8000 --directory web
```
Open **`http://localhost:8000`** in your browser.

Alternatively, double-click [`index.html`](./index.html) directly in any web browser.

---

## 📋 Submission Deliverables

1. **Predictions CSV**: `dataset/output.csv` (1:1 matching row count for `dataset/messages.csv`)
2. **Runnable Code Package**: `code.zip`
3. **Chat Transcript**: `%USERPROFILE%\hackerrank_orchestrate_august26\log.txt` (or `$HOME/hackerrank_orchestrate_august26/log.txt`)

---

## 🏛️ System Architecture

```text
Incoming Message (Text / Image / Voice Note)
   │
   ├── Multimodal Ingestion (Whisper ASR + EasyOCR)
   ├── Relational Context Graph (Users + Groups + Businesses + History)
   ├── Safety & Scam Defense (Domain Audit + Phishing + Prompt Injection)
   └── Decision Engine -> output.csv (action, message_type, reason, confidence, evidence_message_ids)
```
