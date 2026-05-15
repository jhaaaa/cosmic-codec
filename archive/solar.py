"""
COSMIC CODEC — Solar Signal Decoder
August 1, 2017. 13:16:14 UTC.

Block 478,559 was mined. Bitcoin split in two.
The sun was broadcasting. What was it saying?

Data sources:
  - NASA CDAWeb HAPI: OMNI_HRO_1MIN solar wind (speed, density, Bz)
  - GFZ Potsdam: Kp geomagnetic activity index
"""

import requests
import struct
import time
from datetime import datetime, timezone

# ── The moment ────────────────────────────────────────────────────────────────

FORK_TIMESTAMP = 1501593374          # Unix timestamp, verified from Bitcoin block
FORK_UTC = datetime(2017, 8, 1, 13, 16, 14, tzinfo=timezone.utc)
FORK_DATE = "2017-08-01"

# ── Codecs ────────────────────────────────────────────────────────────────────

def load_words(min_len=3, max_len=12):
    try:
        from lexicon_words import WORDS
        words = {w for w in WORDS if min_len <= len(w) <= max_len}
        print(f"  [lexicon: blockchain-derived, {len(words):,} words]")
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
    print("  [lexicon: minimal fallback]")
    return {"the","and","for","are","not","you","all","can","see","one","has",
            "was","from","that","this","with","have","will","your","they","time",
            "void","echo","dark","fire","star","life","free","soul","mind","deep",
            "born","wave","code","zero","open","door","body","data","lost","hold",
            "sun","light","wind","storm","quiet","flow","pulse","field","force",
            "signal","noise","north","south","east","west","earth","moon","dawn",
            "dusk","tide","wave","rise","fall","speed","dense","flux","core"}

def bytes_to_letters(raw: bytes) -> str:
    return "".join(chr(ord('A') + b % 26) for b in raw)

def word_mine(letters: str, words: set) -> list:
    lower = letters.lower()
    found, seen = [], set()
    for start in range(len(lower)):
        for length in range(3, min(13, len(lower) - start + 1)):
            candidate = lower[start:start + length]
            if candidate in words and candidate not in seen:
                seen.add(candidate)
                found.append((start, candidate))
    found.sort(key=lambda x: (-len(x[1]), x[0]))
    return found

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

def decode_signal(label: str, raw: bytes, words: set, note: str = ""):
    letters = bytes_to_letters(raw)
    print(f"\n  {'═' * 64}")
    print(f"  {label}")
    if note:
        print(f"  {note}")
    print(f"  BYTES   {len(raw)}")
    print(f"  RAW     {' '.join(f'{b:03d}' for b in raw[:24])}{'...' if len(raw) > 24 else ''}")
    print()
    print("  CODEC A — measurement values mod 26 → letters:")
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
    print("  CODEC I — vowel injector:")
    print(f"  → {vowel_inject(letters)}")
    print()
    print("  CODEC J — bits → morse → letters:")
    print(f"  → {morse_decode(raw)}")
    print()

# ── Byte conversion ────────────────────────────────────────────────────────────

def values_to_bytes(values: list, scale: float = 1.0, offset: float = 0.0) -> bytes:
    """
    Convert a list of floats to bytes.
    Each value is shifted by offset, scaled, rounded, then taken mod 256.
    No clamping — the full cycle of the byte wheel is allowed.
    """
    result = []
    for v in values:
        if v is None or v != v:  # skip None and NaN
            continue
        result.append(int((v + offset) * scale) % 256)
    return bytes(result)

# ── Data fetchers ──────────────────────────────────────────────────────────────

def get(url, timeout=20):
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200:
            return r
    except Exception as e:
        print(f"  [fetch failed: {url[:60]}... — {e}]")
    return None

def fetch_kp_day():
    """
    Fetch 3-hourly Kp index for August 1, 2017 from GFZ Potsdam.
    Returns list of (time_str, kp_value) tuples.
    """
    print("  Fetching Kp index (GFZ Potsdam)...")
    url = (
        "https://kp.gfz-potsdam.de/app/json/"
        "?start=2017-08-01T00:00:00Z"
        "&end=2017-08-02T00:00:00Z"
        "&index=Kp"
    )
    r = get(url)
    if not r:
        return []
    try:
        data = r.json()
        times = data.get("datetime", data.get("time_tag", []))
        kps   = data.get("Kp",       data.get("kp", []))
        if not kps:
            # Try flat list format
            if isinstance(data, list):
                return [(str(i*3) + ":00", v) for i, v in enumerate(data)]
        return list(zip(times, kps))
    except Exception as e:
        print(f"  [Kp parse error: {e}]")
        return []

