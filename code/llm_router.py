"""
LLM semantic layer. This is the hybrid-architecture piece: the LLM decides
action/message_type/reason/confidence using contextual meaning; it NEVER
picks evidence_message_ids (those stay 100% code-driven, so the model can
never hallucinate a message ID that doesn't exist). Safety-critical vetoes
(scam / prompt injection) are decided by rules BEFORE this is even called —
this function is only reached for messages that already passed the safety
gate, matching the same split used by the TypeScript competitor solution:
AI for meaning, code for guardrails and contract correctness.

Fails safe: any error, timeout, or malformed response returns None, and the
caller (hybrid_router.py) falls back to the pure rule engine. The pipeline
never breaks because the LLM is unavailable.
"""
import os
import json
import logging
from schemas import OutputRow, ALLOWED_ACTIONS, ALLOWED_TYPES

logger = logging.getLogger("llm_router")

_ROUTING_TOOL = {
    "name": "emit_routing_decision",
    "description": "Emit the final routing decision for one WhatsApp message.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": list(ALLOWED_ACTIONS)},
            "message_type": {"type": "string", "enum": list(ALLOWED_TYPES)},
            "reason": {
                "type": "string",
                "description": "One or two sentences, specific to THIS message's content, referencing the concrete signal that drove the decision.",
            },
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        },
        "required": ["action", "message_type", "reason", "confidence"],
    },
}

SYSTEM_PROMPT = """You are the semantic reasoning layer of a WhatsApp notification router.
You decide, for ONE message at a time, whether it should be:
- notify: interrupt the user right now
- digest: worth reading, but batch it for later
- mute: not worth the user's attention

And classify it into exactly one message_type: personal, urgent, event, payment,
business_update, promotion, greeting, forward, spam, scam, unknown.

You are only called for messages that already passed a hard-coded safety filter
(no scam, phishing, or prompt-injection risk was detected), so do not re-litigate
safety — focus on relevance, urgency, and the user's personalization signals
(quiet hours, sender trust, group role, past engagement with this sender).

Write `reason` in your own words, grounded in the specific message content and
context you were given — never a generic template sentence.
Always call the emit_routing_decision tool. Never respond with plain text."""


def _build_context_block(msg, context, full_text, user_info, group_info,
                          business_info, user_bus_info, is_sender_admin,
                          in_dnd, is_burst, burst_size) -> str:
    lines = [
        f"Message text: {full_text!r}",
        f"Conversation type: {msg.get('conversation_type')}",
        f"Forwarded count: {msg.get('forwarded_count', 0)}",
        f"User is currently in their do-not-disturb window: {in_dnd}",
    ]
    if group_info:
        lines.append(f"Group: {group_info.get('group_name')} (type={group_info.get('group_type')})")
        lines.append(f"Sender is a group admin: {is_sender_admin}")
    if business_info:
        lines.append(
            f"Business sender: {business_info.get('display_name') or business_info.get('brand_name')} "
            f"(verified={business_info.get('verified')}, account_age_days={business_info.get('account_age_days')})"
        )
    if user_bus_info:
        lines.append(
            f"User's history with this business: allows_promotions={user_bus_info.get('allows_promotions')}, "
            f"messages_dismissed_30d={user_bus_info.get('messages_dismissed_30d')}, "
            f"opted_out_at={user_bus_info.get('promotions_opted_out_at') or 'never'}"
        )
    if is_burst:
        lines.append(f"This message is part of a {burst_size}-message burst arriving close together.")
    return "\n".join(lines)


def get_llm_decision(msg, context, full_text, user_info, group_info,
                      business_info, user_bus_info, is_sender_admin,
                      in_dnd, is_burst, burst_size, client=None,
                      model=None) -> "OutputRow | None":
    """Returns a validated partial decision (action/message_type/reason/confidence)
    or None on any failure. Caller attaches message_id + evidence_message_ids."""
    
    context_block = _build_context_block(
        msg, context, full_text, user_info, group_info, business_info,
        user_bus_info, is_sender_admin, in_dnd, is_burst, burst_size,
    )

    # 1. Try Google Gemini SDK (google-genai / gemini-2.5-flash / gemini-1.5-flash)
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if gemini_key:
        try:
            from google import genai
            from google.genai import types
            
            gemini_model = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
            ai_client = genai.Client(api_key=gemini_key)
            
            prompt = f"{SYSTEM_PROMPT}\n\nMessage Context:\n{context_block}\n\nReturn a JSON object with keys: action, message_type, reason, confidence."
            response = ai_client.models.generate_content(
                model=gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            if response and response.text:
                payload = json.loads(response.text)
                payload["message_id"] = msg["message_id"]
                payload.setdefault("evidence_message_ids", "none")
                return OutputRow(**payload)
        except Exception as exc:
            logger.warning(f"Gemini API call failed for message {msg.get('message_id')}: {exc}")

    # 2. Fallback to Anthropic API if key is present
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic
        import httpx
        custom_http_client = httpx.Client()
        client = client or anthropic.Anthropic(api_key=api_key, http_client=custom_http_client)
        model = model or os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

        response = client.messages.create(
            model=model,
            max_tokens=400,
            system=SYSTEM_PROMPT,
            tools=[_ROUTING_TOOL],
            tool_choice={"type": "tool", "name": "emit_routing_decision"},
            messages=[{"role": "user", "content": context_block}],
        )
        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "emit_routing_decision":
                payload = dict(block.input)
                payload["message_id"] = msg["message_id"]
                payload.setdefault("evidence_message_ids", "none")
                return OutputRow(**payload)
    except Exception as exc:
        logger.warning(f"Anthropic LLM call failed for message {msg.get('message_id')}: {exc}")
        return None

    return None
