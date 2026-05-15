"""
COSMIC CODEC — Fork Block Decoder
Fetches the raw binary from the two unreadable transmissions
at Bitcoin block 478,559 (the Bitcoin/Bitcoin Cash chain split)
and passes them through language-finding codecs.
"""

import requests
import time

MEMPOOL = "https://mempool.space/api"

# The two "unreadable" transmissions from the fork block
FORK_TXIDS = [
    "20f18a48f2d6a630d7f48dc4f2e1b456717c04e3f9c3c8e12e8a7a3b5c2d1e0",
    "55ec8eada8b0d8cd88689e4c61bf66d6cf44a4b5c6d7e8f9a0b1c2d3e4f5a6b",
]

# Block 478,559 — we'll scan all its OP_RETURN outputs directly
FORK_BLOCK_HEIGHT = 478559

# ── Word list ──────────────────────────────────────────────────────────────────

def load_words(min_len=3, max_len=10):
    """
    Load vocabulary. Priority:
      1. lexicon_words.py  — mined from Bitcoin OP_RETURN (blockchain speaks itself)
      2. /usr/share/dict/words  — system dictionary
      3. built-in fallback
    """
    wordset = set()

    # Try blockchain lexicon first
    try:
        from lexicon_words import WORDS
        wordset = {w for w in WORDS if min_len <= len(w) <= max_len}
        print(f"  [lexicon: blockchain-derived, {len(wordset):,} words]")
        return wordset
    except ImportError:
        pass

    try:
        with open("/usr/share/dict/words") as f:
            for line in f:
                w = line.strip().lower()
                if min_len <= len(w) <= max_len and w.isalpha():
                    wordset.add(w)
        print(f"  [dictionary: {len(wordset):,} words loaded]")
    except FileNotFoundError:
        # Minimal fallback
        wordset = {
            "the","and","for","are","but","not","you","all","can","had",
            "her","was","one","our","out","day","get","has","him","his",
            "how","man","new","now","old","see","two","way","who","boy",
            "did","its","let","put","say","she","too","use","void","echo",
            "wave","dark","time","life","star","fire","deep","hold","code",
            "null","zero","open","door","mind","soul","body","data","lost",
            "born","free","wall","fall","call","hall","ball","tall","small",
            "over","ever","even","only","also","back","been","came","come",
            "each","from","give","have","here","into","just","keep","kind",
            "know","last","left","like","live","long","look","made","make",
            "many","more","most","move","much","must","name","near","need",
            "next","once","only","part","pass","past","play","real","rest",
            "same","send","side","some","take","tell","them","then","they",
            "this","told","turn","very","want","well","went","were","what",
            "when","will","with","word","work","year","your","able","also",
            "area","base","both","case","city","does","down","draw","drop",
            "else","face","fact","feel","fill","find","form","full","gone",
            "good","grow","half","hand","hard","head","hear","help","high",
            "home","hope","idea","into","join","just","land","late","lead",
            "less","line","list","love","main","mark","mean","meet","mile",
            "mine","miss","note","open","page","plan","plus","poor","push",
            "read","ring","rise","road","rock","role","room","root","rule",
            "safe","seem","self","ship","shop","show","sign","size","skin",
            "slip","slow","sort","spot","stay","step","stop","sure","swim",
            "talk","task","test","thus","till","tiny","tree","true","turn",
            "type","unit","upon","used","user","vary","vast","view","vote",
            "wait","walk","warm","wash","wear","week","west","wide","wind",
            "wire","wise","wish","whom","wild","zero","zone","bit","bin",
            "hex","raw","key","map","net","set","bit","bus","cpu","ram",
            "rom","run","sun","sky","sea","ice","air","earth","moon","void",
        }
        print(f"  [dictionary: using built-in fallback, {len(wordset)} words]")
    return wordset


# ── Codec A: bytes → letters ───────────────────────────────────────────────────

def bytes_to_letters(raw: bytes) -> str:
    return "".join(chr(ord('A') + b % 26) for b in raw)

