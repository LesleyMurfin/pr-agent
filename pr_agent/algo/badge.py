"""Badge formatting and parsing utilities for PR review findings and suggestions."""

import re
from typing import Any, Dict, List, Optional, Tuple

RISK_HIGH = "🔴 high"
RISK_MAJOR = "🟠 major"
RISK_MODERATE = "🟡 moderate"
RISK_TRIVIAL = "🔵 trivial"

PILLAR_SECURITY = "🔒 security"
PILLAR_PRIVACY = "👁 privacy"
PILLAR_CONSENT = "✋ consent"
PILLAR_RELIABILITY = "🛡 reliability"
PILLAR_OTHER = "📦 other"

DEFAULT_RISK = RISK_MODERATE
DEFAULT_PILLAR = PILLAR_OTHER
DEFAULT_IMPACT = "📁 unspecified"

# Matches a line that is already a badge: e.g. `_🟡 moderate_ | _📦 other_ | _📁 unspecified_`
BADGE_LINE_RE = re.compile(
    r"^\s*_[^_\n]+_\s*\|\s*_[^_\n]+_\s*\|\s*_[^_\n]+_\s*$"
)

# Pillar keyword patterns (case-insensitive)
SECURITY_KEYWORDS = re.compile(
    r"\b(security|vulnerabilit(y|ies)|exploit|injection|xss|csrf|cve|rce|auth|token|credential|secret|permission|overflow|sanitize)\b",
    re.IGNORECASE
)
PRIVACY_KEYWORDS = re.compile(
    r"\b(privacy|pii|gdpr|ccpa|anonymiz|pseudonymiz|personal\s+data|sensitive\s+data)\b",
    re.IGNORECASE
)
CONSENT_KEYWORDS = re.compile(
    r"\b(consent|opt-in|opt-out|terms\s+of\s+service|cookie\s+banner|gdpr\s+consent)\b",
    re.IGNORECASE
)
RELIABILITY_KEYWORDS = re.compile(
    r"\b(reliab|error|exception|crash|leak|handle|timeout|retry|retries|fail|deadlock|race\s+condition|concurren|thread|memory|drain|robust|telemetry|logging|metrics|test|flake|hang|infinite\s+loop|null\s*pointer|none\s*type|panic)\b",
    re.IGNORECASE
)

# Risk keyword patterns
HIGH_RISK_KEYWORDS = re.compile(
    r"\b(critical|high|fatal|blocker|severe|rce|data\s+loss)\b",
    re.IGNORECASE
)
MAJOR_RISK_KEYWORDS = re.compile(
    r"\b(major|significant|broken|corrupt|deadlock)\b",
    re.IGNORECASE
)
TRIVIAL_RISK_KEYWORDS = re.compile(
    r"\b(trivial|nit|typo|comment|style|formatting|whitespace|naming|minor)\b",
    re.IGNORECASE
)

FLEET_IMPACT_KEYWORDS = re.compile(
    r"\b(fleet|prod|production|cluster|service\s+down|outage|all\s+hosts)\b",
    re.IGNORECASE
)
TEST_IMPACT_KEYWORDS = re.compile(
    r"\b(test|tests|ci|eval|mock|fixture|suite)\b",
    re.IGNORECASE
)


def has_badge(text: str) -> bool:
    """Check if the text already starts with a badge pattern on its first non-empty line."""
    if not text:
        return False
    lines = text.strip().splitlines()
    if not lines:
        return False
    first_line = lines[0].strip()
    return bool(BADGE_LINE_RE.match(first_line))


def parse_badge_line(line: str) -> Optional[Tuple[str, str, str]]:
    """Parse a badge line into (risk, pillar, impact) if matching."""
    line = line.strip()
    if not BADGE_LINE_RE.match(line):
        return None
    parts = [p.strip().strip("_").strip() for p in line.split("|")]
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    return None


def infer_pillar(text: str) -> str:
    """Infer pillar from text keywords, defaulting to '📦 other'."""
    if SECURITY_KEYWORDS.search(text):
        return PILLAR_SECURITY
    if PRIVACY_KEYWORDS.search(text):
        return PILLAR_PRIVACY
    if CONSENT_KEYWORDS.search(text):
        return PILLAR_CONSENT
    if RELIABILITY_KEYWORDS.search(text):
        return PILLAR_RELIABILITY
    return PILLAR_OTHER


def infer_risk(text: str, score: Optional[int] = None) -> str:
    """Infer risk from text keywords or score (1-10), defaulting to '🟡 moderate'."""
    if score is not None:
        try:
            score_val = int(score)
            if score_val >= 9:
                return RISK_HIGH
            if score_val >= 7:
                return RISK_MAJOR
            if score_val <= 3:
                return RISK_TRIVIAL
            return RISK_MODERATE
        except (TypeError, ValueError):
            pass

    if HIGH_RISK_KEYWORDS.search(text):
        return RISK_HIGH
    if MAJOR_RISK_KEYWORDS.search(text):
        return RISK_MAJOR
    if TRIVIAL_RISK_KEYWORDS.search(text):
        return RISK_TRIVIAL
    return RISK_MODERATE


