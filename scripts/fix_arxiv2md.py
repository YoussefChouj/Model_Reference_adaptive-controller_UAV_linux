"""
Post-process arxiv2md output:
1. Collapse `$$ $\displaystyle ...$ $\displaystyle ...$ (N) $$` to clean display math.
2. Remove `fnum@@` prefix from headings and section refs.
3. Tighten inline `Figure:` labels.
"""
import re
from pathlib import Path

INPUT  = Path("raw/papers/neurofly_arxiv2md.md")
OUTPUT = Path("raw/papers/neurofly_arxiv2md.fixed.md")

def fix_display_math(text: str) -> str:
    """Collapse the double $ $displaystyle artifact into a single $$ block."""
    # Pattern: $$ $\displaystyle X$ $\displaystyle Y$ (N) $$  (single-line)
    pattern = re.compile(
        r"\$\$\s*\$\\displaystyle\s*(.+?)\$\s+\$\\displaystyle\s*(.+?)\$\s*\((\d+)\)\s*\$\$",
        re.DOTALL,
    )
    return pattern.sub(
        lambda m: f"$$\n\\displaystyle {m.group(1)} {m.group(2)} \\tag{{{m.group(3)}}}\n$$",
        text,
    )

def fix_headings(text: str) -> str:
    """Remove `fnum@@section` prefix from headings."""
    text = re.sub(r"^(#{1,6})\s*fnum@@section\s*", r"\1 ", text, flags=re.MULTILINE)
    text = re.sub(r"^(#{1,6})\s*fnum@@\s*", r"\1 ", text, flags=re.MULTILINE)
    return text

def fix_abstract_dupe(text: str) -> str:
    """Remove the leading 'Abstract Abstract' from the Abstract section."""
    text = re.sub(r"^## Abstract\s*\n\nAbstract ", "## Abstract\n\n", text, flags=re.MULTILINE)
    return text

def fix_xtitles(text: str) -> str:
    """Collapse `43.6 km / h 43.6\text{\,}\mathrm{k}\mathrm{m}\mathrm{/}\mathrm{h}` → `43.6 km/h`."""
    text = re.sub(r"(\d+(?:\.\d+)?)\s*(km|m|cm|mm)\s*/\s*(h|s|min)\s+\1\\text\\{\\,\\}\\mathrm\{(\w+)\}", r"\1\\text{\,}\\mathrm{\2/\\2}", text)
    return text

def fix_section_refs(text: str) -> str:
    """Fix `[fnum@@sectionN ...]` to `[Section N ...]`."""
    text = re.sub(r"\[fnum@@section(\d+(?:\.\w+)*)", r"[Section \1", text)
    return text

def fix_figure_links(text: str) -> str:
    """Tighten `Figure: Figure N: ...` to a single label."""
    text = re.sub(r"^Figure: Figure (\d+):", r"**Figure \1:**", text, flags=re.MULTILINE)
    return text

def main():
    text = INPUT.read_text()
    text = fix_display_math(text)
    text = fix_headings(text)
    text = fix_section_refs(text)
    text = fix_figure_links(text)
    text = fix_abstract_dupe(text)
    text = fix_xtitles(text)
    OUTPUT.write_text(text)
    print(f"Wrote {OUTPUT} ({len(text)} chars)")

if __name__ == "__main__":
    main()