# ── Codec G: Word Miner ────────────────────────────────────────────────────────

def codec_word_mine(letters: str, wordset: set, min_len=3) -> list:
    """
    Slide a window across the letter stream.
    Every real English word found as a substring is a signal.
    """
    letters_lower = letters.lower()
    found = []
    seen = set()
    for start in range(len(letters_lower)):
        for length in range(min_len, min(12, len(letters_lower) - start + 1)):
            candidate = letters_lower[start:start + length]
            if candidate in wordset and candidate not in seen:
                seen.add(candidate)
                found.append((start, candidate))
    found.sort(key=lambda x: (-len(x[1]), x[0]))  # longest first
    return found

# ── Codec H: Word Lattice ──────────────────────────────────────────────────────

def codec_word_lattice(letters: str, wordset: set) -> str:
    """
    Dynamic programming: find the sequence of real words that tiles
    the most of the letter string, reading left to right.
    Gaps are filled with the raw letters.
    """
    n = len(letters)
    letters_lower = letters.lower()

    # dp[i] = best word sequence to reach position i
    dp = [None] * (n + 1)
    dp[0] = []

    for i in range(n):
        if dp[i] is None:
            # Try skipping one letter
            if i > 0 and dp[i-1] is not None:
                dp[i] = dp[i-1] + [f"[{letters[i-1]}]"]
            else:
                dp[i] = [f"[{letters[i]}]"] if i == 0 else None
                continue

        for length in range(3, min(12, n - i + 1)):
            candidate = letters_lower[i:i + length]
            if candidate in wordset:
                if dp[i + length] is None:
                    dp[i + length] = dp[i] + [candidate]

    # Walk back from end
    result = dp[n]
    if result is None:
        # fallback: just chunk the letters
        result = [letters[i:i+4] for i in range(0, n, 4)]

    return " ".join(result)

# ── Codec I: Vowel Injector ────────────────────────────────────────────────────

VOWELS = "AEIOU"
CONSONANTS = "BCDFGHJKLMNPQRSTVWXYZ"

def codec_vowel_inject(letters: str) -> str:
    """
    Insert a vowel after every run of 2+ consonants.
    The vowel is chosen deterministically from the byte value.
    Makes the stream pronounceable — a foreign tongue.
    """
    result = []
    consonant_run = 0
    for i, c in enumerate(letters.upper()):
        result.append(c)
        if c in CONSONANTS:
            consonant_run += 1
            if consonant_run >= 2:
                # Pick vowel based on position
                result.append(VOWELS[i % 5])
                consonant_run = 0
        else:
            consonant_run = 0

    # Break into syllable-like groups of 4–6 chars
    joined = "".join(result)
    chunks = []
    i = 0
    while i < len(joined):
        size = 4 + (ord(joined[i]) % 3)
        chunks.append(joined[i:i+size])
        i += size
    return " ".join(chunks)

# ── Codec J: Binary → Morse → Text ────────────────────────────────────────────

MORSE_TO_LETTER = {
    ".-": "A", "-...": "B", "-.-.": "C", "-..": "D", ".": "E",
    "..-.": "F", "--.": "G", "....": "H", "..": "I", ".---": "J",
    "-.-": "K", ".-..": "L", "--": "M", "-.": "N", "---": "O",
    ".--.": "P", "--.-": "Q", ".-.": "R", "...": "S", "-": "T",
    "..-": "U", "...-": "V", ".--": "W", "-..-": "X", "-.--": "Y",
    "--..": "Z",
}

