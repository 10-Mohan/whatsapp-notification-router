from datetime import datetime

def compute_message_batches(messages, time_window_minutes=30):
    """
    Groups messages by user and thread (group/business/sender) within a short time window.
    Annotates messages with batch context (e.g. burst_size, is_burst).
    """
    # Sort messages chronologically
    sorted_msgs = sorted(messages, key=lambda x: x.get('created_at', ''))
    
    user_threads = {}
    
    for msg in sorted_msgs:
        user_id = msg.get('user_id', '')
        thread_id = msg.get('group_id') or msg.get('business_id') or msg.get('sender_user_id') or 'direct'
        key = (user_id, thread_id)
        
        if key not in user_threads:
            user_threads[key] = []
            
        user_threads[key].append(msg)

    batch_meta = {}

    for (user_id, thread_id), msg_list in user_threads.items():
        if len(msg_list) <= 1:
            for m in msg_list:
                batch_meta[m['message_id']] = {
                    'burst_size': 1,
                    'is_burst': False,
                    'batch_position': 1
                }
            continue

        # Process burst windows
        current_burst = []
        burst_id = 0

        for i, m in enumerate(msg_list):
            m_time_str = m.get('created_at', '')
            try:
                m_time = datetime.strptime(m_time_str, "%Y-%m-%d %H:%M")
            except Exception:
                m_time = None

            if not current_burst:
                current_burst.append((m, m_time))
            else:
                prev_m, prev_time = current_burst[-1]
                if m_time and prev_time and (m_time - prev_time).total_seconds() / 60.0 <= time_window_minutes:
                    current_burst.append((m, m_time))
                else:
                    # Finalize previous burst
                    b_size = len(current_burst)
                    for pos, (bm, _) in enumerate(current_burst, 1):
                        batch_meta[bm['message_id']] = {
                            'burst_size': b_size,
                            'is_burst': b_size > 1,
                            'batch_position': pos
                        }
                    current_burst = [(m, m_time)]

        if current_burst:
            b_size = len(current_burst)
            for pos, (bm, _) in enumerate(current_burst, 1):
                batch_meta[bm['message_id']] = {
                    'burst_size': b_size,
                    'is_burst': b_size > 1,
                    'batch_position': pos
                }

    return batch_meta
