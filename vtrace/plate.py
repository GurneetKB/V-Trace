"""Licence-plate string utilities: normalisation, wildcard matching and degradation.

'?' is a wildcard for one unknown character (e.g. a partial plate "SGX12??").
"""
import random
import re
import string

# Characters OCR commonly confuses (used to simulate a blurred plate)
CONFUSABLE = {"0": "OD", "O": "0D", "D": "0O", "1": "IL7", "I": "1L", "L": "1I", "5": "S", "S": "5",
              "8": "B", "B": "8", "2": "Z", "Z": "2", "6": "G", "G": "6", "7": "1T", "T": "7"}


def normalize(text, keep_wildcards=False):
    if not text:
        return ""
    allowed = r"[^A-Z0-9?]" if keep_wildcards else r"[^A-Z0-9]"
    return re.sub(allowed, "", text.upper())


def _lev(a, b):
    """Levenshtein distance where '?' matches any character at zero cost."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            sub = 0 if (ca == cb or ca == "?" or cb == "?") else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + sub))
        prev = cur
    return prev[-1]


def similarity(a, b):
    """Similarity in [0,1] between two plate strings (wildcard aware)."""
    a, b = normalize(a, True), normalize(b, True)
    if not a or not b:
        return 0.0
    return 1.0 - _lev(a, b) / max(len(a), len(b))


def query_similarity(query, plate):
    """How well a (possibly partial / wildcarded) user query matches an observed plate.

    A short query may match any part of the plate, so we slide it along the plate and
    also fall back to edit-distance similarity to tolerate OCR errors.
    """
    q, p = normalize(query, True), normalize(plate, True)
    if not q or not p:
        return 0.0
    best = similarity(q, p)
    known = [c for c in q if c != "?"]
    if known and len(q) <= len(p):
        for off in range(len(p) - len(q) + 1):
            window = p[off:off + len(q)]
            hits = sum(1 for qc, pc in zip(q, window) if qc != "?" and (qc == pc or pc == "?"))
            best = max(best, hits / len(known))
    return float(best)


def random_plate(rng):
    """Singapore-style synthetic plate, e.g. SGX1234A (used only for the benchmark)."""
    letters = string.ascii_uppercase
    return ("S" + rng.choice(letters) + rng.choice(letters)
            + "".join(rng.choice(string.digits) for _ in range(4)) + rng.choice(letters))


def degrade(plate, level, rng=None):
    """Simulate plate visibility: 'clear' | 'partial' | 'blurred' | 'hidden'."""
    rng = rng or random.Random(0)
    if level == "hidden" or not plate:
        return ""
    chars = list(plate)
    if level == "clear":
        if rng.random() < 0.1:                       # occasional single OCR slip
            i = rng.randrange(len(chars))
            chars[i] = rng.choice(CONFUSABLE.get(chars[i], chars[i]))
    elif level == "partial":                         # part of the plate not visible
        n_hidden = max(2, int(round(0.45 * len(chars))))
        start = rng.randrange(0, len(chars) - n_hidden + 1)
        for i in range(start, start + n_hidden):
            chars[i] = "?"
    elif level == "blurred":                         # heavy OCR confusion / dropped chars
        for i in range(len(chars)):
            if rng.random() < 0.45:
                chars[i] = rng.choice(CONFUSABLE.get(chars[i], string.ascii_uppercase + string.digits))
        if rng.random() < 0.5:
            del chars[rng.randrange(len(chars))]
    return "".join(chars)
