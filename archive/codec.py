"""
COSMIC CODEC — Multi-codec translator
Apply several deterministic codecs to blockchain data and compare outputs.
No API calls — works on any raw data you feed it.
"""

# ── Known Genesis Block Data (permanent, verifiable) ───────────────────────────

GENESIS = {
    "block":     0,
    "hash":      "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f",
    "nonce":     2083236893,
    "timestamp": 1231006505,
    "merkle":    "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b",
    "message":   "The Times 03/Jan/2009 Chancellor on brink of second bailout for banks",
}

# Additional blocks of interest (hashes verifiable at mempool.space)
BLOCKS = {
    170:    "00000000d1145790a8694403d4063f323d499e655c83426834d4ce2f8dd4a2ee",  # first tx
    478559: "0000000000000000011865af4122fe3b144e2cbeea86142e8ff2fb4107352d43",  # BCH fork
    630000: "000000000000000000024bead8df69990852c202db0e0097c1a12ea637d7e96d",  # 3rd halving
    840000: "0000000000000000000320283a032748cef8227873ff4872689bf23f1cda83a5",  # 4th halving
}

# ── Codec A: Byte mod 26 → A–Z ─────────────────────────────────────────────────

def codec_byte_mod26(hex_str: str) -> str:
    """
    Each byte (0–255) maps to A–Z via modulo 26.
    A 32-byte hash → 32 letters.
    Leading zeros in proof-of-work hashes → 'A' (the alphabet begins where mining ends).
    """
    raw = bytes.fromhex(hex_str.zfill(64))
    return "".join(chr(ord('A') + b % 26) for b in raw)

# ── Codec B: Hex char direct → 16-letter alphabet ─────────────────────────────

HEX_MAP = {
    '0': 'A', '1': 'B', '2': 'C', '3': 'D', '4': 'E', '5': 'F',
    '6': 'G', '7': 'H', '8': 'I', '9': 'J',
    'a': 'K', 'b': 'L', 'c': 'M', 'd': 'N', 'e': 'O', 'f': 'P'
}

def codec_hex_direct(hex_str: str) -> str:
    """
    Direct substitution: 0→A, 1→B … 9→J, a→K, b→L … f→P.
    Alphabet of 16. Every hex digit becomes a letter.
    """
    return "".join(HEX_MAP.get(c, c) for c in hex_str.lower())

# ── Codec C: Integer → base-26 word ────────────────────────────────────────────

def int_to_base26(n: int) -> str:
    """Convert an integer to a base-26 'word' (A=0, B=1 … Z=25)."""
    if n == 0:
        return "A"
    letters = []
    while n > 0:
        letters.append(chr(ord('A') + n % 26))
        n //= 26
    return "".join(reversed(letters))

def codec_base26(hex_str: str) -> str:
    """Treat the entire hex string as one large integer, convert to base-26."""
    n = int(hex_str, 16)
    return int_to_base26(n)

# ── Codec D: Bytes → NATO phonetic alphabet ────────────────────────────────────

NATO = [
    "Alpha","Bravo","Charlie","Delta","Echo","Foxtrot","Golf","Hotel",
    "India","Juliet","Kilo","Lima","Mike","November","Oscar","Papa",
    "Quebec","Romeo","Sierra","Tango","Uniform","Victor","Whiskey",
    "X-ray","Yankee","Zulu"
]

def codec_nato(hex_str: str) -> str:
    """Each byte mod 26 → NATO phonetic word. Reads like a transmission."""
    raw = bytes.fromhex(hex_str.zfill(64))
    words = [NATO[b % 26] for b in raw]
    # Group into lines of 8 words
    lines = [" ".join(words[i:i+8]) for i in range(0, len(words), 8)]
    return "\n    ".join(lines)

# ── Codec E: Nonce → base-26 word ─────────────────────────────────────────────

def codec_nonce(nonce: int) -> str:
    """The mining nonce converted to base-26. One word per block."""
    return int_to_base26(nonce)

# ── Codec F: Timestamp → base-26 ──────────────────────────────────────────────

def codec_timestamp(ts: int) -> str:
    return int_to_base26(ts)

# ── Chunked reading — group letters into word-sized chunks ────────────────────

def chunk(s: str, size: int = 5) -> str:
    """Break a long letter string into space-separated chunks for readability."""
    return " ".join(s[i:i+size] for i in range(0, len(s), size))

# ── Display ────────────────────────────────────────────────────────────────────

def print_block(label: str, data: dict):
    h = data["hash"]
    print(f"\n  {'═' * 60}")
    print(f"  {label}")
    print(f"  {'═' * 60}")
    print(f"  hash      {h}")
    if "nonce" in data:
        print(f"  nonce     {data['nonce']}")
    if "timestamp" in data:
        print(f"  timestamp {data['timestamp']}")
    if "message" in data:
        print(f"\n  EMBEDDED MESSAGE:")
        print(f"  → {data['message']}")

    print(f"\n  CODEC A — byte mod 26 → A–Z (32 letters from 32 bytes):")
    print(f"  → {chunk(codec_byte_mod26(h))}")

    print(f"\n  CODEC B — hex direct → 16-letter alphabet:")
    print(f"  → {chunk(codec_hex_direct(h))}")

    print(f"\n  CODEC C — hash as integer → base-26:")
    b26 = codec_base26(h)
    print(f"  → {chunk(b26)}")
    print(f"  ({len(b26)} letters)")

    print(f"\n  CODEC D — byte mod 26 → NATO phonetic:")
    print(f"    {codec_nato(h)}")

    if "nonce" in data:
        print(f"\n  CODEC E — nonce → base-26:")
        print(f"  → {codec_nonce(data['nonce'])}")

    if "timestamp" in data:
        print(f"\n  CODEC F — timestamp → base-26:")
        print(f"  → {codec_timestamp(data['timestamp'])}")

    print()

# ── Merkle root ────────────────────────────────────────────────────────────────

def print_merkle(merkle_hex: str):
    print(f"\n  MERKLE ROOT (the root of all genesis transactions):")
    print(f"  {merkle_hex}")
    print(f"\n  CODEC A:")
    print(f"  → {chunk(codec_byte_mod26(merkle_hex))}")
    print(f"\n  CODEC B:")
    print(f"  → {chunk(codec_hex_direct(merkle_hex))}")
    print(f"\n  CODEC C (integer → base-26):")
    b26 = codec_base26(merkle_hex)
    print(f"  → {chunk(b26)}")

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print()
    print("  COSMIC CODEC — MULTI-CODEC TRANSLATOR")
    print("  Deterministic translation of blockchain data into language.")
    print()

    # Genesis
    print_block("BLOCK 0 — GENESIS", GENESIS)

    print("  ── GENESIS MERKLE ROOT ──────────────────────────────────────")
    print_merkle(GENESIS["merkle"])

    # Other significant blocks
    for height, bh in BLOCKS.items():
        label_map = {
            170:    "BLOCK 170 — first Bitcoin transaction (Satoshi → Hal Finney)",
            478559: "BLOCK 478,559 — Bitcoin / Bitcoin Cash chain split",
            630000: "BLOCK 630,000 — third halving",
            840000: "BLOCK 840,000 — fourth halving",
        }
        print_block(label_map.get(height, f"BLOCK {height:,}"), {"hash": bh})

    print(f"  {'═' * 60}")
    print("  END OF TRANSMISSION")
    print(f"  {'═' * 60}")
    print()

if __name__ == "__main__":
    main()
