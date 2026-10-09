import difflib
import re


def strip_line_numbers(text: str) -> str:
    """Remove `cat -n` style prefixes if every line has one (consecutive numbers)."""
    lines = text.split("\n")
    nums = []
    for ln in lines:
        m = re.match(r"^\s*(\d+)(?:\t| |$)", ln)
        if not m:
            return text
        nums.append(int(m.group(1)))
    if all(b == a + 1 for a, b in zip(nums, nums[1:])):
        return "\n".join(re.sub(r"^\s*\d+(?:\t| )?", "", ln, count=1) for ln in lines)
    return text


def apply_edit(src: str, old: str, new: str):
    """Returns (new_src, note) on success or (None, error_message)."""
    src = src.replace("\r\n", "\n")
    old = old.replace("\r\n", "\n")
    new = new.replace("\r\n", "\n")

    for o, n in ((old, new), (strip_line_numbers(old), strip_line_numbers(new))):
        c = src.count(o) if o else 0
        if c == 1:
            return src.replace(o, n, 1), "exact match"
        if c > 1:
            return None, f"'old' matches {c} places; include more surrounding lines."

    old_l = [l.strip() for l in strip_line_numbers(old).split("\n")]
    while old_l and not old_l[0]:
        old_l.pop(0)
    while old_l and not old_l[-1]:
        old_l.pop()
    if not old_l:
        return None, "'old' is empty."

    src_l = src.split("\n")
    hits = [i for i in range(len(src_l) - len(old_l) + 1)
            if [x.strip() for x in src_l[i:i + len(old_l)]] == old_l]
    if len(hits) == 1:
        i = hits[0]
        new_l = strip_line_numbers(new).split("\n")
        base = len(src_l[i]) - len(src_l[i].lstrip())
        first = next((l for l in new_l if l.strip()), "")
        delta = base - (len(first) - len(first.lstrip()))

        def fix(l):
            if not l.strip():
                return l
            if delta >= 0:
                return " " * delta + l
            return l[min(-delta, len(l) - len(l.lstrip())):]

        out = src_l[:i] + [fix(l) for l in new_l] + src_l[i + len(old_l):]
        return "\n".join(out), "whitespace-tolerant match"
    if len(hits) > 1:
        return None, "'old' matches several places ignoring whitespace; include more lines."

    stripped = [l.strip() for l in src_l]
    close = difflib.get_close_matches(old_l[0], stripped, n=1, cutoff=0.6)
    if close:
        i = stripped.index(close[0])
        ctx = "\n".join(f"{j + 1}\t{src_l[j]}" for j in range(max(0, i - 2), min(len(src_l), i + 6)))
        return None, ("'old' not found. Closest region of the file:\n" + ctx +
                      "\nCopy the text exactly, or use replace_lines.")
    return None, "'old' not found. Re-read that part of the file, or use replace_lines."


def replace_lines(src: str, start: int, end: int, new: str):
    lines = src.replace("\r\n", "\n").split("\n")
    if not (1 <= start <= end <= len(lines)):
        return None, f"invalid line range; the file has {len(lines)} lines."
    new = new.replace("\r\n", "\n")
    new_l = strip_line_numbers(new).split("\n") if new != "" else []
    return "\n".join(lines[:start - 1] + new_l + lines[end:]), f"replaced lines {start}-{end}"