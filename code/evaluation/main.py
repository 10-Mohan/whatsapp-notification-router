import os
import csv
import logging
import sys

# Ensure code/ is on path
code_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

from features import ContextData
from multimodal import get_audio_transcripts, get_image_ocr
from router import route_message
from batching import compute_message_batches
from hybrid_router import hybrid_route_message

ALLOWED_ACTIONS = ("notify", "digest", "mute")
ALLOWED_TYPES = (
    "personal", "urgent", "event", "payment", "business_update",
    "promotion", "greeting", "forward", "spam", "scam", "unknown",
)


def macro_f1(labels, expected, predicted):
    scores = []
    for label in labels:
        tp = sum(1 for e, p in zip(expected, predicted) if e == label and p == label)
        fp = sum(1 for e, p in zip(expected, predicted) if e != label and p == label)
        fn = sum(1 for e, p in zip(expected, predicted) if e == label and p != label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision and recall) else 0.0
        scores.append(f1)
    return sum(scores) / len(scores)


def evidence_jaccard(expected_str, predicted_str):
    def parse(s):
        s = (s or "none").strip()
        return set() if s.lower() == "none" else set(x.strip() for x in s.split(";") if x.strip())
    e, p = parse(expected_str), parse(predicted_str)
    if not e and not p:
        return 1.0
    union = e | p
    return len(e & p) / len(union) if union else 1.0

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("evaluator")

def evaluate():
    root_dir = os.path.dirname(code_dir)
    dataset_dir = os.path.join(root_dir, "dataset")
    sample_path = os.path.join(dataset_dir, "sample_messages.csv")
    
    if not os.path.exists(sample_path):
        logger.error(f"Sample messages benchmark file not found: {sample_path}")
        return

    logger.info("Loading context and multimodal data...")
    context = ContextData(dataset_dir)
    audio_transcripts = get_audio_transcripts(dataset_dir)
    image_ocr = get_image_ocr(dataset_dir)

    with open(sample_path, mode='r', encoding='utf-8') as f:
        samples = list(csv.DictReader(f))

    batch_info = compute_message_batches(samples, time_window_minutes=30)

    logger.info(f"Evaluating {len(samples)} sample messages...")
    
    correct_action = 0
    correct_type = 0
    exact_joint_match = 0
    total = len(samples)
    gt_actions, pred_actions, gt_types, pred_types, evidence_scores = [], [], [], [], []

    for s in samples:
        msg_id = s['message_id']
        pred = hybrid_route_message(s, context, audio_transcripts, image_ocr, batch_info)

        gt_action = s['action']
        gt_type = s['message_type']
        gt_evidence = s.get('evidence_message_ids', 'none')

        action_ok = (pred['action'] == gt_action)
        type_ok = (pred['message_type'] == gt_type)
        gt_actions.append(gt_action); pred_actions.append(pred['action'])
        gt_types.append(gt_type); pred_types.append(pred['message_type'])
        evidence_scores.append(evidence_jaccard(gt_evidence, pred['evidence_message_ids']))

        if action_ok:
            correct_action += 1
        if type_ok:
            correct_type += 1
        if action_ok and type_ok:
            exact_joint_match += 1
        else:
            logger.info(f"[{msg_id}] MISMATCH:")
            logger.info(f"  GT:   action={gt_action:<8} | type={gt_type:<15} | evidence={gt_evidence}")
            logger.info(f"  PRED: action={pred['action']:<8} | type={pred['message_type']:<15} | evidence={pred['evidence_message_ids']}")
            logger.info(f"  Reason: {pred['reason']}\n")

    action_f1 = macro_f1(ALLOWED_ACTIONS, gt_actions, pred_actions)
    type_f1 = macro_f1(ALLOWED_TYPES, gt_types, pred_types)
    avg_evidence_overlap = sum(evidence_scores) / len(evidence_scores)

    logger.info("=" * 60)
    logger.info(f"EVALUATION SUMMARY ({total} rows):")
    logger.info(f"  Action Accuracy:     {correct_action}/{total} ({correct_action/total*100:.2f}%)")
    logger.info(f"  Message Type Acc:    {correct_type}/{total} ({correct_type/total*100:.2f}%)")
    logger.info(f"  Exact Joint Match:   {exact_joint_match}/{total} ({exact_joint_match/total*100:.2f}%)")
    logger.info(f"  Action Macro-F1:     {action_f1:.4f}")
    logger.info(f"  Type Macro-F1:       {type_f1:.4f}")
    logger.info(f"  Avg Evidence Overlap (Jaccard): {avg_evidence_overlap:.4f}")
    logger.info("=" * 60)

if __name__ == "__main__":
    evaluate()
