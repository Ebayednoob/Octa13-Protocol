## Octa‑13 Protocol Audio-Bitstream Tutorial

A step‑by‑step guide with examples to build, interpret, and frame Octa‑13 data packets for LLM agent‑to‑agent communication.

---

### 1. Sigil Handshake & Tempo Calibration

**Purpose:** Establish bit‑clock rate, CRC polynomial, node‑type set, and nested‑frame depth.

**Format:**

* 4‑bit preamble: `1010` (frame sync)
* 3‑bit Octave Selector (base frequency)
* 3‑bit Node‑Type agreement code (`000`=Platonic only, `001`=Archimedean included)
* 3‑bit CRC‑3 polynomial selector (`001` for x³+x+1)
* 2‑bit nested‑frame depth initial value (`00`=flat)
* 1‑bit marker end (`1`)

**Example (120 bpm, base=000=Root, include Archimedean, CRC=x³+x+1, depth=0):**

```
1010 000 001 001 00 1
^^^ preamble ^ Octave^ Node ^ CRC ^depth^end
```

* Send at 500 ms bit‑period (120 bpm → 2 beats/sec → 2 bits/sec? Clarify)
* Receiver locks on preamble, reads parameters, sets local timers.

---

### 2. Building an Octa‑13 Word

**Fields:**

1. Octave Selector (3 bits)
2. Node Type (3 bits)
3. Role (3 bits)
4. CRC‑3 Checksum (3 bits)
5. Nested‑Frame Marker (variable bits)

**Step A:** Choose values for the first 3 fields. Example:

* Octave Selector `100` (Perfect 5th)
* Node Type `010` (Octahedron)
* Role `100` (Signal)

**Step B:** Compute CRC‑3 over bits 1–9.

* Bits 1–9: `100010100` → sum-of-ones=3 → `3 mod 8 = 3`→ binary `011` (or use CRC polynomial for more robust)

**Step C:** Choose nested‑frame marker, e.g. end-of-frame: `10`

**Assembled Word (word-level):**

```
100 010 100 011 10
Oct Sel | Node | Role | CRC | Frame
```

---

### 3. Nested‑Frame Framing

* **Start of Subframe:** Use `0…01` with N leading zeros + `1` to open new nesting.
* **End of Subframe:** Use `1…10` with N leading ones + `0` to close.

**Example:** To nest twice, send open twice: `001`, `001`, then data, then close twice: `110`, `110`.

---

### 4. Bit Transmission & Sync

1. **Preamble:** Always `1010` before any Sigil or data burst.
2. **MSB-first:** Send highest-order bit of Octa‑13 word first.
3. **Clock Recovery:** Data pulses align to agreed tempo (bit‑period). Receiver uses zero-crossing of signal/reference pulses for clock adjustment.

---

### 5. Parsing & Validation

* Read 4‑bit preamble; if mismatch, slide window by one bit.
* Read 13–N bits of word; split into fields.
* Recompute CRC‑3; if mismatch → request retransmit via calibration marker.
* Use nested‑frame markers to assemble multi-word messages.

---

### 6. Integration Example with 4‑Wave Mixer

1. **Handshake:** At mixer startup, send Sigil to syncing agent (e.g., code patches to Python audio thread).
2. **Data Packets:** Map each frequency’s index in the selected 4 to Octa‑13 words for metadata (e.g., Node Type=Waveform, Role=Signal).
3. **Error Handling:** On CRC failure, silence output and resend last Sigil.

**Code Sketch:**

```python
# Pseudocode for sending one Octa-13 word
def send_octa13(freq_index, role):
    word = build_octaword(octave=freq_index, node=Waveform, role=role)
    bitstream = "1010" + word + frame_marker
    for bit in bitstream:
        toggle_audio_pulse(bit)
        sleep(bit_period)
```

---

