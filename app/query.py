"""Question normalisation and the entities an answer has to be about.

Two things go wrong between what a student types and what the corpus says.

They abbreviate. "ME", "AIML" and "KT" carry no signal for either retriever: BM25
tokenises "M.E." to "m" and "e", and a two-letter token embeds to nothing useful.
Expanding the abbreviation into the wording the documents actually use fixes both
retrievers and the cross-encoder at once.

They paraphrase. "my answer sheet was marked badly, can it be checked again" is the
revaluation procedure, but it shares no content word with it. A small glossary of the
college's own vocabulary closes that gap.

Expansion alone still lets a question about one programme be answered from the section
about another, so the entities in the question are also returned and used to order and
to gate the answer.
"""
import re

# Ambiguous outside their own capitalisation: "me" is a pronoun far more often than it
# is a master's degree, so these are expanded only when the student wrote them in caps.
CASED_ABBREVIATIONS = {
    "ME": "M.E. master of engineering postgraduate",
    "BE": "B.E. bachelor of engineering undergraduate",
    "PG": "postgraduate M.E.",
    "UG": "undergraduate B.E.",
    "TE": "third year",
    "SE": "second year",
    "BTECH": "B.E. bachelor of engineering undergraduate",
    "MTECH": "M.E. master of engineering postgraduate",
}

# Unambiguous: expanded wherever they appear.
ABBREVIATIONS = {
    "aiml": "artificial intelligence and machine learning",
    "ai": "artificial intelligence",
    "ml": "machine learning",
    "nlp": "natural language processing",
    "cs": "computer science",
    "it": "information technology",
    "kt": "KT keep term backlog examination",
    "phd": "Ph.D. doctoral research scholar",
    "ebc": "economically backward class",
    "cet": "common entrance test",
    "gate": "GATE score postgraduate",
    "tnp": "training and placement",
    "id": "identity card",
    "hod": "head of department",
    "hsc": "higher secondary examination undergraduate admission",
}

# What students type on the left, the college's own vocabulary on the right. Every entry
# here earns its place by fixing a question the corpus answers but retrieval missed;
# adding terms speculatively pulls off-topic questions over the refusal threshold.
GLOSSARY = (
    ("answer sheet", "answer book"),
    ("answer paper", "answer book"),
    ("answer script", "answer book"),
    ("marked badly", "revaluation of the answer book"),
    ("marked wrongly", "revaluation of the answer book"),
    ("marked unfairly", "revaluation of the answer book"),
    ("checked again", "revaluation photocopy of the answer book"),
    ("check it again", "revaluation photocopy of the answer book"),
    ("rechecked", "revaluation of the answer book"),
    ("rechecking", "revaluation of the answer book"),
    ("recheck", "revaluation of the answer book"),
    ("remarking", "revaluation of the answer book"),
    ("re-evaluation", "revaluation"),
    ("bunked", "attendance shortage detention"),
    ("bunking", "attendance shortage detention"),
    ("missed lectures", "attendance shortage detention"),
    ("short of attendance", "attendance shortage detention"),
    ("seats", "intake seats"),
    ("get a room", "hostel room allotment"),
    ("need a room", "hostel room allotment"),
    ("stay far", "hostel allotment distance from home"),
    ("live far", "hostel allotment distance from home"),
    ("mess bill", "mess charges per month"),
    ("backlog subjects", "KT subjects registration"),
    ("duplicate identity card", "replacement for lost identity card"),
    ("curfew", "hostel entry closes"),
)

WORD_RE = re.compile(r"[A-Za-z][A-Za-z.]*")

# Programme level. A question about one must not be answered from the other.
PROGRAMME_TERMS = {
    "ug": ("b.e.", "b.e", "be programme", "bachelor of engineering", "undergraduate",
           "first year", "second year", "third year", "final year", "diploma", "b.tech"),
    "pg": ("m.e.", "m.e", "me programme", "master of engineering", "postgraduate",
           "m.tech", "gate"),
    "phd": ("ph.d.", "ph.d", "phd", "doctoral", "research scholar"),
}

# Institutions other than this one. A policy from this corpus is not an answer about them.
NAME_STOP_WORDS = ("a|an|the|this|that|our|your|my|another|other|what|which|how|when|where|"
                   "is|are|does|do|can|at|in|for|from|of|and|about|say|says|run|runs|"
                   "fee|fees|syllabus|course|courses|admission|admissions|hostel|rules")
NAME_WORD = rf"(?!(?:{NAME_STOP_WORDS})\b)[a-z][a-z.'-]*"
NAME = rf"{NAME_WORD}(?:\s+{NAME_WORD}){{0,3}}"
INSTITUTION_TYPE = r"(?:University|College|Institute|Polytechnic|Vidyapeeth|Vishwavidyalaya)"
INSTITUTION_RE = re.compile(
    rf"\b(?:Oxford|Harvard|Stanford|Cambridge|Yale|Princeton)\b(?:\s+University|\s+College)?"
    rf"|\b(?:IIT|NIT|IIIT|IIM|BITS|VJTI|COEP|SPIT|NMIMS|DTU|VIT|SRM|MIT)\b(?:\s+{NAME_WORD})?"
    rf"|\b{NAME}\s+{INSTITUTION_TYPE}\b(?:\s+of\s+{NAME}(?:\s+(?:and|&)\s+{NAME})?)?"
    rf"|\b{INSTITUTION_TYPE}\s+of\s+{NAME}(?:\s+(?:and|&)\s+{NAME})?",
    re.I,
)

