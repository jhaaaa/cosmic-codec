"""
COSMIC CODEC — Bitcoin Transmission Scanner
Reads what humanity has already inscribed on the blockchain.
Uses mempool.space public API — no key required.
"""

import requests
import time
import sys

MEMPOOL = "https://mempool.space/api"

# ── Genesis (hardcoded — permanent, verifiable) ────────────────────────────────

GENESIS_MESSAGE = "The Times 03/Jan/2009 Chancellor on brink of second bailout for banks"
GENESIS_TX = "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"

# ── API helpers ────────────────────────────────────────────────────────────────

def get(url, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                return r
            time.sleep(2 ** i)
        except Exception as e:
            time.sleep(2 ** i)
    return None

def block_hash_at(height):
    r = get(f"{MEMPOOL}/block-height/{height}")
    return r.text.strip() if r else None

def block_txids(block_hash):
    r = get(f"{MEMPOOL}/block/{block_hash}/txids")
    return r.json() if r else []

def tx_data(txid):
    r = get(f"{MEMPOOL}/tx/{txid}")
    return r.json() if r else None

# ── Decoders ───────────────────────────────────────────────────────────────────

def decode_bytes(raw: bytes):
    """Try to extract readable text from raw bytes."""
    for encoding in ("utf-8", "latin-1"):
        try:
            text = raw.decode(encoding)
            clean = "".join(c for c in text if c.isprintable())
            if len(clean) >= 4:
                ratio = len(clean) / max(len(text), 1)
                if ratio > 0.80:
                    return clean
        except Exception:
            pass
    return None

def extract_op_returns(tx):
    """Find all OP_RETURN outputs in a transaction and decode them."""
    results = []
    for vout in tx.get("vout", []):
        if vout.get("scriptpubkey_type") == "op_return":
            asm = vout.get("scriptpubkey_asm", "")
            # asm looks like: "OP_RETURN OP_PUSHBYTES_nn <hex>"
            parts = asm.split()
            for part in parts:
                if len(part) >= 8 and all(c in "0123456789abcdef" for c in part.lower()):
                    try:
                        raw = bytes.fromhex(part)
                        text = decode_bytes(raw)
                        if text:
                            results.append(text)
                    except Exception:
                        pass
    return results

def extract_coinbase_text(tx):
    """Try to read readable text from a coinbase input script."""
    for vin in tx.get("vin", []):
        if vin.get("is_coinbase"):
            script_hex = vin.get("scriptsig", "")
            if not script_hex:
                continue
            try:
                raw = bytes.fromhex(script_hex)
                # Try progressively shorter slices to skip block height prefix
                for skip in range(0, min(12, len(raw))):
                    text = decode_bytes(raw[skip:])
                    if text and len(text) >= 5 and "Chancellor" not in text:
                        return text
            except Exception:
                pass
    return None

# ── Scanner ────────────────────────────────────────────────────────────────────

def scan_block(height, label="", check_coinbase=False, check_op_return=True):
    """Scan a single block for embedded messages."""
    bh = block_hash_at(height)
    if not bh:
        print(f"  [could not fetch block {height}]")
        return []

    txids = block_txids(bh)
    if not txids:
        return []

    found = []
    # For large blocks, limit to first 200 txs to stay within rate limits
    sample = txids[:200]

    for txid in sample:
        tx = tx_data(txid)
        if not tx:
            continue
        time.sleep(0.15)  # gentle rate limiting

        if check_coinbase:
            text = extract_coinbase_text(tx)
            if text:
                found.append(("coinbase", height, txid, text))

        if check_op_return:
            for text in extract_op_returns(tx):
                found.append(("op_return", height, txid, text))

    return found

def print_transmission(source, block_id, txid, text):
    print(f"  BLOCK    {block_id:,}")
    print(f"  TX       {txid[:36]}...")
    print(f"  SOURCE   {source}")
    print(f"  {'─' * 48}")
    for line in text.splitlines():
        if line.strip():
            print(f"  {line.strip()}")
    print()

# ── Main ───────────────────────────────────────────────────────────────────────

# Blocks to scan — chosen for historical significance or era coverage
SCAN_TARGETS = [
    # Early era — coinbase messages from solo miners
    (170,   "Block 170 — first Bitcoin transaction (Satoshi → Hal Finney)", True,  False),
    (1000,  "Block 1,000",                                                   True,  False),
    (9999,  "Block 9,999",                                                   True,  False),

    # OP_RETURN era begins ~2013–2014
    (278458, "Block 278,458 — one of the first OP_RETURN uses",             False, True),
    (300000, "Block 300,000",                                                False, True),
    (350000, "Block 350,000 — 2014",                                        False, True),

    # Cultural moments
    (478559, "Block 478,559 — Bitcoin Cash fork block",                     True,  True),
    (630000, "Block 630,000 — third halving",                               True,  True),
    (700000, "Block 700,000 — 2021",                                        False, True),
    (800000, "Block 800,000 — Ordinals era",                                False, True),
]

def main():
    print()
    print("  ══════════════════════════════════════════════════")
    print("  COSMIC CODEC — BITCOIN TRANSMISSION SCANNER")
    print("  ══════════════════════════════════════════════════")
    print()

    # Transmission Zero — always present
    print("  ── TRANSMISSION ZERO ──────────────────────────────")
    print("  BLOCK    0")
    print("  TIME     2009-01-03 18:15:05 UTC")
    print("  SOURCE   genesis coinbase — Satoshi Nakamoto")
    print(f"  {'─' * 48}")
    print(f"  {GENESIS_MESSAGE}")
    print()

    total_found = 0

    for height, label, coinbase, op_return in SCAN_TARGETS:
        print(f"  ── {label} ──")
        sys.stdout.flush()

        results = scan_block(height, label, coinbase, op_return)

        if results:
            for source, block_id, txid, text in results:
                print_transmission(source, block_id, txid, text)
                total_found += 1
        else:
            print("  (silence)\n")

        time.sleep(0.5)

    print("  ══════════════════════════════════════════════════")
    print(f"  {total_found} transmissions received (excluding genesis)")
    print("  END OF SCAN")
    print("  ══════════════════════════════════════════════════")
    print()

if __name__ == "__main__":
    main()
