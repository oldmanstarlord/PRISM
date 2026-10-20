"""Duplicate and near-duplicate detection using exact hashing and 64-bit SimHash."""

from __future__ import annotations

import hashlib
import re


def normalize_text(text: str) -> str:
    """Normalize text by lowercasing and stripping non-alphanumeric punctuation."""
    lowered = text.lower()
    cleaned = re.sub(r"[^\w\s]", " ", lowered)
    return " ".join(cleaned.split())


def compute_exact_hash(url: str, headline: str) -> str:
    """Compute deterministic SHA-256 hash of canonical URL or normalized headline."""
    key = url.strip() if url.strip() else normalize_text(headline)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def compute_simhash(text: str, hash_bits: int = 64) -> str:
    """Compute 64-bit SimHash for near-duplicate text detection (Charikar, 2002)."""
    norm = normalize_text(text)
    words = norm.split()
    if not words:
        return "0" * (hash_bits // 4)

    # Generate word-level shingles (unigrams + bigrams for semantic structure)
    shingles: list[str] = list(words)
    for i in range(len(words) - 1):
        shingles.append(f"{words[i]}_{words[i+1]}")

    v = [0] * hash_bits
    for shingle in shingles:
        h = int(hashlib.md5(shingle.encode("utf-8")).hexdigest()[:16], 16)
        for i in range(hash_bits):
            bit = (h >> i) & 1
            if bit == 1:
                v[i] += 1
            else:
                v[i] -= 1

    fingerprint = 0
    for i in range(hash_bits):
        if v[i] > 0:
            fingerprint |= 1 << i

    # Return as 16-character hex string (64 bits)
    return f"{fingerprint:016x}"


def hamming_distance(hex1: str, hex2: str) -> int:
    """Calculate the Hamming distance (number of differing bits) between two hex SimHashes."""
    try:
        val1 = int(hex1, 16)
        val2 = int(hex2, 16)
        xor_val = val1 ^ val2
        return bin(xor_val).count("1")
    except ValueError:
        return 64


def is_near_duplicate(
    headline_a: str,
    headline_b: str,
    simhash_a: str | None = None,
    simhash_b: str | None = None,
    max_hamming_distance: int = 4,
    min_token_jaccard: float = 0.65,
) -> bool:
    """Check if two articles are near-duplicates using SimHash and token Jaccard overlap."""
    norm_a = normalize_text(headline_a)
    norm_b = normalize_text(headline_b)

    if norm_a == norm_b:
        return True

    # 1. SimHash check
    sh_a = simhash_a or compute_simhash(norm_a)
    sh_b = simhash_b or compute_simhash(norm_b)
    dist = hamming_distance(sh_a, sh_b)
    if dist <= max_hamming_distance:
        return True

    # 2. Token Jaccard check for shorter headlines
    set_a = set(norm_a.split())
    set_b = set(norm_b.split())
    if not set_a or not set_b:
        return False

    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    jaccard = intersection / union if union > 0 else 0.0

    return jaccard >= min_token_jaccard