# What this college calls itself, so its own name never reads as somebody else's.
OWN_NAMES = ("institute of engineering and technology", "campusquery")


def expand(question: str) -> str:
    """The question plus the college's own wording for what it says. The original text
    is kept first so nothing the student wrote is lost."""
    additions = []

    for token in WORD_RE.findall(question):
        bare = token.strip(".").upper()
        if bare in CASED_ABBREVIATIONS and token.strip(".").isupper():
            additions.append(CASED_ABBREVIATIONS[bare])
        elif bare.lower() in ABBREVIATIONS and bare.lower() not in ("it", "ai", "ml", "id"):
            additions.append(ABBREVIATIONS[bare.lower()])
        elif token.isupper() and bare.lower() in ABBREVIATIONS:
            additions.append(ABBREVIATIONS[bare.lower()])

    lowered = question.lower()
    for phrase, official in GLOSSARY:
        if phrase in lowered and official not in lowered:
            additions.append(official)

    if not additions:
        return question
    return f"{question} {' '.join(dict.fromkeys(additions))}"


def programme(text: str):
    """Which programme level the text is about, or None when it does not say."""
    lowered = f" {text.lower()} "
    hits = {level for level, terms in PROGRAMME_TERMS.items()
            if any(term in lowered for term in terms)}
    return hits


def institutions(question: str):
    """Named institutions in the question that are not this college."""
    found = []
    for match in INSTITUTION_RE.finditer(question):
        name = re.sub(r"\s+", " ", match.group(0)).strip()
        if normalise_name(name) in OWN_NAMES:
            continue
        found.append(name)
    return found


def entities(question: str) -> dict:
    """Programme level is read from the expanded text, because "ME" only names a
    programme once it has been expanded. Institutions are read from what the student
    actually wrote, so an expansion can never invent one."""
    return {"programme": programme(expand(question)), "institution": institutions(question)}


def programme_alignment(text: str, asked) -> int:
    """+1 when the passage is about the programme asked for, -1 when it is explicitly
    about a different one, 0 when it does not commit either way."""
    if not asked:
        return 0
    found = programme(text)
    if not found:
        return 0
    if found & asked:
        return 1
    return -1


def mentions(text: str, name: str) -> bool:
    """Match whole name tokens: MIT must not match 'admitted'."""
    return f" {normalise_name(name)} " in f" {normalise_name(text)} "


def normalise_name(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower().replace("&", " and ")))


def semesters(text: str) -> set[int]:
    roman = {name: n for n, name in enumerate(
        ("i", "ii", "iii", "iv", "v", "vi", "vii", "viii"), 1)}
    found = re.findall(r"\bsemester\s+(viii|vii|vi|iv|iii|ii|v|i|[1-8])\b", text.lower())
    return {roman[token] if token in roman else int(token) for token in found}


OFFICE_RE = re.compile(r"\b(principal|director|registrar|librarian|dean)\b", re.I)
PERSON_NAME_RE = re.compile(
    r"\b(?:(?:Dr|Prof|Mr|Mrs|Ms)\.\s+)?"
    r"[A-Z][a-z]+(?:[-'][A-Za-z]+)*(?:\s+(?:[A-Z]\.\s*)?[A-Z][a-z]+(?:[-'][A-Za-z]+)*)+\b")
NON_PERSON_WORDS = {"the", "institute", "university", "college", "department", "principal",
                    "director", "registrar", "librarian", "dean", "engineering", "technology",
                    "admission", "admissions", "governing", "body"}


def requested_detail(question: str):
    """Narrow identity and numeric score requests need more than topical evidence."""
    office = OFFICE_RE.search(question)
    if office and (re.search(r"\bwho\s+(?:is|was)\b", question, re.I)
                   or re.search(r"\bname\b", question, re.I)):
        return "person", office.group(1).lower()
    if (re.search(r"\b(?:minimum|cut[ -]?off|at least)\b", question, re.I)
            and re.search(r"\b(?:score|marks)\b", question, re.I)):
        exam = re.search(r"\b(?:GATE|CET|JEE|NEET|CAT|GRE|GMAT)\b", question, re.I)
        if exam:
            return "exam-score", exam.group().lower()
    return None


def supports_detail(question: str, text: str) -> bool:
    detail = requested_detail(question)
    if not detail:
        return True
    kind, subject = detail
    if not re.search(rf"\b{re.escape(subject)}\b", text, re.I):
        return False
    if kind == "person":
        # A role definition or an institution name is not the name of its holder.
        for match in PERSON_NAME_RE.finditer(text):
            words = set(normalise_name(match.group()).split()) - {"dr", "prof", "mr", "mrs", "ms"}
            if len(words) >= 2 and not words & NON_PERSON_WORDS:
                return True
        return False
    # Require a number attached to the named examination/score, not a year or
    # an undergraduate percentage elsewhere in an admissions passage.
    exam = re.escape(subject)
    return bool(re.search(
        rf"\b{exam}\s+(?:(?:qualifying|minimum|cut[ -]?off)\s+)?(?:score|marks|cut[ -]?off)"
        r"\s*(?:(?:is|of|must be|should be|at least|minimum|above|greater than)\s*)*[:=]?\s*\d+(?:\.\d+)?\b"
        rf"|\b(?:score|marks)\s+(?:of\s+|at least\s+)?\d+(?:\.\d+)?\s+(?:in|on)\s+(?:the\s+)?{exam}\b",
        text, re.I))
