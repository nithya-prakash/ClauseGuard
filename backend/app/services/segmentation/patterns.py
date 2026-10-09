import re

# Each pattern matches at the START of a (already-normalized, single) line
# and captures the clause/section label in group 1. Order matters: more
# specific patterns are tried first. These are heuristics tuned for German
# contracts, not a full parser - see segmenter.py module docstring for known
# limitations.
CLAUSE_START_PATTERNS: list[re.Pattern[str]] = [
    # "§ 3", "§3a"
    re.compile(r"^(§\s*\d+[a-zA-Z]?)\b"),
    # "Art. 5", "Artikel 12"
    re.compile(r"^(Art(?:ikel)?\.?\s*\d+[a-zA-Z]?)\b"),
    # "Ziffer 4"
    re.compile(r"^(Ziffer\s+\d+[a-zA-Z]?)\b"),
    # "(1)", "(2a)" - parenthesized sub-clause at line start
    re.compile(r"^(\(\d+[a-zA-Z]?\))\s"),
    # "1.", "1.1", "3.2.1" numbered clause/sub-clause, followed by a space
    # A number followed by a unit word ("50 Prozent", "14 Tage") is a quantity on a wrapped line,
    # not a heading.
    re.compile(
        r"^(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+"
        r"(?!(?:Prozent|%|EUR|Euro|Tage|Tagen|Werktage|Werktagen|Wochen|Monate|Monaten|Jahre|"
        r"Jahren|Stunden)\b)\S"
    ),
]

# A line consisting only of a clause label with no trailing heading text
# still counts as a boundary; heading is then taken from the label match
# itself with nothing appended.
BULLET_LINE = re.compile(r"^[-•*]\s")