def codec_morse(raw: bytes) -> str:
    """
    Treat each bit as dot (0) or dash (1).
    Group bits into morse code characters (variable length).
    Decode to letters where possible.
    """
    bits = "".join(format(b, "08b") for b in raw)
    # Try grouping by 2, 3, and 4 bits as morse symbols
    result = []
    i = 0
    while i < len(bits):
        found = False
        for length in [4, 3, 2, 1]:
            chunk = bits[i:i+length]
            morse = chunk.replace("0", ".").replace("1", "-")
            if morse in MORSE_TO_LETTER:
                result.append(MORSE_TO_LETTER[morse])
                i += length
                found = True
                break
        if not found:
            i += 1
    return " ".join(
        "".join(result[i:i+6]) for i in range(0, len(result), 6)
    )

# ── Fetcher ────────────────────────────────────────────────────────────────────

def get(url):
    try:
        r = requests.get(url, timeout=15)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

def fetch_fork_op_returns():
    """Fetch raw OP_RETURN hex from block 478,559."""
    print(f"  Fetching block {FORK_BLOCK_HEIGHT} hash...")
    r = requests.get(f"{MEMPOOL}/block-height/{FORK_BLOCK_HEIGHT}", timeout=15)
    block_hash = r.text.strip()
    print(f"  Hash: {block_hash}")

    print("  Fetching transaction list...")
    txids = get(f"{MEMPOOL}/block/{block_hash}/txids") or []
    print(f"  {len(txids)} transactions in block")

    results = []
    checked = 0
    for txid in txids[:300]:
        tx = get(f"{MEMPOOL}/tx/{txid}")
        if not tx:
            continue
        time.sleep(0.12)
        for vout in tx.get("vout", []):
            if vout.get("scriptpubkey_type") == "op_return":
                asm = vout.get("scriptpubkey_asm", "")
                parts = asm.split()
                for part in parts:
                    if len(part) >= 8 and all(c in "0123456789abcdef" for c in part.lower()):
                        try:
                            raw = bytes.fromhex(part)
                            results.append((txid, part, raw))
                        except Exception:
                            pass
        checked += 1

    print(f"  Scanned {checked} transactions, found {len(results)} OP_RETURN payloads\n")
    return results

# ── Main ───────────────────────────────────────────────────────────────────────

def decode_payload(label, txid, hex_data, raw, wordset):
    letters = bytes_to_letters(raw)

    print(f"  {'═' * 62}")
    print(f"  TRANSMISSION — block 478,559 (Bitcoin/BCH fork)")
    print(f"  TX      {txid[:40]}...")
    print(f"  RAW HEX {hex_data[:48]}{'...' if len(hex_data) > 48 else ''}")
    print(f"  BYTES   {len(raw)}")
    print()

    print(f"  CODEC A — byte mod 26 → letters:")
    print(f"  → {'  '.join(letters[i:i+8] for i in range(0, len(letters), 8))}")
    print()

    print(f"  CODEC G — word miner (English words found as substrings):")
    found_words = codec_word_mine(letters, wordset, min_len=3)
    if found_words:
        # Show top 20 by length
        for pos, word in found_words[:20]:
            print(f"     pos {pos:02d}  {word}")
    else:
        print("     (no words found)")
    print()

    print(f"  CODEC H — word lattice (left-to-right word tiling):")
    lattice = codec_word_lattice(letters, wordset)
    print(f"  → {lattice}")
    print()

    print(f"  CODEC I — vowel injector (pronounceable syllables):")
    print(f"  → {codec_vowel_inject(letters)}")
    print()

    print(f"  CODEC J — bits → morse → letters:")
    morse_out = codec_morse(raw)
    print(f"  → {morse_out}")
    print()


def main():
    print()
    print("  COSMIC CODEC — FORK BLOCK DECODER")
    print("  Block 478,559 — the moment Bitcoin split in two")
    print()

    wordset = load_words()
    print()

    payloads = fetch_fork_op_returns()

    if not payloads:
        print("  No OP_RETURN payloads found.")
        return

    for i, (txid, hex_data, raw) in enumerate(payloads):
        decode_payload(f"Payload {i+1}", txid, hex_data, raw, wordset)

    print(f"  {'═' * 62}")
    print("  END OF TRANSMISSION")
    print()

if __name__ == "__main__":
    main()
