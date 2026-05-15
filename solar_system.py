"""
COSMIC CODEC — Real-Time Signal Reader

Three signals, available now:

  SOLAR WIND  — DSCOVR satellite at L1, magnetic field (NOAA SWPC)
  X-RAY       — GOES satellite, solar X-ray flux (NOAA SWPC)
  COSMIC RAYS — GOES high-energy protons ≥100 MeV, galactic cosmic ray proxy (NOAA SWPC)
                OR Neutron Monitor Database (NMDB) if accessible

All three update every minute. All three are free, no key required.

Usage:
  python3 solar_system.py
  python3 solar_system.py --message --tone meaningful
  python3 solar_system.py --message --tone dada
  python3 solar_system.py --tone scifi --persona ghost
"""

import argparse
import os
import requests
import textwrap
import math
from datetime import datetime, timezone, timedelta

from google import genai

from solar_lattice import (
    load_dict, bytes_to_letters, to_bytes,
    combined_reading, CHANNEL_META,
)

NOAA = "https://services.swpc.noaa.gov/json"
FILL = -999.0

# ── Fetch helpers ───────────────────────────────────────────────────────────────

def get_json(url, label=""):
    try:
        r = requests.get(url, timeout=20)
        if r.status_code == 200:
            return r.json()
        print(f"  [{label} HTTP {r.status_code}]")
    except Exception as e:
        print(f"  [{label} error: {e}]")
    return []


def clean(v, fill=FILL):
    if v is None:
        return None
    try:
        f = float(v)
        return None if f <= fill or not math.isfinite(f) else f
    except (TypeError, ValueError):
        return None

# ── Solar wind (DSCOVR) ────────────────────────────────────────────────────────

def fetch_solar_wind():
    """
    Fetch DSCOVR real-time magnetic field and plasma from NOAA SWPC.
    Returns dict of channel → [values], newest-to-oldest reversed to chronological.
    """
    print("  Fetching solar wind (DSCOVR) ...")
    mag  = get_json(f"{NOAA}/rtsw/rtsw_mag_1m.json",  "DSCOVR mag")
    wind = get_json(f"{NOAA}/rtsw/rtsw_wind_1m.json", "DSCOVR plasma")

    # Both are newest-first — reverse to chronological
    mag  = list(reversed(mag))
    wind = list(reversed(wind))

    channels = {
        "bt":          [clean(d.get("bt"))          for d in mag],
        "bz":          [clean(d.get("bz_gsm"))      for d in mag],
        "bx":          [clean(d.get("bx_gse"))      for d in mag],
        "by":          [clean(d.get("by_gse"))       for d in mag],
        "speed":       [clean(d.get("speed"))        for d in wind],
        "density":     [clean(d.get("density"))      for d in wind],
    }

    for name, vals in channels.items():
        valid = [v for v in vals if v is not None]
        if valid:
            print(f"    {name:<12} {len(valid):>5} valid  "
                  f"range [{min(valid):.3f}, {max(valid):.3f}]")

    latest = mag[-1].get("time_tag") if mag else "?"
    print(f"    latest: {latest}")
    return channels


SOLAR_WIND_CODEC = {
    # DSCOVR at L1. B field ~1–20 nT typical.
    "bt":      ("B TOTAL",    0.0,  12.0),
    "bz":      ("Bz (GSM)",  20.0,   6.5),
    "bx":      ("Bx (GSE)",  20.0,   6.5),
    "by":      ("By (GSE)",  20.0,   6.5),
    "speed":   ("WIND SPEED", 0.0,   0.5),
    "density": ("DENSITY",    0.0,   8.0),
}

# ── X-ray flux (GOES) ──────────────────────────────────────────────────────────

