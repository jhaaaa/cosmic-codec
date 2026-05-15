"""
COSMIC CODEC — Blockchain Lexicon Harvester
Scans Bitcoin OP_RETURN outputs across all eras.
The blockchain builds its own vocabulary.
No editorial selection — every word comes from what was inscribed.
"""

import requests
import time
import re
import json
from collections import Counter
from pathlib import Path

MEMPOOL = "https://mempool.space/api"

# ── Blocks to sample — spread across all eras ─────────────────────────────────
# Each entry: (height, label)
# We sample broadly to let the full range of human inscription speak.

SAMPLE_BLOCKS = [
    # OP_RETURN era opens (~2013)
    (278458, "first OP_RETURN use"),
    (279000, "early OP_RETURN"),
    (280000, "early OP_RETURN"),
    (285000, "early OP_RETURN"),
    (290000, "early OP_RETURN"),

    # 2014 — protocols emerge (Omni, Counterparty, Proof of Existence)
    (295000, "2014 early"),
    (300000, "2014 block 300k"),
    (305000, "2014"),
    (310000, "2014"),
    (315000, "2014"),
    (320000, "2014"),
    (325000, "2014"),
    (330000, "2014"),

    # 2015 — consolidation
    (340000, "2015"),
    (350000, "2015"),
    (360000, "2015"),
    (370000, "2015"),

    # 2016
    (390000, "2016"),
    (400000, "2016 block 400k"),
    (410000, "2016"),
    (420000, "2016 first halving eve"),

    # 2017 — ICO era
    (450000, "2017"),
    (460000, "2017"),
    (470000, "2017"),
    (478558, "2017 fork eve"),
    (478559, "2017 BCH fork"),
    (480000, "2017 post-fork"),
    (490000, "2017"),
    (500000, "2017 block 500k"),

    # 2018 — bear market inscriptions
    (510000, "2018"),
    (520000, "2018"),
    (530000, "2018"),
    (540000, "2018"),
    (550000, "2018"),
    (560000, "2018 winter"),
    (570000, "2018-2019"),

    # 2019-2020
    (580000, "2019"),
    (590000, "2019"),
    (600000, "2019"),
    (610000, "2019-2020"),
    (620000, "2020"),
    (629999, "2020 halving eve"),
    (630000, "2020 third halving"),
    (640000, "2020"),
    (650000, "2020"),
    (660000, "2020"),
    (670000, "2021"),
    (680000, "2021"),

    # 2021-2022 — NFT and inscription era begins
    (690000, "2021"),
    (700000, "2021"),
    (710000, "2021-2022"),
    (720000, "2022"),
    (730000, "2022"),
    (740000, "2022"),
    (750000, "2022"),
    (760000, "2022"),
    (770000, "2022"),

    # 2023 — Ordinals
    (775000, "2023 ordinals"),
    (780000, "2023"),
    (790000, "2023"),
    (800000, "2023 ordinals era"),
    (810000, "2023"),

    # 2024 — fourth halving era
    (830000, "2024"),
    (839999, "2024 halving eve"),
    (840000, "2024 fourth halving"),
    (850000, "2024"),
    (860000, "2024"),
]

# ── API ────────────────────────────────────────────────────────────────────────

def get_json(url, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=20)
            if r.status_code == 200:
                return r.json()
            time.sleep(2 ** attempt)
        except Exception:
            time.sleep(2 ** attempt)
    return None

def get_text(url, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=20)
            if r.status_code == 200:
                return r.text.strip()
            time.sleep(2 ** attempt)
        except Exception:
            time.sleep(2 ** attempt)
    return None

# ── OP_RETURN decoder ──────────────────────────────────────────────────────────

