"""
COSMIC CODEC — Daily Solar Message

Picks the most word-rich solar wind channel for the day,
collects its words in the order they arrived,
and generates a message from an AI persona who must use them as a spine.

Usage:
  python3 cosmic_message.py
  python3 cosmic_message.py --tone dada --persona ghost
  python3 cosmic_message.py --date 2017-08-01 --tone scifi --persona scientist
  python3 cosmic_message.py --persona "You are a grieving astronomer."
"""

import argparse
import os
import textwrap
from datetime import datetime, timezone, timedelta

from google import genai

from solar_lattice import (
    load_dict, fetch_omni, bytes_to_letters, to_bytes,
    combined_reading, CHANNEL_META,
)

# ── Tones ──────────────────────────────────────────────────────────────────────

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

# ── Persona presets ─────────────────────────────────────────────────────────────

PERSONAS = {
    "oracle": (
        "You are an oracle — ancient, pattern-seeing, sparse with words. "
        "You speak in fragments. You know more than you say. "
        "You address the reader as if you have been waiting for them."
    ),
    "ghost": (
        "You are a ghost — once human, now signal. "
        "You miss something you cannot name. "
        "You speak from the other side of a threshold the reader is still standing on."
    ),
    "scientist": (
        "You are a scientist who has been quietly destroyed by their findings. "
        "You are precise but overwhelmed. "
        "You report what the data says, and cannot help that it is beautiful."
    ),
    "lover": (
        "You are addressing someone you love. "
        "The signal is a love letter and every word in it is for them. "
        "Be intimate, direct, and unafraid."
    ),
    "stranger": (
        "You have just arrived somewhere. Everything is new. "
        "You report with wonder and without context. "
        "The reader knows more than you do, and that is fine."
    ),
}

# ── Channel scoring ─────────────────────────────────────────────────────────────

def score_channel(name, values, words):
    """
    Score a channel by total word-characters found across Reading I + III.
    Returns (score, word_seq) where word_seq is [(word, 'I'|'III'), ...] in order.
    """
    label, offset, scale, _ = CHANNEL_META[name]
    valid = [v for v in values if v is not None]
    if not valid:
        return 0, []

    raw = to_bytes(values, scale=scale, offset=offset)
    if not raw:
        return 0, []

    letters = bytes_to_letters(raw)
    _, word_seq = combined_reading(letters, words)
    score = sum(len(w) for w, _ in word_seq)
    return score, word_seq


def pick_best_channel(channels, words):
    """
    Score all channels. Returns (best_name, word_seq, all_scores_dict).
    """
    scores = {}
    seqs = {}
    for name in channels:
        score, seq = score_channel(name, channels[name], words)
        scores[name] = score
        seqs[name] = seq

    best = max(scores, key=lambda n: scores[n])
    return best, seqs[best], scores


# ── Message generation ──────────────────────────────────────────────────────────

SYSTEM_TEMPLATE = """\
{persona_desc}

You have received a transmission. It came from the solar wind — a stream of plasma \
and magnetic field that flows past Earth every day. Through a deterministic codec, \
its raw measurements were converted to letters, and from those letters, words emerged.

The words below arrived in this order. They are real. You did not choose them. \
The sun did not choose them either — they emerged from physics passing through a rule.

Your task: write a message using these words as its spine, in this order. \
You may use any other words as connective tissue. \
Do not change, rearrange, or omit any of the signal words. They are fixed.

Tone: {tone_desc}

Rules:
- Use every signal word, in the order given, somewhere in your message.
- Write signal words in ALL CAPS. No bold, no italics, no markdown formatting of any kind.
- Do not explain the codec, the solar wind, or bytes. Just write.
- Length: 100–250 words.
- The goal is not to explain. The goal is to make the reader feel something.\
"""

def generate_message(word_seq, persona_key, tone_key, date_str, channel_label):
    """Call Claude to write the cosmic message."""
    persona_desc = PERSONAS.get(persona_key, persona_key)
    tone_desc = TONES.get(tone_key, TONES["meaningful"])

    system = SYSTEM_TEMPLATE.format(
        persona_desc=persona_desc,
        tone_desc=tone_desc,
    )

    words_block = "\n".join(
        f"  {'  ' if tag == 'I' else '· '}{w.upper()}"
        for w, tag in word_seq
    )
    user_content = (
        f"Date: {date_str}\n"
        f"Channel: {channel_label}\n\n"
        f"Signal words (in order — indent marks source, · = vowel-enabled):\n"
        f"{words_block}"
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


# ── Display ─────────────────────────────────────────────────────────────────────

def print_box(text, width=62):
    print(f"  ┌{'─' * width}┐")
    for para in text.split("\n"):
        for line in textwrap.wrap(para, width=width - 4) or [""]:
            print(f"  │  {line:<{width - 4}}  │")
    print(f"  └{'─' * width}┘")


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="COSMIC CODEC — Daily Solar Message")
    parser.add_argument("--date", default=None,
        help="Date to read (YYYY-MM-DD). Defaults to yesterday (today is rarely complete).")
    parser.add_argument("--tone", default="meaningful",
        choices=list(TONES.keys()),
        help="Tone of the message. (meaningful, realistic, scifi, dada)")
    parser.add_argument("--persona", default="oracle",
        help="Persona preset or custom description. "
             "Presets: oracle, ghost, scientist, lover, stranger")
    parser.add_argument("--channel", default=None,
        help="Force a specific channel (flow_speed, BZ_GSM, proton_density, etc.)")
    args = parser.parse_args()

    # Default to yesterday — today's data is often incomplete
    if args.date:
        date = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        date = datetime.now(timezone.utc) - timedelta(days=1)

    date_str = date.strftime("%Y-%m-%d")
    start = date.strftime("%Y-%m-%dT00:00:00Z")
    stop  = (date + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")

    print()
    print("  ══════════════════════════════════════════════════════════")
    print("  COSMIC CODEC — DAILY SOLAR MESSAGE")
    print(f"  {date_str}  ·  persona: {args.persona}  ·  tone: {args.tone}")
    print("  ══════════════════════════════════════════════════════════")
    print()

    words = load_dict(min_len=3, max_len=12)
    print()

    result = fetch_omni(start, stop)
    if not result or len(result) != 2:
        print("  [could not fetch solar wind data]")
        return
    channels, _ = result
    print()

    # Score all channels
    if args.channel and args.channel in channels:
        best_name = args.channel
        _, word_seq = score_channel(best_name, channels[best_name], words)
        _, _, all_scores = pick_best_channel(channels, words)
        print(f"  [channel forced: {best_name}]")
    else:
        best_name, word_seq, all_scores = pick_best_channel(channels, words)

    print("  ── CHANNEL SCORES ───────────────────────────────────────")
    for name, score in sorted(all_scores.items(), key=lambda x: -x[1]):
        label = CHANNEL_META[name][0]
        marker = "  ◀ chosen" if name == best_name else ""
        bar = "█" * min(score // 8, 36)
        print(f"  {label:<28}  {score:>4}  {bar}{marker}")

    channel_label = CHANNEL_META[best_name][0]

    print(f"\n  ── SIGNAL WORDS  ({channel_label}) ─────────────────")
    if not word_seq:
        print("  (no words found in this channel today)")
        return
    for w, tag in word_seq:
        marker = "   " if tag == 'I' else " · "
        print(f"  {marker}{w.upper()}")

    print(f"\n  ── MESSAGE ──────────────────────────────────────────────")
    print()

    message = generate_message(word_seq, args.persona, args.tone, date_str, channel_label)
    print_box(message)
    print()


if __name__ == "__main__":
    main()