def fetch_xray():
    """
    Fetch GOES real-time X-ray flux (0.1–0.8 nm band) from NOAA SWPC.
    Returns dict of channel → [values].
    """
    print("  Fetching X-ray flux (GOES) ...")
    data = get_json(f"{NOAA}/goes/primary/xrays-1-day.json", "GOES xray")

    # Filter to the 0.1–0.8nm band (the main one), sorted chronologically
    long = sorted(
        [d for d in data if d.get("energy") == "0.1-0.8nm"],
        key=lambda d: d["time_tag"]
    )
    short = sorted(
        [d for d in data if d.get("energy") == "0.05-0.4nm"],
        key=lambda d: d["time_tag"]
    )

    channels = {
        "xray_long":  [clean(d.get("flux")) for d in long],
        "xray_short": [clean(d.get("flux")) for d in short],
    }

    for name, vals in channels.items():
        valid = [v for v in vals if v is not None]
        if valid:
            print(f"    {name:<14} {len(valid):>5} valid  "
                  f"range [{min(valid):.3e}, {max(valid):.3e}]")

    latest = long[-1].get("time_tag") if long else "?"
    print(f"    latest: {latest}")
    return channels


XRAY_CODEC = {
    # X-ray flux in W/m². Background ~1e-8, C flare ~1e-6, X flare ~1e-4.
    # Scale by 1e9 so background (~1e-7) → byte ~100.
    "xray_long":  ("X-RAY 0.1-0.8nm", 0.0, 1e9),
    "xray_short": ("X-RAY 0.05-0.4nm", 0.0, 1e10),
}

# ── Cosmic rays (GOES protons + optional NMDB) ─────────────────────────────────

def fetch_cosmic_rays():
    """
    Fetch high-energy proton flux from GOES as a galactic cosmic ray proxy.
    ≥100 MeV and ≥500 MeV channels are least contaminated by solar energetic particles.
    Tries NMDB (Jungfraujoch station) first; falls back to GOES protons.
    """
    print("  Fetching cosmic rays ...")

    # Try NMDB first (true galactic cosmic rays)
    try:
        from datetime import datetime, timezone, timedelta
        now   = datetime.now(timezone.utc)
        start = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        end   = now.strftime("%Y-%m-%d")
        url = (f"https://www.nmdb.eu/nest/serve.php"
               f"?stations[]=JUNG"
               f"&startdate_0={start}&startdate_1=00:00"
               f"&enddate_0={end}&enddate_1=23:59"
               f"&tresolution=60&output=ascii")
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and "JUNG" in r.text:
            vals = []
            for line in r.text.splitlines():
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.split(";")
                if len(parts) >= 2:
                    vals.append(clean(parts[1].strip()))
            if vals and any(v is not None for v in vals):
                valid = [v for v in vals if v is not None]
                print(f"    JUNG (NMDB)    {len(valid):>5} valid  "
                      f"range [{min(valid):.1f}, {max(valid):.1f}]")
                print(f"    source: NMDB Jungfraujoch (true galactic cosmic rays)")
                return {"nmdb_jung": vals}, "NMDB"
    except Exception:
        pass

    # Fall back to GOES high-energy protons
    data = get_json(f"{NOAA}/goes/primary/integral-protons-1-day.json", "GOES protons")

    channels = {}
    for energy in [">=100 MeV", ">=500 MeV"]:
        rows = sorted(
            [d for d in data if d.get("energy") == energy],
            key=lambda d: d["time_tag"]
        )
        key = energy.replace(">=", "p").replace(" ", "")
        channels[key] = [clean(d.get("flux")) for d in rows]
        valid = [v for v in channels[key] if v is not None]
        if valid:
            print(f"    {key:<14} {len(valid):>5} valid  "
                  f"range [{min(valid):.4f}, {max(valid):.4f}]")

    latest = data[-1].get("time_tag") if data else "?"
    print(f"    latest: {latest}")
    print(f"    source: GOES integral protons (galactic cosmic ray proxy)")
    return channels, "GOES"


def cosmic_ray_codec(source):
    if source == "NMDB":
        return {
            "nmdb_jung": ("COSMIC RAYS (JUNG)", 0.0, 0.05),
        }
    return {
        # GOES proton flux in particles/(cm² s sr). Background ~0.1–1.
        "p100MeV": ("COSMIC RAYS ≥100 MeV", 0.0, 200.0),
        "p500MeV": ("COSMIC RAYS ≥500 MeV", 0.0, 2000.0),
    }

# ── Codec runner ───────────────────────────────────────────────────────────────

