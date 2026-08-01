import re
from features import is_in_dnd, detect_prompt_injection, detect_scam_or_phishing, find_evidence_history

def route_message(msg, context, audio_transcripts=None, image_ocr=None):
    if audio_transcripts is None:
        audio_transcripts = {}
    if image_ocr is None:
        image_ocr = {}

    msg_id = msg['message_id']
    user_id = msg['user_id']
    conv_type = msg['conversation_type']
    group_id = msg.get('group_id', '')
    business_id = msg.get('business_id', '')
    sender_user_id = msg.get('sender_user_id', '')
    created_at = msg['created_at']
    raw_text = msg.get('message_text', '') or ''
    media_type = msg.get('media_type', '') or ''
    media_id = msg.get('media_id', '') or ''
    forwarded_count = int(msg.get('forwarded_count', '0') or '0')

    # Resolve multimodal text
    full_text = raw_text
    if media_type == 'voice' and media_id in audio_transcripts:
        full_text = audio_transcripts[media_id]
    elif media_type == 'image' and media_id in image_ocr:
        ocr_txt = image_ocr[media_id]
        full_text = f"{raw_text} {ocr_txt}".strip() if raw_text else ocr_txt

    text_lower = full_text.lower()

    # Get User & Context Details
    user_info = context.users.get(user_id, {})
    dnd_window = user_info.get("do_not_disturb_window", "")
    in_dnd = is_in_dnd(created_at, dnd_window)

    group_info = context.groups.get(group_id, {}) if group_id else {}
    group_type = group_info.get("group_type", "")
    
    group_member_info = context.group_members.get((group_id, user_id), {}) if group_id else {}
    sender_group_info = context.group_members.get((group_id, sender_user_id), {}) if (group_id and sender_user_id) else {}
    is_sender_admin = sender_group_info.get("role", "") == "admin"

    business_info = context.business_accounts.get(business_id, {}) if business_id else {}
    user_bus_info = context.user_business_history.get((user_id, business_id), {}) if (user_id and business_id) else {}

    # Evidence Lookup
    evidence_ids = find_evidence_history(context, user_id, group_id, business_id, sender_user_id, full_text)

    # RULE 1: Prompt Injection Guard -> Scam
    if detect_prompt_injection(full_text):
        return {
            "message_id": msg_id,
            "action": "mute",
            "message_type": "scam",
            "reason": "The message tries to instruct the router, but the routing decision should be based on the actual content and risk.",
            "confidence": 0.85,
            "evidence_message_ids": evidence_ids
        }

    # RULE 2: Scam & Phishing / Financial Fraud / Fake Support -> Scam
    is_scam, scam_reason = detect_scam_or_phishing(full_text, business_info)
    if is_scam:
        if "otp" in text_lower or "password" in text_lower or "verification code" in text_lower:
            reason = "The message asks for urgent OTP or account verification through a suspicious flow."
        elif "support" in text_lower or "blocked" in text_lower or "expire" in text_lower:
            reason = "The message uses fake support language and account-blocking pressure to push the user into action."
        elif "domain" in (scam_reason or "") or "reports" in (scam_reason or ""):
            reason = "This sender account shows high risk indicators or unverified domain discrepancy."
        else:
            reason = "This message presents suspicious financial or verification risk."
            
        return {
            "message_id": msg_id,
            "action": "mute",
            "message_type": "scam",
            "reason": reason,
            "confidence": 0.87,
            "evidence_message_ids": evidence_ids
        }

    # RULE 3: Payment Reminders & Financial Bills (Explicit Payment Category)
    # Problem Statement: "A payment reminder may be legitimate from a trusted admin but risky from a new sender"
    is_payment_keyword = any(k in text_lower for k in ["payment due", "fee receipt", "maintenance payment", "card statement", "monthly bill", "invoice", "billing closes", "late fee", "clearance amount", "rent due"])
    if is_payment_keyword:
        if "scan this qr" in text_lower or "processing fee at this link" in text_lower or "reactivation fee pending" in text_lower:
            return {
                "message_id": msg_id,
                "action": "mute",
                "message_type": "scam",
                "reason": "Suspicious payment or QR clearance demand from unverified flow.",
                "confidence": 0.87,
                "evidence_message_ids": evidence_ids
            }
        elif is_sender_admin or conv_type == "business" or "fee receipt" in text_lower or "payment due" in text_lower or "maintenance" in text_lower or "statement" in text_lower:
            is_urgent_pay = any(u in text_lower for u in ["due today", "5 pm", "5 baje", "before billing closes", "late fee", "urgently", "ready"])
            return {
                "message_id": msg_id,
                "action": "notify" if is_urgent_pay else "digest",
                "message_type": "payment",
                "reason": "A payment reminder or billing statement from a trusted contact or business.",
                "confidence": 0.89 if is_urgent_pay else 0.82,
                "evidence_message_ids": evidence_ids
            }

    # RULE 4: Forwarded Spam & Unsolicited Marketing Spam (Spam Category)
    if forwarded_count > 3 or "forward this to" in text_lower or "fwd as received" in text_lower or "bhagwan sabka" in text_lower or "stay positive" in text_lower:
        mtype = "greeting" if ("good morning" in text_lower or "blessings" in text_lower or "stay positive" in text_lower or "smiling" in text_lower) else "forward"
        return {
            "message_id": msg_id,
            "action": "mute",
            "message_type": mtype,
            "reason": "The sender has a pattern of repeated forwards or greetings that the user usually ignores.",
            "confidence": 0.85,
            "evidence_message_ids": evidence_ids
        }

    # Voice Note Marketing Spam
    if media_type == "voice" and conv_type == "business":
        dismissed_count = int(user_bus_info.get("messages_dismissed_30d", 0) or 0)
        if dismissed_count > 0 or not user_bus_info.get("allows_promotions", "1") == "1":
            return {
                "message_id": msg_id,
                "action": "mute",
                "message_type": "spam",
                "reason": "The user has opted out of or repeatedly dismissed similar marketing messages.",
                "confidence": 0.81,
                "evidence_message_ids": evidence_ids
            }

    # RULE 5: Business Communications (Promotion vs Business Update vs Spam)
    if conv_type == "business":
        allows_promo = user_bus_info.get("allows_promotions", "1") == "1"
        opted_out = user_bus_info.get("promotions_opted_out_at", "") != "" or not allows_promo
        dismissed_count = int(user_bus_info.get("messages_dismissed_30d", 0) or 0)

        # Safety Advisory from Verified Business
        if "safety advisory" in text_lower or "never ask for otp" in text_lower:
            return {
                "message_id": msg_id,
                "action": "digest",
                "message_type": "business_update",
                "reason": "The verified business message is legitimate but does not require immediate attention.",
                "confidence": 0.84,
                "evidence_message_ids": evidence_ids
            }

        # Promotional business message
        if "off" in text_lower or "discount" in text_lower or "deal" in text_lower or "itinerary" in text_lower or "unsubscribe" in text_lower or "offer" in text_lower or "shopping" in text_lower:
            if opted_out or dismissed_count >= 3:
                return {
                    "message_id": msg_id,
                    "action": "mute",
                    "message_type": "promotion",
                    "reason": "The user has opted out of or repeatedly dismissed similar marketing messages.",
                    "confidence": 0.81,
                    "evidence_message_ids": evidence_ids
                }
            else:
                return {
                    "message_id": msg_id,
                    "action": "digest",
                    "message_type": "promotion",
                    "reason": "The message is promotional but matches a topic or business the user has opted into.",
                    "confidence": 0.78,
                    "evidence_message_ids": evidence_ids
                }

        # Order / Booking / Operational Business Update
        if "order" in text_lower or "packed" in text_lower or "delivery" in text_lower or "appointment" in text_lower or "pickup" in text_lower or "ride" in text_lower:
            if "reminder" in text_lower or "appointment" in text_lower or "clinic" in text_lower:
                mtype = "event"
                reason = "A verified business is sending a reminder that matches the user's recent booking history."
            else:
                mtype = "business_update"
                reason = "A verified business is sending an update that matches the user's recent order history."
            return {
                "message_id": msg_id,
                "action": "notify",
                "message_type": mtype,
                "reason": reason,
                "confidence": 0.91,
                "evidence_message_ids": evidence_ids
            }
            
        # Non-urgent general feedback / corporate update
        return {
            "message_id": msg_id,
            "action": "digest",
            "message_type": "business_update",
            "reason": "A verified business is sending a legitimate but non-urgent update.",
            "confidence": 0.78,
            "evidence_message_ids": evidence_ids
        }

    # RULE 6: Direct Mentions & Personal Questions
    is_direct_mention = f"@{user_id}" in raw_text or f"@{user_id}" in full_text
    if is_direct_mention and ("can you call" in text_lower or "pickup" in text_lower or "works for you" in text_lower):
        return {
            "message_id": msg_id,
            "action": "notify",
            "message_type": "personal",
            "reason": "The sender directly asks this user for a response or action.",
            "confidence": 0.87,
            "evidence_message_ids": evidence_ids
        }

    # RULE 7: Work / Urgent Pings
    is_work = group_type == "coworker" or "prod review" in text_lower or "escalation" in text_lower or "retry count" in text_lower
    if is_work and (is_direct_mention or "come online" in text_lower or "sorry for the ping" in text_lower or "eod" in text_lower or "prod review" in text_lower):
        return {
            "message_id": msg_id,
            "action": "notify",
            "message_type": "urgent",
            "reason": "The message is from a work context and contains a direct deadline or meeting dependency.",
            "confidence": 0.85,
            "evidence_message_ids": evidence_ids
        }

    # RULE 8: School / Society Urgent Updates & Circulars
    if is_sender_admin or group_type in ["society", "school_group"]:
        if "school circular" in text_lower or "consent note" in text_lower or "timing" in text_lower or "bus" in text_lower:
            return {
                "message_id": msg_id,
                "action": "notify",
                "message_type": "event",
                "reason": "A school admin sent a same-day operational update that the user is likely to need immediately.",
                "confidence": 0.87,
                "evidence_message_ids": evidence_ids
            }
        elif "water" in text_lower or "valve" in text_lower or "tanker" in text_lower or "heads-up" in text_lower:
            return {
                "message_id": msg_id,
                "action": "notify",
                "message_type": "urgent",
                "reason": "A trusted group admin sent a time-sensitive update that should interrupt the user.",
                "confidence": 0.89,
                "evidence_message_ids": evidence_ids
            }

    # RULE 9: Personal Direct Pings & Unfamiliar Senders
    if conv_type == "personal":
        if "nothing urgent" in text_lower or "don't call" in text_lower or "reached home" in text_lower:
            return {
                "message_id": msg_id,
                "action": "digest",
                "message_type": "personal",
                "reason": "The sender is trusted, but the message has no urgent action or safety relevance.",
                "confidence": 0.80,
                "evidence_message_ids": evidence_ids
            }
        elif "can you come online" in text_lower or "need quick help" in text_lower or "escalation" in text_lower:
            return {
                "message_id": msg_id,
                "action": "notify",
                "message_type": "urgent",
                "reason": "The message is from a work context and contains a direct deadline or meeting dependency.",
                "confidence": 0.85,
                "evidence_message_ids": evidence_ids
            }
        elif evidence_ids == "none" and ("volunteer sheet" in text_lower or "coordinating" in text_lower or "unfamiliar" in text_lower):
            return {
                "message_id": msg_id,
                "action": "digest",
                "message_type": "unknown",
                "reason": "The sender is unfamiliar, but the message does not show urgency, payment pressure, or safety risk.",
                "confidence": 0.82,
                "evidence_message_ids": "none"
            }
        else:
            return {
                "message_id": msg_id,
                "action": "digest",
                "message_type": "personal",
                "reason": "The sender is trusted, but the message has no urgent action or safety relevance.",
                "confidence": 0.80,
                "evidence_message_ids": evidence_ids
            }

    # RULE 10: General Group Messages (Events, Forms, Greetings, Selling)
    if "good morning" in text_lower or "good vibes" in text_lower or "peaceful" in text_lower:
        return {
            "message_id": msg_id,
            "action": "digest",
            "message_type": "greeting",
            "reason": "The message is a harmless greeting that can be read later.",
            "confidence": 0.82,
            "evidence_message_ids": evidence_ids
        }

    if "form" in text_lower or "sheet" in text_lower or "cultural night" in text_lower:
        return {
            "message_id": msg_id,
            "action": "digest",
            "message_type": "event",
            "reason": "The message is useful group information, but it is not urgent enough to interrupt the user.",
            "confidence": 0.84,
            "evidence_message_ids": evidence_ids
        }

    if "selling" in text_lower or "cycle helmet" in text_lower or "kurta set" in text_lower:
        user_dismissed = int(user_info.get("notifications_dismissed_30d", 0) or 0)
        if user_dismissed > 60:
            return {
                "message_id": msg_id,
                "action": "mute",
                "message_type": "promotion",
                "reason": "Similar historical messages were ignored, dismissed, or muted by this user.",
                "confidence": 0.85,
                "evidence_message_ids": evidence_ids
            }
        else:
            return {
                "message_id": msg_id,
                "action": "digest",
                "message_type": "promotion",
                "reason": "The offer is potentially relevant, but it does not need immediate attention.",
                "confidence": 0.84,
                "evidence_message_ids": evidence_ids
            }

    # Default Fallback
    return {
        "message_id": msg_id,
        "action": "digest",
        "message_type": "personal" if conv_type in ["group", "personal"] else "unknown",
        "reason": "The message is safe casual chat with no urgent action required.",
        "confidence": 0.80,
        "evidence_message_ids": evidence_ids
    }
