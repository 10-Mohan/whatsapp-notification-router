import os
import csv
import logging
import sys

# Ensure code/ is on path
code_dir = os.path.dirname(os.path.abspath(__file__))
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

from features import ContextData
from multimodal import get_audio_transcripts, get_image_ocr
from router import route_message
from hybrid_router import hybrid_route_message
from batching import compute_message_batches

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dataset_dir = os.path.join(root_dir, "dataset")
    
    logger.info("Initializing context data and multimodal extractors...")
    context = ContextData(dataset_dir)
    audio_transcripts = get_audio_transcripts(dataset_dir)
    image_ocr = get_image_ocr(dataset_dir)

    messages_path = os.path.join(dataset_dir, "messages.csv")
    if not os.path.exists(messages_path):
        logger.error(f"Input file missing: {messages_path}")
        return

    with open(messages_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        messages = list(reader)

    # Claim temporal batching differentiator
    batch_info = compute_message_batches(messages, time_window_minutes=30)

    logger.info(f"Processing {len(messages)} incoming messages with hybrid router engine...")
    results = []
    
    for msg in messages:
        res = hybrid_route_message(msg, context, audio_transcripts, image_ocr, batch_info)
        results.append(res)

    output_path = os.path.join(dataset_dir, "output.csv")
    fieldnames = ["message_id", "action", "message_type", "reason", "confidence", "evidence_message_ids"]

    with open(output_path, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    logger.info(f"Successfully generated predictions in {output_path}")
    
    actions = [r['action'] for r in results]
    types = [r['message_type'] for r in results]
    logger.info(f"Action Distribution: {{'notify': {actions.count('notify')}, 'digest': {actions.count('digest')}, 'mute': {actions.count('mute')}}}")
    logger.info(f"Message Type Breakdown: {dict((t, types.count(t)) for t in set(types))}")

if __name__ == "__main__":
    main()