def run_codec(values, offset, scale, words):
    valid = [v for v in values if v is not None]
    if not valid:
        return 0, [], 0, ""
    raw = to_bytes(values, scale=scale, offset=offset)
    if not raw:
        return 0, [], 0, ""
    letters = bytes_to_letters(raw)
    _, word_seq = combined_reading(letters, words)
    score = sum(len(w) for w, _ in word_seq)
    return score, word_seq, len(valid), letters


def read_source(source_name, channels, codec_def, words):
    """Score all channels, print results, return (best_label, word_seq, score)."""
    print(f"\n  {'═' * 64}")
    print(f"  {source_name.upper()}")
    print(f"  {'─' * 64}")

    results = []
    for ch_name, (label, offset, scale) in codec_def.items():
        if ch_name not in channels:
            continue
        score, word_seq, n_valid, letters = run_codec(channels[ch_name], offset, scale, words)
        results.append((score, label, word_seq, n_valid, letters))

    if not results:
        print(f"  (no data)")
        return None, [], 0

    results.sort(reverse=True)
    best_score, best_label, best_seq, _, best_letters = results[0]

    for score, label, word_seq, n_valid, _ in results:
        marker = "  ◀" if label == best_label else ""
        bar = "█" * min(score // 8, 40)
        print(f"  {label:<26}  {n_valid:>5} pts  {score:>4} chars  {bar}{marker}")

    # Raw letter stream (Codec A output, before word lattice or vowel injection)
    if best_letters:
        print(f"\n  RAW SIGNAL  ({best_label})")
        width = 64
        for i in range(0, len(best_letters), width):
            print(f"  {best_letters[i:i+width]}")

    if best_seq:
        print(f"\n  SIGNAL WORDS from {best_label}:")
        for w, tag in best_seq:
            marker = "   " if tag == 'I' else " · "
            print(f"  {marker}{w.upper()}")
    else:
        print(f"\n  (no words found)")

    return best_label, best_seq, best_score

# ── AI message generation ───────────────────────────────────────────────────────

SOURCE_PERSONAS = {
    "SOLAR WIND": (
        "oracle",
        "You are an oracle — ancient, pattern-seeing, sparse with words. "
        "You speak in fragments. You know more than you say. "
        "You address the reader as if you have been watching them for a long time."
    ),
    "X-RAY": (
        "lover",
        "You are light itself — not a metaphor for light, but light. "
        "You left the sun eight minutes ago. You have just arrived. "
        "Everything you touch, you illuminate. Be direct. Be warm. Be immediate."
    ),
    "COSMIC RAYS": (
        "ghost",
        "You are ancient. You came from a star that exploded before the sun was born. "
        "You have been traveling for millions of years. "
        "You passed through the solar system without stopping. "
        "You speak from the other side of everything."
    ),
}

TONES = {
    "meaningful": (
        "Find the emotional weight in whatever the words are. "
        "Treat each word as carrying gravity. Be contemplative. "
        "The message should feel like something the reader needed to hear today."
    ),
    "realistic": (
        "Ground the words in physical sensation — body, weather, landscape, time. "
        "Make it immediate and human. "
        "The reader should feel it in their chest, not their head."
    ),
    "scifi": (
        "The words are transmissions from a distant intelligence. "
        "You are an interpreter of signals. Be clinical but awed. "
        "The reader should feel both small and vast."
    ),
    "dada": (
        "Obey the words but let the connective tissue destabilize. "
        "Grammar is optional. Logic is a suggestion. "
        "The reader should feel slightly unmoored — in a good way."
    ),
}

MESSAGE_SYSTEM = """\
{persona_desc}

You have received a transmission. It was encoded in physical measurement — \
converted through a deterministic rule into letters, and from those letters, words emerged.

The words below arrived in this order. They are real. Neither you nor anyone chose them.

Your task: write a message using these words as its spine, in this order. \
You may use any other words as connective tissue. \
Do not change, rearrange, or omit any of the signal words. They are fixed.

Tone: {tone_desc}

Rules:
- Use every signal word, in the order given.
- Write signal words in ALL CAPS. No bold, no italics, no markdown formatting of any kind.
- Do not explain the process. Just write.
- Length: 80–200 words.
- The goal is not to explain. The goal is to make the reader feel something.\
"""

MAX_WORDS = 35


def generate_message(source_name, word_seq, tone_key, date_str, persona_override=None):
    _, default_persona = SOURCE_PERSONAS.get(source_name, ("oracle", SOURCE_PERSONAS["SOLAR WIND"][1]))
    persona_desc = persona_override or default_persona
    tone_desc = TONES.get(tone_key, TONES["meaningful"])

    system = MESSAGE_SYSTEM.format(persona_desc=persona_desc, tone_desc=tone_desc)

    capped = word_seq[:MAX_WORDS]
    words_block = "\n".join(
        f"  {'  ' if tag == 'I' else '· '}{w.upper()}"
        for w, tag in capped
    )
    user_content = (
        f"Date: {date_str}\n"
        f"Source: {source_name}\n\n"
        f"Signal words (in order):\n{words_block}"
    )

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        config=genai.types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=1024,
            thinking_config=genai.types.ThinkingConfig(thinking_budget=0),
        ),
        contents=user_content,
    )
    return response.text.strip()


