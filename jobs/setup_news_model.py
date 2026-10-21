"""Download pinned FinBERT weights once, then verify actual local inference."""

from huggingface_hub import snapshot_download

from backend.app.news.sentiment import MODEL_ID, MODEL_REVISION, SentimentAnalyzer


def main() -> None:
    location = snapshot_download(
        MODEL_ID,
        revision=MODEL_REVISION,
        allow_patterns=[
            "config.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "vocab.txt",
            "tokenizer.json",
            "model.safetensors",
            "README.md",
        ],
    )
    print(f"FinBERT cached at {location}")
    analyzer = SentimentAnalyzer()
    for sentence in [
        "The company reported record profits and strong revenue growth.",
        "The company reported a substantial loss and falling revenue.",
    ]:
        result = analyzer.analyze(sentence)
        print(f"{result['label']} ({result['confidence']:.3f}): {sentence}")


if __name__ == "__main__":
    main()
