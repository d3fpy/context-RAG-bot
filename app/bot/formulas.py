import re

from .config import MAX_LEN

SUPER = {"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "-": "⁻", "+": "⁺"}
SUB = {"0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉", "-": "₋"}

SYMBOLS = {
    "\\neq": "≠", "\\leq": "≤", "\\le": "≤", "\\geq": "≥", "\\ge": "≥",
    "\\cdot": "·", "\\times": "×", "\\div": "÷", "\\pm": "±",
    "\\infty": "∞", "\\approx": "≈", "\\equiv": "≡",
    "\\alpha": "α", "\\beta": "β", "\\gamma": "γ", "\\pi": "π", "\\lambda": "λ",
    "\\sqrt": "√", "\\angle": "∠", "\\triangle": "△", "\\circ": "°",
    "\\perp": "⊥", "\\parallel": "∥", "\\in": "∈", "\\notin": "∉",
    "\\rightarrow": "→", "\\to": "→", "\\cup": "∪", "\\cap": "∩",

    "/g153": "¬",
    "/g155": "∨",
    "/g156": "∧",
    "/g157": "→",
    "/g158": "↔",
    "/g159": "≡",
    "/g160": "≠",
    "/g161": "≤",
    "/g162": "≥",
    "/g163": "∞",
    "/g164": "√",
    "/g165": "∑",
    "/g166": "∏",
    "/g167": "∫",
    "/g168": "∈",
    "/g169": "∉",
    "/g170": "⊂",
    "/g171": "⊃",
    "/g172": "∪",
    "/g173": "∩",
    "/g174": "∅",
    "/g175": "∀",
    "/g176": "∃",
    "/g177": "∄",
    "/g178": "∴",
    "/g179": "∵",
    "/g180": "∠",
    "/g181": "⊥",
    "/g182": "∥",
    "/g183": "△",
    "/g184": "□",
    "/g185": "○",
    "/g186": "⊕",
    "/g187": "⊗",
    "/g188": "≈",
    "/g189": "∼",
    "/g190": "≅",
    "/g191": "≃",
    "/g192": "∝",
    "/g193": "∂",
    "/g194": "∇",
    "/g195": "°",
    "/g196": "′",
    "/g197": "″",
    "/g198": "‴",
    "/g199": "⁗",
    "/g200": "№",
}

def _sup(s):
    return "".join(SUPER.get(ch, ch) for ch in s)


def _sub(s):
    return "".join(SUB.get(ch, ch) for ch in s)


def clean_formulas(text: str) -> str:
    text = re.sub(r'[\u4e00-\u9fff\u3040-\u30ff]+', '', text)
    
    text = text.replace("\\(", "").replace("\\)", "")
    text = text.replace("\\[", "").replace("\\]", "")
    text = text.replace("$", "")

    for _ in range(3):
        new = re.sub(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"(\1)/(\2)", text)
        new = re.sub(r"\\sqrt\s*\{([^{}]+)\}", r"√(\1)", new)
        if new == text:
            break
        text = new

    for latex, symbol in sorted(SYMBOLS.items(), key=lambda kv: -len(kv[0])):
        text = text.replace(latex, symbol)

    text = re.sub(r"\^\{([^{}]+)\}", lambda m: _sup(m.group(1)), text)
    text = re.sub(r"\^(\d+|[-+])", lambda m: _sup(m.group(1)), text)
    text = re.sub(r"_\{([^{}]+)\}", lambda m: _sub(m.group(1)), text)
    text = re.sub(r"_(\d+|[-+])", lambda m: _sub(m.group(1)), text)

    text = re.sub(r"[{}]", "", text)
    text = re.sub(r" +", " ", text).strip()
    
    return text


def split_message(text: str) -> list[str]:
    if len(text) <= MAX_LEN:
        return [text]
    parts = []
    while text:
        chunk = text[:MAX_LEN]
        cut = max(chunk.rfind("\n\n"), chunk.rfind("\n"), chunk.rfind(". "), chunk.rfind(" "))
        if cut < MAX_LEN // 2:
            cut = MAX_LEN
        parts.append(text[:cut].strip())
        text = text[cut:].strip()
    return parts
