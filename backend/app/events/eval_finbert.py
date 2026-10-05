"""Evaluation script for announcement sentiment models against labelled data (SRS Step 10)."""

from __future__ import annotations

import argparse
import csv
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from backend.app.events.finbert import score_announcement_text

logger = logging.getLogger(__name__)


def evaluate_sentiment_model(
    csv_path: Path | str,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate sentiment classification on a labelled CSV dataset.

    Returns:
        dict with overall accuracy, total count, and per-class precision/recall/F1 metrics.
    """
    csv_file = Path(csv_path)

    if not csv_file.exists():
        raise FileNotFoundError(f"Labelled evaluation dataset not found at {csv_file}")

    rows: list[dict[str, str]] = []
    with open(csv_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    if not rows:
        return {"total": 0, "accuracy": 0.0, "classes": {}}

    classes = ["positive", "negative", "neutral"]
    tp: dict[str, int] = defaultdict(int)
    fp: dict[str, int] = defaultdict(int)
    fn: dict[str, int] = defaultdict(int)
    correct = 0

    for r in rows:
        headline = r.get("headline", "")
        text = r.get("text", "")
        gold_sentiment = r.get("sentiment", "neutral").strip().lower()

        pred_result = score_announcement_text(headline=headline, body=text, config=config)
        pred_sentiment = pred_result.sentiment.lower()

        if pred_sentiment == gold_sentiment:
            correct += 1
            tp[gold_sentiment] += 1
        else:
            fp[pred_sentiment] += 1
            fn[gold_sentiment] += 1

    total = len(rows)
    accuracy = round(correct / total, 4)

    per_class: dict[str, dict[str, float]] = {}
    for c in classes:
        c_tp = tp[c]
        c_fp = fp[c]
        c_fn = fn[c]

        prec = c_tp / (c_tp + c_fp) if (c_tp + c_fp) > 0 else 0.0
        rec = c_tp / (c_tp + c_fn) if (c_tp + c_fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        per_class[c] = {
            "true_positives": c_tp,
            "false_positives": c_fp,
            "false_negatives": c_fn,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
        }

    return {
        "dataset_path": str(csv_file),
        "total_examples": total,
        "correct_predictions": correct,
        "accuracy": accuracy,
        "per_class_metrics": per_class,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate sentiment against an explicit dataset")
    parser.add_argument("csv_path", type=Path)
    args = parser.parse_args()
    report = evaluate_sentiment_model(args.csv_path)
    print("--- Sentiment Model Evaluation Report ---")
    print(f"Total Examples: {report['total_examples']}")
    print(f"Accuracy:       {report['accuracy'] * 100:.1f}%")
    print("Per-class Metrics:")
    for cls_name, m in report["per_class_metrics"].items():
        p, r, f1 = m["precision"], m["recall"], m["f1"]
        print(f"  [{cls_name}]: Precision={p:.2f}, Recall={r:.2f}, F1={f1:.2f}")