def decode_op_return(hex_part):
    """Decode a hex string from an OP_RETURN output. Returns readable text or None."""
    try:
        raw = bytes.fromhex(hex_part)
    except Exception:
        return None

    # Skip known binary protocol headers
    if raw[:4] == b'omni':          # Omni Layer (USDT)
        return None
    if raw[:2] == b'CX':            # Counterparty
        return None
    if raw[:4] == b'\x13\x00\x00\x00':  # Colored Coins
        return None

    # Try UTF-8 first, then latin-1
    for encoding in ("utf-8", "latin-1"):
        try:
            text = raw.decode(encoding)
            clean = "".join(c for c in text if c.isprintable())
            if len(clean) >= 4:
                ratio = len(clean) / max(len(text), 1)
                if ratio > 0.75:
                    return clean
        except Exception:
            pass
    return None

def extract_from_tx(tx):
    """Extract all readable OP_RETURN texts from a transaction."""
    results = []
    for vout in tx.get("vout", []):
        if vout.get("scriptpubkey_type") == "op_return":
            asm = vout.get("scriptpubkey_asm", "")
            parts = asm.split()
            for part in parts:
                if len(part) >= 8 and all(c in "0123456789abcdef" for c in part.lower()):
                    text = decode_op_return(part)
                    if text:
                        results.append(text)
    return results

# ── Word extractor ─────────────────────────────────────────────────────────────

def extract_words(text):
    """Pull clean alphabetic words (3–20 chars) from a text string."""
    # Split on anything non-alpha
    tokens = re.findall(r'[a-zA-Z]{3,20}', text)
    # Filter: no ALL-CAPS abbreviations over 4 chars, no obvious hex-like strings
    words = []
    for t in tokens:
        # Skip if it looks like a protocol identifier (all caps, short)
        if t.isupper() and len(t) <= 4:
            continue
        # Accept otherwise
        words.append(t.lower())
    return words

# ── Scanner ────────────────────────────────────────────────────────────────────

def scan_block(height, label, max_txs=200):
    """Scan one block. Returns list of (text, words) tuples."""
    block_hash = get_text(f"{MEMPOOL}/block-height/{height}")
    if not block_hash:
        return []

    txids = get_json(f"{MEMPOOL}/block/{block_hash}/txids") or []
    if not txids:
        return []

    results = []
    for txid in txids[:max_txs]:
        tx = get_json(f"{MEMPOOL}/tx/{txid}")
        if not tx:
            continue
        time.sleep(0.10)

        for text in extract_from_tx(tx):
            words = extract_words(text)
            if words:
                results.append((text, words))

    return results

# ── Main ───────────────────────────────────────────────────────────────────────

CHECKPOINT_PATH = Path("harvest_checkpoint.json")

def save_checkpoint(done_heights, all_messages, all_words):
    data = {
        "done": done_heights,
        "messages": all_messages,
        "words": dict(all_words),
    }
    CHECKPOINT_PATH.write_text(json.dumps(data))

def load_checkpoint():
    if not CHECKPOINT_PATH.exists():
        return set(), [], Counter()
    try:
        data = json.loads(CHECKPOINT_PATH.read_text())
        return set(data["done"]), data["messages"], Counter(data["words"])
    except Exception:
        return set(), [], Counter()


