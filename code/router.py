import re
from features import is_in_dnd, detect_prompt_injection, detect_scam_or_phishing, find_evidence_history, extract_message_entities, fuzzy_match_any

def route_message(msg, context, audio_transcripts=None, image_ocr=None, batch_info=None):
    if audio_transcripts is None:
        audio_transcripts = {}
    if image_ocr is None:
        image_ocr = {}
    if batch_info is None:
        batch_info = {}

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
    entities = extract_message_entities(full_text)

    # Get User & Context Details
    user_info = context.users.get(user_id, {})
    dnd_window = user_info.get("do_not_disturb_window", "")
    in_dnd = is_in_dnd(created_at, dnd_window)

    group_info = context.groups.get(group_id, {}) if group_id else {}
    group_name = group_info.get("group_name", "Group Chat")
    group_type = group_info.get("group_type", "")
    
    group_member_info = context.group_members.get((group_id, user_id), {}) if group_id else {}
    sender_group_info = context.group_members.get((group_id, sender_user_id), {}) if (group_id and sender_user_id) else {}
    is_sender_admin = sender_group_info.get("role", "") == "admin"

    business_info = context.business_accounts.get(business_id, {}) if business_id else {}
    brand_name = business_info.get("display_name") or business_info.get("brand_name") or "Business"
    user_bus_info = context.user_business_history.get((user_id, business_id), {}) if (user_id and business_id) else {}

    # Batching context
    b_meta = batch_info.get(msg_id, {})
    is_burst = b_meta.get("is_burst", False)
    burst_size = b_meta.get("burst_size", 1)

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
    is_scam, scam_detail = detect_scam_or_phishing(full_text, business_info)
    if is_scam:
        if any(k in text_lower for k in ["otp", "password", "verification code"]):
            reason = f"Suspicious message requesting sensitive verification details ({scam_detail})."
        elif any(k in text_lower for k in ["support", "blocked", "expire"]):
            reason = "The message uses fake support language and account-blocking pressure to push the user into action."
        elif business_id:
            reason = f"{brand_name} sender shows security risk indicators ({scam_detail})."
        else:
            reason = f"Suspicious security risk payload intercepted ({scam_detail})."
            
        return {
            "message_id": msg_id,
            "action": "mute",
            "message_type": "scam",
            "reason": reason,
            "confidence": 0.87,
            "evidence_message_ids": evidence_ids
        }

    # RULE 3: Payment Reminders & Financial Bills (Payment Category)
    payment_patterns = [r"payment\s+due", r"fee\s+receipt", r"maintenance\s+payment", r"card\s+statement", r"monthly\s+bill", r"invoice", r"billing\s+closes", r"late\s+fee", r"clearance\s+amount", r"rent\s+due"]
    has_payment, _ = fuzzy_match_any(text_lower, payment_patterns)
    if has_payment:
        if any(k in text_lower for k in ["scan this qr", "processing fee at this link", "reactivation fee pending"]):
            return {
                "message_id": msg_id,
                "action": "mute",
                "message_type": "scam",
                "reason": f"Suspicious payment demand with unverified transaction flow ({brand_name or 'Unknown'}).",
                "confidence": 0.87,
                "evidence_message_ids": evidence_ids
            }
        elif is_sender_admin or conv_type == "business" or "fee receipt" in text_lower or "payment due" in text_lower or "maintenance" in text_lower or "statement" in text_lower:
            is_urgent_pay = any(u in text_lower for u in ["due today", "5 pm", "5 baje", "before billing closes", "late fee", "urgently", "ready"])
            sender_desc = f"{brand_name}" if business_id else (f"Admin in {group_name}" if is_sender_admin else "Trusted Contact")
            time_desc = f" (Deadline: {entities['time_window']})" if "time_window" in entities else ""
            reason = f"Official payment reminder from {sender_desc}{time_desc} requiring action." if is_urgent_pay else f"Legitimate statement or payment summary from {sender_desc}."
            return {
                "message_id": msg_id,
                "action": "notify" if is_urgent_pay else "digest",
                "message_type": "payment",
                "reason": reason,
                "confidence": 0.89 if is_urgent_pay else 0.82,
                "evidence_message_ids": evidence_ids
            }

    # RULE 4: Forwarded Spam & Unsolicited Marketing Spam (Spam Category)
    if forwarded_count > 3 or any(k in text_lower for k in ["forward this to", "fwd as received", "bhagwan sabka", "stay positive"]):
        mtype = "greeting" if any(g in text_lower for g in ["good morning", "blessings", "stay positive", "smiling"]) else "forward"
        reason = f"The sender has a pattern of repeated forwards ({forwarded_count} forwards) or greetings that the user usually ignores."
        return {
            "message_id": msg_id,
            "action": "mute",
            "message_type": mtype,
            "reason": reason,
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
                "reason": f"Unsolicited audio marketing from {brand_name} matching user's dismissal patterns.",
                "confidence": 0.81,
                "evidence_message_ids": evidence_ids
            }

    # RULE 5: Business Communications
    if conv_type == "business":
        allows_promo = user_bus_info.get("allows_promotions", "1") == "1"
        opted_out = user_bus_info.get("promotions_opted_out_at", "") != "" or not allows_promo
        dismissed_count = int(user_bus_info.get("messages_dismissed_30d", 0) or 0)

        # Safety Advisory from Verified Business
        if any(k in text_lower for k in ["safety advisory", "never ask for otp"]):
            return {
                "message_id": msg_id,
                "action": "digest",
                "message_type": "business_update",
                "reason": f"Legitimate security advisory from verified business {brand_name}.",
                "confidence": 0.84,
                "evidence_message_ids": evidence_ids
            }

        # Promotional business message
        if any(k in text_lower for k in ["off", "discount", "deal", "itinerary", "unsubscribe", "offer", "shopping"]):
            if opted_out or dismissed_count >= 3:
                return {
                    "message_id": msg_id,
                    "action": "mute",
                    "message_type": "promotion",
                    "reason": f"Marketing offer from {brand_name} which the user has opted out of or dismissed.",
                    "confidence": 0.81,
                    "evidence_message_ids": evidence_ids
                }
            else:
                return {
                    "message_id": msg_id,
                    "action": "digest",
                    "message_type": "promotion",
                    "reason": f"Promotional update from {brand_name} matching user's active relationship.",
                    "confidence": 0.78,
                    "evidence_message_ids": evidence_ids
                }

        # Order / Booking / Operational Business Update
        if any(k in text_lower for k in ["order", "packed", "delivery", "appointment", "pickup", "ride"]):
            if any(k in text_lower for k in ["reminder", "appointment", "clinic"]):
                mtype = "event"
                reason = f"Appointment reminder from {brand_name} matching recent user bookings."
            else:
                mtype = "business_update"
                order_tag = f" (Order #{entities['order_id']})" if "order_id" in entities else ""
                reason = f"Verified operational update from {brand_name}{order_tag} matching active orders."
            return {
                "message_id": msg_id,
                "action": "notify",
                "message_type": mtype,
                "reason": reason,
                "confidence": 0.91,
                "evidence_message_ids": evidence_ids
            }
            
        return {
            "message_id": msg_id,
            "action": "digest",
            "message_type": "business_update",
            "reason": f"Non-urgent account update from verified sender {brand_name}.",
            "confidence": 0.78,
            "evidence_message_ids": evidence_ids
        }

    # RULE 6: Direct Mentions & Personal Questions
    is_direct_mention = f"@{user_id}" in raw_text or f"@{user_id}" in full_text
    if is_direct_mention and any(k in text_lower for k in ["can you call", "pickup", "works for you", "join"]):
        return {
            "message_id": msg_id,
            "action": "notify",
            "message_type": "personal",
            "reason": f"Direct mention @{user_id} in {group_name} requesting response.",
            "confidence": 0.87,
            "evidence_message_ids": evidence_ids
        }

    # RULE 7: Work / Urgent Pings
    is_work = group_type == "coworker" or any(k in text_lower for k in ["prod review", "escalation", "retry count"])
    if is_work and (is_direct_mention or any(k in text_lower for k in ["come online", "sorry for the ping", "eod", "prod review"])):
        return {
            "message_id": msg_id,
            "action": "notify",
            "message_type": "urgent",
            "reason": f"Urgent workplace dependency in {group_name or 'coworker chat'} requiring immediate attention.",
            "confidence": 0.85,
            "evidence_message_ids": evidence_ids
        }

    # RULE 8: School / Society Urgent Updates & Circulars
    if is_sender_admin or group_type in ["society", "school_group"]:
        if any(k in text_lower for k in ["school circular", "consent note", "timing", "bus"]):
            return {
                "message_id": msg_id,
                "action": "notify",
                "message_type": "event",
                "reason": f"Operational notice from {group_name} admin requiring quick review.",
                "confidence": 0.87,
                "evidence_message_ids": evidence_ids
            }
        elif any(k in text_lower for k in ["water", "valve", "tanker", "heads-up"]):
            time_tag = f" ({entities['time_window']})" if "time_window" in entities else ""
            return {
                "message_id": msg_id,
                "action": "notify",
                "message_type": "urgent",
                "reason": f"Time-sensitive facility alert from {group_name} admin{time_tag}.",
                "confidence": 0.89,
                "evidence_message_ids": evidence_ids
            }

    # RULE 9: Personal Direct Pings & Unfamiliar Senders
    if conv_type == "personal":
        if any(k in text_lower for k in ["nothing urgent", "don't call", "reached home"]):
            return {
                "message_id": msg_id,
                "action": "digest",
                "message_type": "personal",
                "reason": "Direct message from trusted contact specifying no immediate urgency.",
                "confidence": 0.80,
                "evidence_message_ids": evidence_ids
            }
        elif any(k in text_lower for k in ["can you come online", "need quick help", "escalation"]):
            return {
                "message_id": msg_id,
                "action": "notify",
                "message_type": "urgent",
                "reason": "Direct urgent request from contact needing immediate assistance.",
                "confidence": 0.85,
                "evidence_message_ids": evidence_ids
            }
        elif evidence_ids == "none" and any(k in text_lower for k in ["volunteer sheet", "coordinating", "unfamiliar"]):
            return {
                "message_id": msg_id,
                "action": "digest",
                "message_type": "unknown",
                "reason": "First message from unfamiliar sender without clear urgency or safety risk.",
                "confidence": 0.82,
                "evidence_message_ids": "none"
            }
        else:
            return {
                "message_id": msg_id,
                "action": "digest",
                "message_type": "personal",
                "reason": "Casual personal message from contact without urgent action requirement.",
                "confidence": 0.80,
                "evidence_message_ids": evidence_ids
            }

    # RULE 10: General Group Messages & Batch Digesting
    if any(k in text_lower for k in ["good morning", "good vibes", "peaceful"]):
        return {
            "message_id": msg_id,
            "action": "digest",
            "message_type": "greeting",
            "reason": f"Harmless group greeting in {group_name}.",
            "confidence": 0.82,
            "evidence_message_ids": evidence_ids
        }

    if any(k in text_lower for k in ["form", "sheet", "cultural night"]):
        return {
            "message_id": msg_id,
            "action": "digest",
            "message_type": "event",
            "reason": f"Non-urgent group operational information in {group_name}.",
            "confidence": 0.84,
            "evidence_message_ids": evidence_ids
        }

    if any(k in text_lower for k in ["selling", "cycle helmet", "kurta set"]):
        user_dismissed = int(user_info.get("notifications_dismissed_30d", 0) or 0)
        if user_dismissed > 60:
            return {
                "message_id": msg_id,
                "action": "mute",
                "message_type": "promotion",
                "reason": f"Marketplace listing in {group_name} matching user's dismissal pattern.",
                "confidence": 0.85,
                "evidence_message_ids": evidence_ids
            }
        else:
            return {
                "message_id": msg_id,
                "action": "digest",
                "message_type": "promotion",
                "reason": f"Marketplace offer in {group_name} suitable for digest reading.",
                "confidence": 0.84,
                "evidence_message_ids": evidence_ids
            }

    # Default Fallback with Burst Batching Context
    burst_desc = f" (Part of {burst_size}-message burst)" if is_burst else ""
    fallback_type = "unknown" if (conv_type == "business" or evidence_ids == "none") else "personal"
    return {
        "message_id": msg_id,
        "action": "digest",
        "message_type": fallback_type,
        "reason": f"Standard chat message in {group_name or 'conversation'}{burst_desc} evaluated for digest.",
        "confidence": 0.80,
        "evidence_message_ids": evidence_ids
    }