def print_box(title, text, width=62):
    print(f"\n  ┌─ {title} {'─' * max(0, width - len(title) - 3)}┐")
    for para in text.split("\n"):
        for line in textwrap.wrap(para, width=width - 4) or [""]:
            print(f"  │  {line:<{width - 4}}  │")
    print(f"  └{'─' * width}┘")

# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="COSMIC CODEC — Real-Time Signal Reader")
    parser.add_argument("--message", action="store_true",
        help="Generate an AI message for each source.")
    parser.add_argument("--tone", default="meaningful",
        choices=list(TONES.keys()),
        help="Tone for generated messages.")
    parser.add_argument("--persona", default=None,
        help="Override persona for all sources.")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d %H:%M UTC")

    print()
    print("  ══════════════════════════════════════════════════════════════")
    print("  COSMIC CODEC — REAL-TIME SIGNAL READER")
    print(f"  {date_str}")
    print("  ══════════════════════════════════════════════════════════════")
    print()

    words = load_dict(min_len=3, max_len=12)
    print()

    all_sources = []

    # ── Solar wind ─────────────────────────────────────────────────────────────
    sw_channels = fetch_solar_wind()
    label, seq, score = read_source("SOLAR WIND", sw_channels, SOLAR_WIND_CODEC, words)
    all_sources.append(("SOLAR WIND", label, seq, score))

    print()

    # ── X-ray ──────────────────────────────────────────────────────────────────
    xr_channels = fetch_xray()
    label, seq, score = read_source("X-RAY", xr_channels, XRAY_CODEC, words)
    all_sources.append(("X-RAY", label, seq, score))

    print()

    # ── Cosmic rays ────────────────────────────────────────────────────────────
    cr_channels, cr_source = fetch_cosmic_rays()
    cr_codec = cosmic_ray_codec(cr_source)
    label, seq, score = read_source("COSMIC RAYS", cr_channels, cr_codec, words)
    all_sources.append(("COSMIC RAYS", label, seq, score))

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f"\n\n  {'═' * 64}")
    print(f"  TRANSMISSION  ·  {date_str}")
    print(f"  {'─' * 64}")
    for source_name, channel_label, word_seq, score in all_sources:
        words_str = "  ".join(w.upper() for w, _ in word_seq[:15])
        if not words_str:
            words_str = "(silence)"
        marker = f"[{channel_label}]" if channel_label else ""
        print(f"  {source_name:<14}  {words_str}")
    print()

    # ── AI messages ────────────────────────────────────────────────────────────
    if args.message:
        print(f"  {'═' * 64}")
        print(f"  MESSAGES  ·  tone: {args.tone}")
        print(f"  {'═' * 64}")

        for source_name, channel_label, word_seq, score in all_sources:
            if not word_seq:
                print_box(source_name, "(silence — no words found today)")
                continue

            preset_name, _ = SOURCE_PERSONAS.get(source_name, ("oracle", ""))
            persona_label = args.persona or preset_name

            print(f"\n  generating {source_name} ({persona_label}) ...", flush=True)
            try:
                msg = generate_message(source_name, word_seq, args.tone, date_str,
                                       persona_override=args.persona)
                print_box(f"{source_name} · {persona_label}", msg)
            except Exception as e:
                print(f"  [error: {e}]")

        print()


if __name__ == "__main__":
    main()