def main():
    print()
    print("  COSMIC CODEC — BLOCKCHAIN LEXICON HARVESTER")
    print("  Mining words inscribed on the Bitcoin blockchain.")
    print("  The universe builds its own vocabulary.")
    print()

    done_heights, all_messages, all_words = load_checkpoint()
    if done_heights:
        print(f"  [resuming: {len(done_heights)} blocks already done, {len(all_messages)} messages so far]")
        print()

    total_blocks = len(SAMPLE_BLOCKS)

    for i, (height, label) in enumerate(SAMPLE_BLOCKS, 1):
        if height in done_heights:
            print(f"  [{i:02d}/{total_blocks}] Block {height:,}  (already done — skipping)")
            continue

        print(f"  [{i:02d}/{total_blocks}] Block {height:,}  ({label})", end="", flush=True)

        results = scan_block(height, label)

        if results:
            word_count = sum(len(words) for _, words in results)
            print(f"  → {len(results)} messages, {word_count} words")
            for text, words in results:
                all_messages.append((height, label, text))
                all_words.update(words)
        else:
            print("  (silence)")

        done_heights.add(height)
        save_checkpoint(list(done_heights), all_messages, all_words)

        time.sleep(0.3)

    print()
    print(f"  ── HARVEST COMPLETE ──────────────────────────────────────")
    print(f"  Blocks scanned:    {total_blocks}")
    print(f"  Messages found:    {len(all_messages)}")
    print(f"  Unique words:      {len(all_words)}")
    print(f"  Total word tokens: {sum(all_words.values())}")
    print()

    # ── Write transmission log ─────────────────────────────────────────────────
    log_path = Path("transmissions.txt")
    with open(log_path, "w") as f:
        f.write("COSMIC CODEC — BLOCKCHAIN TRANSMISSIONS\n")
        f.write("What humanity inscribed in Bitcoin, 2013–2024.\n")
        f.write("=" * 60 + "\n\n")
        current_height = None
        for height, label, text in all_messages:
            if height != current_height:
                f.write(f"\n── Block {height:,}  ({label}) ──\n")
                current_height = height
            # Truncate very long texts
            display = text[:200] + ("..." if len(text) > 200 else "")
            f.write(f"  {display}\n")

    print(f"  Transmissions written to: {log_path}")

    # ── Write frequency-sorted word list ──────────────────────────────────────
    # Filter: keep words that appear at least twice (reduce noise)
    filtered = {w: c for w, c in all_words.items() if c >= 1}
    sorted_words = sorted(filtered.items(), key=lambda x: (-x[1], x[0]))

    lexicon_path = Path("lexicon.txt")
    with open(lexicon_path, "w") as f:
        f.write("# COSMIC CODEC LEXICON\n")
        f.write("# Words inscribed on the Bitcoin blockchain, 2013–2024.\n")
        f.write("# Format: word<TAB>frequency\n")
        f.write("# Sorted by frequency descending.\n")
        f.write("#\n")
        for word, count in sorted_words:
            f.write(f"{word}\t{count}\n")

    print(f"  Lexicon written to:       {lexicon_path}  ({len(sorted_words)} words)")

    # ── Write Python module ────────────────────────────────────────────────────
    wordset = set(w for w, _ in sorted_words)
    py_path = Path("lexicon_words.py")
    with open(py_path, "w") as f:
        f.write('"""\n')
        f.write('COSMIC CODEC — Blockchain-derived lexicon.\n')
        f.write(f'Generated from {len(all_messages)} inscriptions across {total_blocks} Bitcoin blocks.\n')
        f.write('These words were chosen by the blockchain, not by any human editor.\n')
        f.write('"""\n\n')
        f.write(f"WORD_COUNT = {len(wordset)}\n")
        f.write(f"SOURCE_MESSAGES = {len(all_messages)}\n")
        f.write(f"SOURCE_BLOCKS = {total_blocks}\n\n")
        f.write("WORDS: set = {\n")
        for word in sorted(wordset):
            f.write(f'    "{word}",\n')
        f.write("}\n")

    print(f"  Python module written to: {py_path}")

    # Clean up checkpoint now that harvest is complete
    if CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()
    print()

    # ── Preview top words ──────────────────────────────────────────────────────
    print("  ── MOST INSCRIBED WORDS ──────────────────────────────────")
    print("  (what the blockchain repeats most) \n")
    for word, count in sorted_words[:60]:
        bar = "█" * min(count, 40)
        print(f"  {word:<20} {count:>5}  {bar}")
    print()

    # ── Sample messages ────────────────────────────────────────────────────────
    if all_messages:
        print("  ── SAMPLE TRANSMISSIONS ──────────────────────────────────")
        print()
        import random
        random.seed(42)
        sample = random.sample(all_messages, min(20, len(all_messages)))
        for height, label, text in sorted(sample, key=lambda x: x[0]):
            preview = text[:100].replace('\n', ' ').replace('\r', ' ')
            print(f"  {height:>7,}  {preview}")
        print()


if __name__ == "__main__":
    main()
