import sys
import os
import csv
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from features import ContextData
from router import route_message
from multimodal import get_audio_transcripts, get_image_ocr

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("evaluator")

def evaluate():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    dataset_dir = os.path.join(base_dir, "dataset")
    sample_csv = os.path.join(dataset_dir, "sample_messages.csv")

    if not os.path.exists(sample_csv):
        logger.error(f"Sample messages file not found: {sample_csv}")
        return

    logger.info("Loading context and multimodal data...")
    context = ContextData(dataset_dir)
    audio_transcripts = get_audio_transcripts(dataset_dir)
    image_ocr = get_image_ocr(dataset_dir)

    sample_rows = []
    with open(sample_csv, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        sample_rows = list(reader)

    total = len(sample_rows)
    action_correct = 0
    type_correct = 0
    exact_correct = 0

    logger.info(f"Evaluating {total} sample messages...\n")

    for row in sample_rows:
        pred = route_message(row, context, audio_transcripts, image_ocr)
        
        gt_action = row.get("action", "").strip()
        gt_type = row.get("message_type", "").strip()
        gt_evidence = row.get("evidence_message_ids", "").strip()

        pred_action = pred.get("action", "").strip()
        pred_type = pred.get("message_type", "").strip()
        pred_evidence = pred.get("evidence_message_ids", "").strip()

        a_match = (gt_action == pred_action)
        t_match = (gt_type == pred_type)

        if a_match:
            action_correct += 1
        if t_match:
            type_correct += 1
        if a_match and t_match:
            exact_correct += 1
        else:
            msg_id = row['message_id']
            logger.info(f"[{msg_id}] MISMATCH:")
            logger.info(f"  GT:   action={gt_action:7s} | type={gt_type:15s} | evidence={gt_evidence}")
            logger.info(f"  PRED: action={pred_action:7s} | type={pred_type:15s} | evidence={pred_evidence}")
            logger.info(f"  Reason: {pred.get('reason')}\n")

    print("=" * 60)
    print(f"EVALUATION SUMMARY ({total} rows):")
    print(f"  Action Accuracy:     {action_correct}/{total} ({action_correct/total*100:.2f}%)")
    print(f"  Message Type Acc:    {type_correct}/{total} ({type_correct/total*100:.2f}%)")
    print(f"  Exact Joint Match:   {exact_correct}/{total} ({exact_correct/total*100:.2f}%)")
    print("=" * 60)

if __name__ == "__main__":
    evaluate()
