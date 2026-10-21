"""Offline FinBERT inference. Download explicitly with jobs.setup_news_model."""

import threading
from typing import Any

MODEL_ID = "ProsusAI/finbert"
MODEL_REVISION = "0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031"
MODEL_VERSION = f"{MODEL_ID}@{MODEL_REVISION}:passages-v1"


class ModelUnavailable(RuntimeError):
    pass


class SentimentAnalyzer:
    def __init__(self) -> None:
        self._tokenizer: Any = None
        self._model: Any = None
        self._lock = threading.Lock()

    @staticmethod
    def downloaded() -> bool:
        from huggingface_hub import try_to_load_from_cache

        return all(
            isinstance(try_to_load_from_cache(MODEL_ID, name, revision=MODEL_REVISION), str)
            for name in ("config.json", "vocab.txt", "model.safetensors")
        )

    def load(self) -> None:
        with self._lock:
            if self._model is not None:
                return
            try:
                import torch
                from transformers import AutoModelForSequenceClassification, AutoTokenizer

                torch.set_num_threads(min(4, torch.get_num_threads()))
                self._tokenizer = AutoTokenizer.from_pretrained(
                    MODEL_ID,
                    revision=MODEL_REVISION,
                    local_files_only=True,
                )
                self._model = AutoModelForSequenceClassification.from_pretrained(
                    MODEL_ID,
                    revision=MODEL_REVISION,
                    local_files_only=True,
                    use_safetensors=True,
                ).eval()
            except Exception as exc:
                raise ModelUnavailable(
                    "Local FinBERT is unavailable. Run uv run python -m jobs.setup_news_model."
                ) from exc

    def analyze(self, text: str) -> dict[str, Any]:
        self.load()
        import torch

        if not text.strip():
            raise ValueError("No article text to analyze")
        with self._lock, torch.inference_mode():
            tokens = self._tokenizer(
                text,
                truncation=True,
                max_length=512,
                stride=0,
                return_overflowing_tokens=True,
                padding=True,
                return_tensors="pt",
            )
            tokens.pop("overflow_to_sample_mapping", None)
            total_chunks = tokens["input_ids"].shape[0]
            # Bound inference cost; disclose incomplete coverage in the result.
            count = min(total_chunks, 16)
            values, weights = [], []
            for start in range(0, count, 4):
                batch = {key: val[start : min(start + 4, count)] for key, val in tokens.items()}
                values.append(self._model(**batch).logits.softmax(dim=-1))
                weights.append(batch["attention_mask"].sum(dim=1).float())
            probs = torch.cat(values)
            weight = torch.cat(weights)
            average = (probs * weight[:, None]).sum(dim=0) / weight.sum()
            scores = {
                str(self._model.config.id2label[i]).lower(): round(float(p), 6)
                for i, p in enumerate(average)
            }
            if set(scores) != {"positive", "negative", "neutral"}:
                raise ModelUnavailable("FinBERT returned unexpected sentiment labels")
            label = max(scores, key=lambda key: scores[key])
            return {
                "label": label if scores[label] >= 0.55 else "uncertain",
                "score": round(scores["positive"] - scores["negative"], 6),
                "confidence": scores[label],
                "probabilities": scores,
                "model": MODEL_VERSION,
                "chunks_analyzed": count,
                "truncated": total_chunks > count,
            }
