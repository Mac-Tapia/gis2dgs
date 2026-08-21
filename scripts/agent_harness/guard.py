from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Permission = Literal["allow", "ask", "deny"]


@dataclass(frozen=True)
class ShellDecision:
    permission: Permission
    reason: str


# Deterministic sensors: block or ask before dangerous shell actions.
_DENY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\bgit\s+push\b.*(--force|-f)\b", re.I),
        "Force-push is blocked by the agent harness.",
    ),
    (
        re.compile(r"\bgit\s+reset\s+--hard\b", re.I),
        "git reset --hard is blocked by the agent harness.",
    ),
    (
        re.compile(r"\bgit\s+clean\s+-[a-z]*f", re.I),
        "git clean -f is blocked by the agent harness.",
    ),
    (
        re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+.*-r|--recursive.*-f|-rf|-fr)\b", re.I),
        "Recursive force delete (rm -rf) is blocked by the agent harness.",
    ),
    (
        re.compile(
            r"\bRemove-Item\b.*(-Recurse|-r).*(-Force|-f)|"
            r"\bRemove-Item\b.*(-Force|-f).*(-Recurse|-r)",
            re.I,
        ),
        "Recursive force Remove-Item is blocked by the agent harness.",
    ),
    (
        re.compile(r"\b(DROP\s+(TABLE|DATABASE|SCHEMA)|TRUNCATE\s+TABLE)\b", re.I),
        "Destructive SQL DDL is blocked by the agent harness.",
    ),
    (
        re.compile(
            r"(?:\brm\b|\bdel\b|\berase\b|\bRemove-Item\b|\bMove-Item\b|"
            r"\bSet-Content\b|\bOut-File\b|\bCopy-Item\b).*"
            r"data[/\\]reference[/\\]real|"
            r"data[/\\]reference[/\\]real.*"
            r"(?:\brm\b|\bdel\b|\bRemove-Item\b|\bSet-Content\b|\bOut-File\b|\b>\b)",
            re.I,
        ),
        "Mutating real reference files under data/reference/real is blocked.",
    ),
    (
        re.compile(r"\bFormat-Volume\b|\bformat\s+[A-Za-z]:", re.I),
        "Disk format commands are blocked by the agent harness.",
    ),
]

_ASK_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\bgit\s+push\b", re.I),
        "git push requires explicit user confirmation.",
    ),
    (
        re.compile(r"\bgit\s+commit\b", re.I),
        "git commit requires explicit user confirmation.",
    ),
    (
        re.compile(r"\bdocker\s+(compose\s+)?(down|rm)\b", re.I),
        "Docker teardown may destroy local state; confirm with the user.",
    ),
]


def classify_shell_command(command: str) -> ShellDecision:
    text = (command or "").strip()
    if not text:
        return ShellDecision("allow", "empty command")

    for pattern, reason in _DENY_PATTERNS:
        if pattern.search(text):
            return ShellDecision("deny", reason)

    for pattern, reason in _ASK_PATTERNS:
        if pattern.search(text):
            return ShellDecision("ask", reason)

    return ShellDecision("allow", "ok")