def fetch_solar_wind_hapi(start_iso: str, stop_iso: str, dataset: str = "OMNI_HRO_1MIN"):
    """
    Fetch solar wind measurements via NASA CDAWeb (CSV format).
    OMNI_HRO_1MIN column layout (0-indexed after timestamp):
      col 0:  Time
      col 15: BZ_GSM
      col 18: flow_speed
      col 22: proton_density
    Returns (times, speeds, densities, bzs)
    """
    url = (
        f"https://cdaweb.gsfc.nasa.gov/hapi/data"
        f"?id={dataset}"
        f"&time.min={start_iso}"
        f"&time.max={stop_iso}"
    )
    print(f"  Fetching solar wind (NASA CDAWeb, {dataset})...")
    r = get(url, timeout=30)
    if not r:
        return [], [], [], []

    # Column indices (0=Time, then data columns 1-N)
    # Determined from HAPI /info parameter order
    IDX_BZ    = 15   # BZ_GSM
    IDX_SPEED = 18   # flow_speed
    IDX_DENS  = 22   # proton_density
    FILL_VALS = {9999.99, 99999.9, 9999999.0, 999.99}

    def clean(v):
        try:
            f = float(v)
            return None if f in FILL_VALS or f > 9000 else f
        except Exception:
            return None

    times, speeds, densities, bzs = [], [], [], []
    for line in r.text.strip().splitlines():
        parts = line.split(",")
        if len(parts) <= IDX_DENS:
            continue
        times.append(parts[0])
        speeds.append(clean(parts[IDX_SPEED]))
        densities.append(clean(parts[IDX_DENS]))
        bzs.append(clean(parts[IDX_BZ]))

    n_valid = sum(1 for v in speeds if v is not None)
    print(f"  {len(times)} measurements, {n_valid} valid speed readings")
    return times, speeds, densities, bzs

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print()
    print("  COSMIC CODEC — SOLAR SIGNAL DECODER")
    print("  Block 478,559 mined: 2017-08-01T13:16:14Z")
    print("  Bitcoin split in two. What was the sun broadcasting?")
    print()

    words = load_words()
    print()

    # ── 1. Kp index for the full day ───────────────────────────────────────────
    print("  ── KP INDEX: August 1, 2017 (geomagnetic activity) ────────────")
    print("  Scale: 0 = deep quiet  9 = severe geomagnetic storm")
    print()
    kp_readings = fetch_kp_day()

    if kp_readings:
        print("  TIME          Kp    BAR")
        kp_values = []
        for t, kp in kp_readings:
            try:
                v = float(kp)
                kp_values.append(v)
                bar = "█" * int(v * 2)
                t_short = str(t)[11:16] if len(str(t)) > 10 else str(t)
                print(f"  {t_short}       {v:4.1f}  {bar}")
            except (ValueError, TypeError):
                pass
        print()

        if kp_values:
            # Kp range 0-9; scale × 28 to spread across byte range
            raw_kp = values_to_bytes(kp_values, scale=28.0)
            decode_signal(
                "SIGNAL: KP INDEX — full day, August 1 2017",
                raw_kp,
                words,
                note=f"8 3-hourly geomagnetic measurements → bytes (value × 28 mod 256)"
            )
    else:
        print("  [Kp data unavailable]\n")

    time.sleep(0.5)

    # ── 2. Solar wind — the hour of the fork ──────────────────────────────────
    print("  ── SOLAR WIND: 13:00–14:00 UTC (the hour of the fork) ─────────")
    print("  Source: ACE/DSCOVR via NASA OMNI database, 1-minute resolution")
    print()

    times, speeds, densities, bzs = fetch_solar_wind_hapi(
        "2017-08-01T13:00:00.000Z",
        "2017-08-01T14:00:00.000Z"
    )

    if speeds:
        # Print a sample
        print("  TIME (UTC)     SPEED km/s  DENSITY p/cm³   Bz nT")
        for i, (t, sp, dn, bz) in enumerate(zip(times, speeds, densities, bzs)):
            if i % 5 == 0:  # every 5 minutes
                t_short = str(t)[11:19]
                sp_s = f"{sp:7.1f}" if sp else "    ---"
                dn_s = f"{dn:7.2f}" if dn else "    ---"
                bz_s = f"{bz:+7.2f}" if bz else "    ---"
                print(f"  {t_short}     {sp_s}     {dn_s}     {bz_s}")
        print()

        # Speed → bytes: typical range 300-800 km/s, ÷2 fits in ~0-255
        valid_speeds = [v for v in speeds if v is not None]
        if valid_speeds:
            raw_speed = values_to_bytes(valid_speeds, scale=0.5)
            decode_signal(
                "SIGNAL: SOLAR WIND SPEED — 13:00–14:00 UTC",
                raw_speed,
                words,
                note=f"60 measurements @ 1-min resolution. Speed (km/s) × 0.5 mod 256. "
                     f"Mean: {sum(valid_speeds)/len(valid_speeds):.0f} km/s"
            )

        # Bz → bytes: Bz typically –20 to +20 nT; shift by +30, ×4
        valid_bzs = [v for v in bzs if v is not None]
        if valid_bzs:
            raw_bz = values_to_bytes(valid_bzs, offset=30.0, scale=4.0)
            mean_bz = sum(valid_bzs) / len(valid_bzs)
            polarity = "southward (geoeffective)" if mean_bz < 0 else "northward (quiet)"
            decode_signal(
                "SIGNAL: INTERPLANETARY MAGNETIC FIELD Bz — 13:00–14:00 UTC",
                raw_bz,
                words,
                note=f"Bz in GSM coordinates. Mean: {mean_bz:+.2f} nT ({polarity}). "
                     f"(value + 30) × 4 mod 256"
            )

        # Density → bytes: typical 1-30 protons/cm³, ×8
        valid_dens = [v for v in densities if v is not None]
        if valid_dens:
            raw_dens = values_to_bytes(valid_dens, scale=8.0)
            decode_signal(
                "SIGNAL: SOLAR WIND DENSITY — 13:00–14:00 UTC",
                raw_dens,
                words,
                note=f"Proton density (particles/cm³) × 8 mod 256. "
                     f"Mean: {sum(valid_dens)/len(valid_dens):.1f} p/cm³"
            )

    else:
        print("  [1-minute data unavailable]")

    # ── 3. The exact minute: 13:16 ────────────────────────────────────────────
    print()
    print("  ── THE EXACT MINUTE: 13:16:14 UTC ─────────────────────────────")
    print("  Block 478,559 was accepted by the network.")
    print("  Bitcoin and Bitcoin Cash became two separate chains.")
    print()

    if speeds and len(speeds) >= 16:
        # Minute 16 = index 16 in the 13:00–14:00 series
        minute_16_speed   = speeds[16]
        minute_16_density = densities[16]
        minute_16_bz      = bzs[16]

        if minute_16_speed:
            print(f"  Solar wind speed:    {minute_16_speed:.1f} km/s")
        if minute_16_density:
            print(f"  Proton density:      {minute_16_density:.2f} particles/cm³")
        if minute_16_bz:
            print(f"  Magnetic field Bz:   {minute_16_bz:+.2f} nT")
        print()

        # Combine all three measurements into one 3-byte signal
        moment_bytes = []
        if minute_16_speed:
            moment_bytes.append(int(minute_16_speed * 0.5) % 256)
        if minute_16_density:
            moment_bytes.append(int(minute_16_density * 8) % 256)
        if minute_16_bz:
            moment_bytes.append(int((minute_16_bz + 30) * 4) % 256)

        if moment_bytes:
            decode_signal(
                "SIGNAL: THE MOMENT — 2017-08-01T13:16:14Z",
                bytes(moment_bytes),
                words,
                note="Three measurements. The sun compressed to a single breath."
            )

    print(f"  {'═' * 64}")
    print("  END OF SOLAR TRANSMISSION")
    print()


if __name__ == "__main__":
    main()