def infer_impact(text: str, pillar: str) -> str:
    """Infer consequence + blast radius (💥 fleet/prod, 📁 this repo, 🧪 tests only). Never repeat pillar."""
    blast_radius = "📁"
    if FLEET_IMPACT_KEYWORDS.search(text):
        blast_radius = "💥"
    elif TEST_IMPACT_KEYWORDS.search(text):
        blast_radius = "🧪"

    if blast_radius == "💥":
        scope = "fleet/prod"
    elif blast_radius == "🧪":
        scope = "tests only"
    else:
        scope = "this repo"

    if "security" in pillar:
        consequence = "unhandled exploit exposure"
    elif "privacy" in pillar:
        consequence = "sensitive data exposure"
    elif "consent" in pillar:
        consequence = "unauthorized operation"
    elif "reliability" in pillar:
        if "leak" in text.lower():
            consequence = "resource leak"
        elif "crash" in text.lower() or "exception" in text.lower():
            consequence = "runtime failure"
        elif "timeout" in text.lower() or "hang" in text.lower():
            consequence = "operation timeout"
        elif "test" in text.lower():
            consequence = "test defect"
        else:
            consequence = "runtime instability"
    else:
        consequence = "unspecified"

    return f"{blast_radius} {consequence} ({scope})"


def create_badge(risk: Optional[str] = None,
                 pillar: Optional[str] = None,
                 impact: Optional[str] = None) -> str:
    """Generate a badge string: _<risk>_ | _<pillar>_ | _<impact>_"""
    r = risk or DEFAULT_RISK
    p = pillar or DEFAULT_PILLAR
    i = impact or DEFAULT_IMPACT
    return f"_{r}_ | _{p}_ | _{i}_"


def ensure_badge(text: str,
                 risk: Optional[str] = None,
                 pillar: Optional[str] = None,
                 impact: Optional[str] = None,
                 score: Optional[int] = None) -> str:
    """
    Ensure the first line of text is a badge.
    If text already starts with a badge pattern, returns unchanged.
    Otherwise parses text for keywords or uses defaults/overrides and prepends badge.
    """
    if not isinstance(text, str):
        text = str(text or "")
    stripped = text.strip()
    if has_badge(stripped):
        return text

    inferred_p = pillar or infer_pillar(stripped)
    inferred_r = risk or infer_risk(stripped, score=score)
    inferred_i = impact or infer_impact(stripped, inferred_p)

    badge = create_badge(inferred_r, inferred_p, inferred_i)
    if not stripped:
        return badge
    return f"{badge}\n\n{text}"


def build_summary_headers(data: dict, raw_markdown: str = "") -> str:
    """
    Build the required PR summary header block:
    ## Merge risk: …
    ## Pillars: …
    ## Impact: …
    """
    review = (data.get("review") or {}) if isinstance(data, dict) else {}
    risk_level = str(review.get("risk_level") or "").strip().lower()

    risk_rank = {
        "critical": (4, RISK_HIGH),
        "high": (4, RISK_HIGH),
        "major": (3, RISK_MAJOR),
        "medium": (2, RISK_MODERATE),
        "moderate": (2, RISK_MODERATE),
        "low": (1, RISK_TRIVIAL),
        "trivial": (1, RISK_TRIVIAL),
    }

    current_max_rank, max_risk_badge = risk_rank.get(risk_level, (2, DEFAULT_RISK))

    pillars_found = set()
    impacts_found = set()

    # Scan key issues
    key_issues = review.get("key_issues_to_review") or []
    if isinstance(key_issues, list):
        for issue in key_issues:
            if isinstance(issue, dict):
                content = f"{issue.get('issue_header', '')} {issue.get('issue_content', '')}"
                p = infer_pillar(content)
                pillars_found.add(p)
                r = infer_risk(content)
                rank = risk_rank.get(r.split()[1], (2, r))[0]
                if rank > current_max_rank:
                    current_max_rank = rank
                    max_risk_badge = r
                impacts_found.add(infer_impact(content, p))

    # Also check if raw_markdown has any badge lines
    for line in raw_markdown.splitlines():
        parsed = parse_badge_line(line)
        if parsed:
            r, p, imp = parsed
            pillars_found.add(p)
            impacts_found.add(imp)
            r_name = r.split()[-1] if " " in r else r
            rank = risk_rank.get(r_name, (2, r))[0]
            if rank > current_max_rank:
                current_max_rank = rank
                max_risk_badge = r

    if not pillars_found:
        pillars_found.add(DEFAULT_PILLAR)
    if not impacts_found:
        impacts_found.add(DEFAULT_IMPACT)

    pillars_str = " · ".join(sorted(pillars_found))
    impacts_str = " · ".join(sorted(impacts_found))

    header_block = (
        f"## Merge risk: {max_risk_badge}\n"
        f"## Pillars: {pillars_str}\n"
        f"## Impact: {impacts_str}\n\n"
    )
    return header_block
