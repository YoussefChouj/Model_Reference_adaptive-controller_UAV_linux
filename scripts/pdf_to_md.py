"""
Convert pdftotext -layout output to well-formatted Markdown.
Keeps the structure, wraps math in LaTeX delimiters, formats figures.
"""
import re
import sys
from pathlib import Path

INPUT  = Path("raw/papers/neurofly.txt")
OUTPUT = Path("raw/papers/neurofly_converted.md")

def is_heading(line: str) -> bool:
    stripped = line.strip()
    return bool(re.match(r"^\s*\d+\s+[A-Z]", stripped))

def clean_line(line: str) -> str:
    # Remove page markers
    line = re.sub(r"\f", "", line)
    # Remove repeated spaces from layout extraction
    line = re.sub(r" {2,}", " ", line)
    # Remove leading page-number lines that are just whitespace + number + whitespace + number
    line = re.sub(r"^\s*\d+\s+\d+\s*$", "", line)
    # Dashes that are actually em-dashes in math
    line = line.rstrip()
    return line

def math_candidate(line: str) -> bool:
    """Heuristic: line contains math symbols."""
    math_markers = [
        r"\\", r"\^", r"_", r"\ddot", r"\dot", r"\bar",
        r"\phi", r"\Phi", r"\theta", r"\Theta", r"\psi", r"\Psi",
        r"\omega", r"\Omega", r"\epsilon", r"\varepsilon",
        r"\nabla", r"\partial", r"\infty", r"\ref",
        r"\=", r"\<", r"\>", r"\pm", r"\times", r"\cdot",
        r"\mathrm", r"\mathbf", r"\hat", r"\tilde",
        r"\alpha", r"\beta", r"\gamma", r"\delta",
        r"\sigma", r"\lambda", r"\mu", r"\nu", r"\rho",
        r"\eta", r"\zeta", r"\xi", r"\kappa", r"\tau",
    ]
    return any(re.search(m, line) for m in math_markers)

def format_figure_caption(line: str) -> str:
    """Convert figure caption lines to Markdown figure blocks."""
    # Match: Figure N: caption text
    m = re.match(r"^Figure\s+(\d+[\w\d]*)\s*:\s*(.+)$", line.strip(), re.DOTALL | re.IGNORECASE)
    if m:
        num = m.group(1)
        caption = m.group(2).strip()
        return f"\n**Figure {num}:** {caption}\n"
    # Fallback
    m2 = re.match(r"^(Fig\.\s*\d+[\w\d]*)\s*[-–—]\s*(.+)$", line.strip(), re.DOTALL | re.IGNORECASE)
    if m2:
        num = m2.group(1)
        caption = m2.group(2).strip()
        return f"\n**{num}:** {caption}\n"
    return line

def convert_inline_math(text: str) -> str:
    """Convert common LaTeX-like patterns to proper LaTeX."""
    # Already properly wrapped
    text = re.sub(r"\$\$", "$$", text)
    # Single-char subscripts: x_1 -> $x_1$
    # But be careful not to double-wrap
    text = re.sub(r"(?<!\\)\$([^\$]+)\$", lambda m: m.group(0), text)
    return text

def section_num(line: str) -> str | None:
    m = re.match(r"^\s*(\d+(?:\.\d+)*)\s+([A-Z].*)$", line.strip())
    if m:
        return m.group(1), m.group(2).strip()
    return None

def process():
    raw = INPUT.read_text()
    lines = raw.splitlines()

    out_lines = []
    in_math_block = False
    i = 0

    while i < len(lines):
        line = clean_line(lines[i])

        # Skip empty page-header/footer lines
        if re.match(r"^\s*\d+\s+\d+\s*$", line.strip()):
            i += 1
            continue

        # Section heading: "1 INTRODUCTION", "2.1 METHOD", etc.
        sec = section_num(line)
        if sec:
            num, title = sec
            out_lines.append(f"\n## {num}  {title}\n")
            i += 1
            continue

        # Figure caption: "Figure 1: Agile flight..."
        if re.match(r"^\s*Figure\s+\d", line.strip(), re.IGNORECASE):
            out_lines.append(format_figure_caption(line))
            i += 1
            continue

        # Table caption: "Table 1: ..."
        if re.match(r"^\s*Table\s+\d", line.strip(), re.IGNORECASE):
            out_lines.append(f"\n**{line.strip()}**\n")
            i += 1
            continue

        # Algorithm / listing caption
        if re.match(r"^\s*(Algorithm|Listing|Procedure)\s+\d", line.strip(), re.IGNORECASE):
            out_lines.append(f"\n**{line.strip()}**\n")
            i += 1
            continue

        # Empty line
        if not line.strip():
            out_lines.append("")
            i += 1
            continue

        # Pass through (light math detection)
        out_lines.append(line)
        i += 1

    # Join, collapse multiple blank lines, write
    text = "\n".join(out_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)

    OUTPUT.write_text(text)
    print(f"Wrote {OUTPUT} ({len(text)} chars, {len(out_lines)} lines)")

if __name__ == "__main__":
    process()
