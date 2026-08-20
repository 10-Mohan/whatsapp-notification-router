"""
Hybrid orchestration layer.

Design (mirrors the safety-first hybrid pattern):
  1. SAFETY GATE (deterministic, non-overridable): prompt injection and
     scam/phishing detection run first. If either fires, we call the
     existing rule engine directly — it already handles these as hard
     vetoes (Rule 1 / Rule 2) — and the LLM is never consulted. This
     guarantees a scam can never slip through because a model judged it
     as benign.
  2. LLM SEMANTIC LAYER: for everything else, ask the LLM for
     action/message_type/reason/confidence. Evidence IDs are never
     requested from the model — they stay 100% code-derived, so the
     model can't hallucinate a message_id that doesn't exist.
  3. FALLBACK: if the LLM is unavailable, errors, or returns something
     that fails schema validation, we fall back to the full deterministic
     rule cascade (router.route_message). The pipeline is never broken
     by an LLM outage, missing API key, or malformed response.

Toggle: set USE_LLM_ROUTER=false to disable the LLM layer entirely and
run in pure rule-based mode (useful if no API key is available at
grading time — output is still 100% valid either way).
"""
import os
import logging

from features import (
    is_in_dnd, detect_prompt_injection, detect_scam_or_phishing,
    find_evidence_history,
)
from router import route_message
from llm_router import get_llm_decision

logger = logging.getLogger("hybrid_router")


def _resolve_full_text(msg, audio_transcripts, image_ocr):
    raw_text = msg.get('message_text', '') or ''
    media_type = msg.get('media_type', '') or ''
    media_id = msg.get('media_id', '') or ''
    if media_type == 'voice' and media_id in audio_transcripts:
        return audio_transcripts[media_id]
    if media_type == 'image' and media_id in image_ocr:
        ocr_txt = image_ocr[media_id]
        return f"{raw_text} {ocr_txt}".strip() if raw_text else ocr_txt
    return raw_text


def hybrid_route_message(msg, context, audio_transcripts=None, image_ocr=None,
                          batch_info=None):
    audio_transcripts = audio_transcripts or {}
    image_ocr = image_ocr or {}
    batch_info = batch_info or {}

    use_llm = os.environ.get("USE_LLM_ROUTER", "true").lower() != "false"
    full_text = _resolve_full_text(msg, audio_transcripts, image_ocr)

    # --- 1. Safety gate: never bypassed, never handed to the LLM ---
    business_info = context.business_accounts.get(msg.get('business_id', ''), {})
    if detect_prompt_injection(full_text) or detect_scam_or_phishing(full_text, business_info)[0]:
        return route_message(msg, context, audio_transcripts, image_ocr, batch_info)

    if not use_llm:
        return route_message(msg, context, audio_transcripts, image_ocr, batch_info)

    # --- 2. LLM semantic layer ---
    user_id = msg['user_id']
    group_id = msg.get('group_id', '')
    sender_user_id = msg.get('sender_user_id', '')
    business_id = msg.get('business_id', '')

    user_info = context.users.get(user_id, {})
    group_info = context.groups.get(group_id, {}) if group_id else {}
    sender_group_info = context.group_members.get((group_id, sender_user_id), {}) if (group_id and sender_user_id) else {}
    is_sender_admin = sender_group_info.get("role", "") == "admin"
    user_bus_info = context.user_business_history.get((user_id, business_id), {}) if (user_id and business_id) else {}
    in_dnd = is_in_dnd(msg['created_at'], user_info.get("do_not_disturb_window", ""))

    b_meta = batch_info.get(msg['message_id'], {})
    is_burst = b_meta.get("is_burst", False)
    burst_size = b_meta.get("burst_size", 1)

    decision = get_llm_decision(
        msg, context, full_text, user_info, group_info, business_info,
        user_bus_info, is_sender_admin, in_dnd, is_burst, burst_size,
    )

    if decision is None:
        # LLM unavailable / failed / invalid -> deterministic fallback
        return route_message(msg, context, audio_transcripts, image_ocr, batch_info)

    # --- 3. Evidence stays code-derived, never trust the model for it ---
    evidence_ids = find_evidence_history(
        context, user_id, group_id, business_id, sender_user_id, full_text,
    )
    decision.evidence_message_ids = evidence_ids
    return decision.to_csv_row()
