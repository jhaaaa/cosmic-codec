"""
COSMIC CODEC — Signal Explorer
Point at any Bitcoin block and listen.
Uses the blockchain-derived lexicon if harvested; system dictionary otherwise.
"""

import requests
import time
import sys
import re
from pathlib import Path

MEMPOOL = "https://mempool.space/api"

# ── Lexicon ────────────────────────────────────────────────────────────────────

def load_words(min_len=3, max_len=12):
    try:
        from lexicon_words import WORDS, WORD_COUNT, SOURCE_MESSAGES, SOURCE_BLOCKS
        words = {w for w in WORDS if min_len <= len(w) <= max_len}
        print(f"  [lexicon: {WORD_COUNT:,} blockchain-derived words")
        print(f"   from {SOURCE_MESSAGES:,} inscriptions across {SOURCE_BLOCKS} blocks]")
        return words
    except ImportError:
        pass

    try:
        words = set()
        with open("/usr/share/dict/words") as f:
            for line in f:
                w = line.strip().lower()
                if min_len <= len(w) <= max_len and w.isalpha():
                    words.add(w)
        print(f"  [lexicon: system dictionary, {len(words):,} words]")
        return words
    except FileNotFoundError:
        pass

    # Minimal fallback
    words = {
        "the","and","for","are","but","not","you","all","can","had","her","was",
        "one","our","out","day","get","has","him","his","how","man","new","now",
        "old","see","two","way","who","did","its","let","put","say","she","use",
        "void","echo","wave","dark","time","life","star","fire","deep","hold",
        "code","null","zero","open","door","mind","soul","body","data","lost",
        "born","free","wall","fall","call","over","ever","even","only","also",
        "back","been","came","come","each","from","give","have","here","into",
        "just","keep","know","last","left","like","live","long","look","made",
        "make","many","more","most","move","much","must","name","near","need",
        "next","once","part","pass","past","play","real","rest","same","send",
        "side","some","take","tell","them","then","they","this","told","turn",
        "very","want","well","went","were","what","when","will","with","word",
        "work","year","your","able","area","base","both","case","city","does",
        "down","draw","drop","else","face","fact","feel","fill","find","form",
        "full","gone","good","grow","hand","hard","head","hear","help","high",
        "home","hope","idea","join","land","late","lead","less","line","list",
        "love","main","mark","mean","meet","note","page","plan","push","read",
        "ring","rise","road","rock","role","room","root","rule","safe","seem",
        "self","ship","show","sign","size","sort","spot","stay","step","stop",
        "sure","talk","task","test","tree","true","type","unit","upon","used",
        "user","vary","vast","view","vote","wait","walk","warm","wear","week",
        "west","wide","wind","wire","wise","wish","zone",
    }
    print(f"  [lexicon: built-in fallback, {len(words)} words]")
    return words

# ── Codec A: bytes → letters ───────────────────────────────────────────────────

def bytes_to_letters(raw: bytes) -> str:
    return "".join(chr(ord('A') + b % 26) for b in raw)

# ── Codec G: Word Miner ────────────────────────────────────────────────────────

def word_mine(letters: str, words: set, min_len=3) -> list:
    lower = letters.lower()
    found, seen = [], set()
    for start in range(len(lower)):
        for length in range(min_len, min(13, len(lower) - start + 1)):
            candidate = lower[start:start + length]
            if candidate in words and candidate not in seen:
                seen.add(candidate)
                found.append((start, candidate))
    found.sort(key=lambda x: (-len(x[1]), x[0]))
    return found

# ── Codec H: Word Lattice ──────────────────────────────────────────────────────

def word_lattice(letters: str, words: set) -> str:
    n = len(letters)
    lower = letters.lower()
    dp = [None] * (n + 1)
    dp[0] = []
    for i in range(n):
        if dp[i] is None:
            if i > 0 and dp[i-1] is not None:
                dp[i] = dp[i-1] + [f"[{letters[i-1]}]"]
            else:
                dp[i] = [f"[{letters[i]}]"] if i == 0 else None
                continue
        for length in range(3, min(13, n - i + 1)):
            candidate = lower[i:i + length]
            if candidate in words and dp[i + length] is None:
                dp[i + length] = dp[i] + [candidate]
    result = dp[n] or [letters[i:i+4] for i in range(0, n, 4)]
    return " ".join(result)

# ── Codec I: Vowel Injector ────────────────────────────────────────────────────

VOWELS = "AEIOU"
CONSONANTS = "BCDFGHJKLMNPQRSTVWXYZ"

