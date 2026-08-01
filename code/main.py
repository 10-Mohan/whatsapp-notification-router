import os
import sys
import csv
import logging

from features import ContextData
from router import route_message
from multimodal import get_audio_transcripts, get_image_ocr

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("main")

def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    dataset_dir = os.path.join(base_dir, "dataset")
    messages_csv = os.path.join(dataset_dir, "messages.csv")
    output_csv = os.path.join(dataset_dir, "output.csv")

    if not os.path.exists(messages_csv):
        logger.error(f"Input messages file not found: {messages_csv}")
        sys.exit(1)

    logger.info("Initializing context data and multimodal extractors...")
    context = ContextData(dataset_dir)
    audio_transcripts = get_audio_transcripts(dataset_dir)
    image_ocr = get_image_ocr(dataset_dir)

    messages = []
    with open(messages_csv, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        messages = list(reader)

    logger.info(f"Processing {len(messages)} incoming messages...")

    output_rows = []
    action_counts = {"notify": 0, "digest": 0, "mute": 0}
    type_counts = {}

    for msg in messages:
        pred = route_message(msg, context, audio_transcripts, image_ocr)
        
        action = pred.get("action", "digest")
        mtype = pred.get("message_type", "unknown")
        
        action_counts[action] = action_counts.get(action, 0) + 1
        type_counts[mtype] = type_counts.get(mtype, 0) + 1

        output_rows.append({
            "message_id": pred["message_id"],
            "action": action,
            "message_type": mtype,
            "reason": pred.get("reason", "Standard routing decision based on message content and context."),
            "confidence": f"{pred.get('confidence', 0.80):.2f}",
            "evidence_message_ids": pred.get("evidence_message_ids", "none")
        })

    fieldnames = ["message_id", "action", "message_type", "reason", "confidence", "evidence_message_ids"]
    with open(output_csv, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    logger.info(f"Successfully generated predictions in {output_csv}")
    logger.info(f"Action Distribution: {action_counts}")
    logger.info(f"Message Type Breakdown: {type_counts}")

if __name__ == "__main__":
    main()
