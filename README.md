# COSMIC CODEC

*Deterministic translation of signals from space into language.*

---

## What this is

Three signals are arriving right now. The solar wind is streaming past the L1 point, a million miles from Earth. GOES satellites are recording X-ray light from the sun — photons that left eight minutes ago and just arrived. And from outside the solar system, ancient particles accelerated by supernovae billions of years old are raining down through the atmosphere.

None of these signals speak English. But they produce numbers, and numbers can be converted to letters, and letters can be searched for words.

This system reads three real-time signals from space, passes them through a series of deterministic codecs, and finds the language inside. No interpretation. No editorial voice. The same input always produces the same output. The codec is a lens, not an author.

---

## The signals

| Signal | Source | Cadence | Character |
|--------|--------|---------|-----------|
| Solar wind | DSCOVR satellite at L1 | 1 minute | Magnetic field threading through Earth's neighborhood |
| X-ray | GOES satellite | 1 minute | Light itself, eight minutes from the sun |
| Cosmic rays | GOES high-energy protons | 5 minutes | Ancient particles from beyond the solar system |

All three are free, public, no API key required. All three update in near-real-time.

---

## The scripts

### `solar_system.py`
Reads all three signals simultaneously and prints what each one said.

```
python3 solar_system.py
python3 solar_system.py --message
python3 solar_system.py --message --tone meaningful
python3 solar_system.py --message --tone dada
```

With `--message`, generates an AI-written transmission from each signal's persona:

| Signal | Persona | Character |
|--------|---------|-----------|
| Solar wind | oracle | ancient, pattern-seeing, has been watching you |
| X-ray | lover | light itself, just arrived, eight minutes from the sun |
| Cosmic rays | ghost | from before the solar system, still moving, passing through |

### `solar_lattice.py`
Full-day solar wind word lattice. Fetches a complete day of solar wind data at 1-minute resolution across seven physical channels — speed, proton density, magnetic field Bx/By/Bz, plasma temperature, flow pressure — and runs three readings on each:

- **Reading I** — word lattice on the raw letter stream: what is literally there
- **Reading II** — vowel injector: the raw stream made pronounceable
- **Reading III** — word lattice on the vowel-enriched stream: words enabled by the codec

Then produces a **combined view** — the full enriched stream with all three readings embedded simultaneously, plus a sequential word list tagged by which reading found each word.

```
python3 solar_lattice.py
```

### `cosmic_message.py`
Standalone daily message generator. Scores all solar wind channels for a given day, picks the most word-rich, collects those words in the order they arrived, and generates an AI-written message using them as a spine.

```
python3 cosmic_message.py --date 2017-08-01
python3 cosmic_message.py --date 2017-08-01 --tone meaningful --persona oracle
python3 cosmic_message.py --date 2017-08-01 --tone dada --persona ghost
python3 cosmic_message.py --date 2017-08-01 --persona "You are a grieving astronomer."
```

Note: uses NASA CDAWeb OMNI data which has a ~2 week lag. Always pass `--date` with a date at least two weeks in the past.

**Tone options:** `meaningful` · `realistic` · `scifi` · `dada`

**Persona presets:** `oracle` · `ghost` · `scientist` · `lover` · `stranger`

Requires a Gemini API key (`GEMINI_API_KEY`). Free tier available at aistudio.google.com.

---

## The codecs

### Codec A — Byte mod 26
Each byte (0–255) maps to a letter A–Z via modulo 26. A minute of solar wind magnetic field measurements becomes a stream of letters. The codec applies identically to every source — solar wind, X-ray, cosmic rays — so the same rule reads them all.

### Codec H — Word Lattice
Dynamic programming: finds the sequence of real words that tiles the most of the letter stream reading left to right, greedily preferring longer words. Gaps are filled with raw letters in brackets. The result is a partial sentence that emerged from physics — not chosen, but found.

### Codec I — Vowel Injector
Inserts a vowel after every run of two or more consonants. The vowel is chosen deterministically from the position in the stream — no randomness. Makes the signal pronounceable. A foreign tongue with its own sound.

### Combined Reading
Runs Codecs H and I together, then overlays the results. Words found in the raw signal appear in plain caps. Words enabled by vowel injection appear in parentheses. Injected vowels appear as `·v·`. Gaps remain as lowercase. The full signal is visible at once, each reading's contribution marked.

```
FILM ·o· STAR ·a· (LULL) ·e· MORO ·u· LOT
```

---

## How the byte conversion works

Physical measurements are converted to bytes before the codec runs:

```
byte = int((value + offset) × scale) % 256
```

Different channels use different scales to fill the full byte range meaningfully:

| Channel | Encoding |
|---------|----------|
| Magnetic field (B total) | nT × 12 |
| Magnetic field (Bz) | (Bz + 20) × 6.5 |
| X-ray flux (long) | flux × 1e9 |
| X-ray flux (short) | flux × 1e10 |
| GOES protons ≥100 MeV | flux × 200 |

Each byte maps to a letter A–Z via mod 26. The letter stream is then read by the word lattice.

---

## The data sources

All data is fetched from public APIs with no key required.

**Solar wind** — [NOAA SWPC DSCOVR](https://www.swpc.noaa.gov/), `rtsw_mag_1m.json` + `rtsw_wind_1m.json`. Magnetic field (Bt, Bz, Bx, By) and plasma (speed, density) at 1-minute cadence. Updated in near-real-time.

**X-ray** — NOAA SWPC GOES, `goes/primary/xrays-1-day.json`. The 0.1–0.8nm band (long X-ray) and 0.05–0.4nm band (short X-ray). Updated every minute. Background is ~1e-7 W/m²; X-class flares reach 1e-4.

**Cosmic rays** — NOAA SWPC GOES, `goes/primary/integral-protons-1-day.json`. High-energy channels (≥100 MeV, ≥500 MeV) are dominated by galactic cosmic rays during quiet solar conditions. Updated every 5 minutes. If NMDB (Neutron Monitor Database, Jungfraujoch) is accessible, it provides true ground-level cosmic ray counts instead.

**AI message generation** — Google Gemini API (`gemini-2.5-flash`). Requires `GEMINI_API_KEY`. Free tier available at [aistudio.google.com](https://aistudio.google.com).

---

## What the signals said on May 14, 2026

Three sources. One moment. One codec.

```
SOLAR WIND    FLO · GAM · MIM · KEA · MEW · LOG · GURGE · GYN · OLE ...
X-RAY         DAS · ASS · KEF · MHO · PEW · HOG · RIG · DAP · AIR ...
COSMIC RAYS   KOA · LAI · HEI · NAN · FAG · ECHO · OKI · JAG · LAN ...
```

---

## Installation

```
pip install requests google-genai
python3 solar_system.py
python3 solar_system.py --message --tone meaningful
```

For message generation:
```
export GEMINI_API_KEY=your-key-here
python3 solar_system.py --message
```

---

*The solar wind does not know it is being read. The codec does not know what it will find. The words emerge from the gap between them.*