def vowel_inject(letters: str) -> str:
    result, run = [], 0
    for i, c in enumerate(letters.upper()):
        result.append(c)
        if c in CONSONANTS:
            run += 1
            if run >= 2:
                result.append(VOWELS[i % 5])
                run = 0
        else:
            run = 0
    joined = "".join(result)
    chunks, i = [], 0
    while i < len(joined):
        size = 4 + (ord(joined[i]) % 3)
        chunks.append(joined[i:i+size])
        i += size
    return " ".join(chunks)

# ── Codec J: Bits → Morse ──────────────────────────────────────────────────────

MORSE = {
    ".-": "A", "-...": "B", "-.-.": "C", "-..": "D", ".": "E",
    "..-.": "F", "--.": "G", "....": "H", "..": "I", ".---": "J",
    "-.-": "K", ".-..": "L", "--": "M", "-.": "N", "---": "O",
    ".--.": "P", "--.-": "Q", ".-.": "R", "...": "S", "-": "T",
    "..-": "U", "...-": "V", ".--": "W", "-..-": "X", "-.--": "Y",
    "--..": "Z",
}

def morse_decode(raw: bytes) -> str:
    bits = "".join(format(b, "08b") for b in raw)
    result, i = [], 0
    while i < len(bits):
        for length in [4, 3, 2, 1]:
            chunk = bits[i:i+length]
            m = chunk.replace("0", ".").replace("1", "-")
            if m in MORSE:
                result.append(MORSE[m])
                i += length
                break
        else:
            i += 1
    return " ".join("".join(result[i:i+6]) for i in range(0, len(result), 6))

# ── Decode one payload ─────────────────────────────────────────────────────────

def decode_payload(txid, raw: bytes, words: set, source=""):
    letters = bytes_to_letters(raw)

    print(f"\n  {'═' * 64}")
    if source:
        print(f"  {source}")
    print(f"  TX    {txid[:48]}{'...' if len(txid) > 48 else ''}")
    print(f"  BYTES {len(raw)}  HEX {raw.hex()[:48]}{'...' if len(raw.hex()) > 48 else ''}")
    print()

    print("  CODEC A — byte mod 26 → letters:")
    print(f"  → {'  '.join(letters[i:i+8] for i in range(0, len(letters), 8))}")
    print()

    found = word_mine(letters, words)
    print("  CODEC G — word miner:")
    if found:
        for pos, word in found[:20]:
            print(f"     pos {pos:02d}  {word}")
    else:
        print("     (silence)")
    print()

    print("  CODEC H — word lattice:")
    print(f"  → {word_lattice(letters, words)}")
    print()

    print("  CODEC I — vowel injector (pronounceable):")
    print(f"  → {vowel_inject(letters)}")
    print()

    print("  CODEC J — bits → morse → letters:")
    print(f"  → {morse_decode(raw)}")
    print()

# ── Fetch helpers ──────────────────────────────────────────────────────────────

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

def fetch_op_returns(height, max_txs=300):
    block_hash = get_text(f"{MEMPOOL}/block-height/{height}")
    if not block_hash:
        print(f"  [could not fetch block {height}]")
        return []

    print(f"  Block hash: {block_hash}")
    txids = get_json(f"{MEMPOOL}/block/{block_hash}/txids") or []
    print(f"  {len(txids)} transactions — scanning first {min(max_txs, len(txids))}")

    payloads = []
    for txid in txids[:max_txs]:
        tx = get_json(f"{MEMPOOL}/tx/{txid}")
        if not tx:
            continue
        time.sleep(0.10)
        for vout in tx.get("vout", []):
            if vout.get("scriptpubkey_type") == "op_return":
                asm = vout.get("scriptpubkey_asm", "")
                for part in asm.split():
                    if len(part) >= 8 and all(c in "0123456789abcdef" for c in part.lower()):
                        try:
                            raw = bytes.fromhex(part)
                            payloads.append((txid, raw))
                        except Exception:
                            pass

    print(f"  Found {len(payloads)} OP_RETURN payloads\n")
    return payloads

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    heights = []
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            try:
                heights.append(int(arg))
            except ValueError:
                print(f"  [ignoring non-integer argument: {arg}]")
    if not heights:
        # Default: explore a handful of interesting blocks
        heights = [478559, 630000, 840000]

    print()
    print("  COSMIC CODEC — SIGNAL EXPLORER")
    print()

    words = load_words()
    print()

    for height in heights:
        print(f"  ── BLOCK {height:,} ──────────────────────────────────────────────")
        payloads = fetch_op_returns(height)
        if not payloads:
            print("  (no OP_RETURN payloads)\n")
            continue
        for txid, raw in payloads:
            decode_payload(txid, raw, words, source=f"block {height:,}")

    print(f"  {'═' * 64}")
    print("  END OF TRANSMISSION")
    print()


if __name__ == "__main__":
    main()
