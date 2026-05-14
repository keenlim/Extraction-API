from __future__ import annotations

import re


FENCE_LINE_REGEX = re.compile(r"^(?P<indent>[ \t]*)(?P<fence>`{3,}|~{3,})(?P<info>[^\n]*)$")


def sanitize_markdown_output(markdown: str) -> str:
    if not markdown:
        return markdown

    lines = markdown.splitlines()
    open_stack: list[tuple[int, str, int]] = []
    for index, line in enumerate(lines):
        match = FENCE_LINE_REGEX.match(line)
        if not match:
            continue
        fence = match.group("fence")
        fence_char = fence[0]
        fence_length = len(fence)
        if open_stack and open_stack[-1][1] == fence_char and fence_length >= open_stack[-1][2]:
            open_stack.pop()
        else:
            open_stack.append((index, fence_char, fence_length))

    unmatched_indices = {index for index, _, _ in open_stack}
    sanitized_lines: list[str] = []
    for index, line in enumerate(lines):
        if index in unmatched_indices and _is_probable_artifact_fence_line(line):
            continue
        if index in unmatched_indices:
            sanitized_lines.append(_escape_fence_line(line))
        else:
            sanitized_lines.append(line)

    sanitized = "\n".join(sanitized_lines)
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized).rstrip()
    if sanitized and markdown.endswith("\n"):
        return sanitized + "\n"
    return sanitized


def _escape_fence_line(line: str) -> str:
    match = FENCE_LINE_REGEX.match(line)
    if not match:
        return line
    indent = match.group("indent") or ""
    fence = match.group("fence") or ""
    info = match.group("info") or ""
    return f"{indent}\\{fence}{info}"


def _is_probable_artifact_fence_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if re.fullmatch(r"`{6,}", stripped):
        return True
    if re.fullmatch(r"~{6,}", stripped):
        return True
    return False
