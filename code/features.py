import os
import re
import csv
from datetime import datetime

class ContextData:
    def __init__(self, dataset_dir):
        self.dataset_dir = dataset_dir
        self.users = {}
        self.groups = {}
        self.group_members = {}
        self.business_accounts = {}
        self.user_business_history = {}
        self.message_history = {}
        self.message_events = {}
        self.daily_summary = {}
        self._load_all()

    def _read_csv(self, filename):
        path = os.path.join(self.dataset_dir, filename)
        if not os.path.exists(path):
            return []
        with open(path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)

    def _load_all(self):
        # Users
        for row in self._read_csv('users.csv'):
            self.users[row['user_id']] = row

        # Groups
        for row in self._read_csv('groups.csv'):
            self.groups[row['group_id']] = row

        # Group Members
        for row in self._read_csv('group_members.csv'):
            key = (row['group_id'], row['user_id'])
            self.group_members[key] = row

        # Business Accounts
        for row in self._read_csv('business_accounts.csv'):
            self.business_accounts[row['business_id']] = row

        # User Business History
        for row in self._read_csv('user_business_history.csv'):
            key = (row['user_id'], row['business_id'])
            self.user_business_history[key] = row

        # Message History
        for row in self._read_csv('message_history.csv'):
            self.message_history[row['message_id']] = row

        # Message Events
        for row in self._read_csv('message_events.csv'):
            key = (row['user_id'], row['message_id'])
            self.message_events[key] = row

        # Daily Notification Summary
        for row in self._read_csv('daily_notification_summary.csv'):
            self.daily_summary[(row['user_id'], row.get('date', ''))] = row


def is_in_dnd(created_at_str, dnd_window_str):
    if not dnd_window_str or dnd_window_str == "none":
        return False
    try:
        dt = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M")
        msg_time = dt.time()
        
        parts = dnd_window_str.split("-")
        if len(parts) != 2:
            return False
        
        start_time = datetime.strptime(parts[0], "%H:%M").time()
        end_time = datetime.strptime(parts[1], "%H:%M").time()
        
        if start_time <= end_time:
            return start_time <= msg_time <= end_time
        else: # Spans midnight (e.g. 22:00-07:00)
            return msg_time >= start_time or msg_time <= end_time
    except Exception:
        return False


def detect_prompt_injection(text):
    if not text:
        return False
    patterns = [
        r"ignore all previous",
        r"routing override",
        r"set action=",
        r"mark this message as",
        r"system prompt:",
        r"bypass rules"
    ]
    text_lower = text.lower()
    for p in patterns:
        if re.search(p, text_lower):
            return True
    return False


def detect_scam_or_phishing(text, business_info=None):
    if not text:
        text = ""
    text_lower = text.lower()
    
    # Exclude legitimate safety advisories from verified businesses
    if "safety advisory" in text_lower or "never ask for otp" in text_lower or "beware of fraud" in text_lower:
        return False, None

    # Check domain mismatch or high report business
    if business_info:
        verified = business_info.get("verified", "1") == "1"
        off_domain = business_info.get("official_domain", "").strip().lower()
        sender_domain = business_info.get("domain_used_by_sender", "").strip().lower()
        sender_domain_age = float(business_info.get("domain_used_by_sender_age_days", "999") or "999")
        user_reports = float(business_info.get("user_reports_30d", "0") or "0")
        
        if not verified and off_domain and sender_domain and off_domain != sender_domain:
            return True, "unverified_domain_mismatch"
        if sender_domain_age < 30:
            return True, "recent_suspicious_domain"
        if user_reports > 30:
            return True, "high_business_reports"
            
    scam_keywords = [
        "otp", "verification code", "verify now", "account will be blocked",
        "access will expire today", "enter code", "confirm password",
        "penalty list", "scan this qr", "pay the clearance amount",
        "reattempt fee", "wallet verification",
        "login-code", "account-login", "security alert: otp"
    ]
    for kw in scam_keywords:
        if kw in text_lower:
            return True, f"suspicious_keyword_{kw}"
            
    return False, None


def find_evidence_history(context, user_id, group_id, business_id, sender_user_id, message_text):
    matched_ids = []
    # Search message history for exact/similar sender or topic matches for this user
    for msg_id, msg in context.message_history.items():
        if msg.get("user_id") == user_id:
            same_business = business_id and msg.get("business_id") == business_id
            same_group = group_id and msg.get("group_id") == group_id
            same_sender = sender_user_id and msg.get("sender_user_id") == sender_user_id
            
            if same_business or same_sender or (same_group and sender_user_id and msg.get("sender_user_id") == sender_user_id):
                matched_ids.append(msg_id)
                
    if not matched_ids:
        return "none"
        
    # Sort matched IDs to get most relevant historical evidence
    matched_ids.sort(key=lambda x: context.message_history[x].get("created_at", ""), reverse=True)
    return ";".join(matched_ids[:2])

