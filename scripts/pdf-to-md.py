#!/usr/bin/env python3
"""
pdf-to-md: Convert a PDF to Markdown using pdf-inspector (primary, fast, clean)
or CiroZhang/paper_reader (secondary, image extraction).

Usage:
    python scripts/pdf-to-md.py path/to/paper.pdf                    # pdf-inspector (default)
    python scripts/pdf-to-md.py path/to/paper.pdf --engine both     # pdf-inspector + images from paper-reader
    python scripts/pdf-to-md.py path/to/paper.pdf --engine paper-reader  # paper-reader only

Naming logic:
  1. If a matching *-briefing.md exists in raw/papers/ whose frontmatter sources:
       contains the same arXiv ID, use its filename prefix (FirstAuthor-Year-ShortTitle).
  2. Otherwise use the bare arXiv ID from the filename.
  3. Otherwise use the PDF stem.

Output lands in raw/papers/ as:
  <YYYY-MM-DD>-<FirstAuthor>-<Year>-<ShortTitle>-converted.md
  <YYYY-MM-DD>-<FirstAuthor>-<Year>-<ShortTitle>-converted-images/   (paper-reader only)
  <YYYY-MM-DD>-<FirstAuthor>-<Year>-<ShortTitle>-converted-raw.jsonl (paper-reader only)
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path


# ---------------------------------------------------------------------------
# pdf-inspector engine
# ---------------------------------------------------------------------------

def run_pdf_inspector(pdf_path: Path) -> tuple[str, dict]:
    """Extract markdown from a PDF using pdf-inspector (Rust, no OCR, ~200ms).

    Returns (markdown, info_dict).
    info_dict contains: pdf_type, page_count, pages_needing_ocr, processing_time_ms
    """
    import pdf_inspector

    t0 = time.time()
    result = pdf_inspector.process_pdf(str(pdf_path))
    elapsed = time.time() - t0

    if result.markdown is None:
        sys.stderr.write(
            f"pdf-inspector returned no markdown for {pdf_path.name} "
            f"(type={result.pdf_type}). Try --engine paper-reader.\n"
        )
        sys.exit(1)

    info = {
        "pdf_type": result.pdf_type,
        "page_count": result.page_count,
        "pages_needing_ocr": result.pages_needing_ocr,
        "confidence": result.confidence,
        "processing_time_s": round(elapsed, 3),
    }

    return result.markdown, info


def post_process_pdf_inspector_markdown(md_text: str) -> str:
    """Light post-processing for pdf-inspector output.

    - Skip author/affiliation/metadata block (lines between title H1 and first section)
    - Convert "**Abstract**" bold -> H2, merging its paragraphs (split by page breaks)
    - Remove per-page arXiv footer lines that appear mid-paragraph
    - Convert "**References**", "**Acknowledgements**" bold -> H2
    - Skip duplicate top-level section headings (e.g. "SUPPLEMENTARY MATERIALS" appears twice)
    """
    lines = md_text.splitlines()
    out: list[str] = []
    seen_headings: set[str] = set()
    past_front_matter = False
    i = 0

    while i < len(lines):
        raw = lines[i]
        s = raw.strip()
        i += 1

        # skip per-page arXiv footer lines
        if re.match(r"^# arXiv:\d+\.\d+v\d+", s):
            continue

        # title H1 (line 0)
        if s.startswith("## ") and not s.startswith("### ") and len(out) == 0:
            out.append(raw)
            continue

        # Abstract bold -> H2 (merge paragraphs, skip per-page footers)
        if s == "**Abstract**":
            out.append("## Abstract")
            parts: list[str] = []
            while i < len(lines):
                next_s = lines[i].strip()
                if not next_s:
                    i += 1
                    continue
                if next_s.startswith("### ") or next_s.startswith("!["):
                    break
                if re.match(r"^# arXiv:\d+\.\d+v\d+", next_s):
                    i += 1
                    continue
                parts.append(next_s)
                i += 1
            if parts:
                out.append(" ".join(parts))
            continue

        # bold References -> H2
        if s == "**References**":
            out.append("## References")
            continue

        # bold Acknowledgements (plain, no colon) -> H2
        # Must NOT match "**Acknowledgements:**" (section heading in supplementary)
        if re.match(r"^\*\*Acknowledgements\*\*$", s):
            out.append("## Acknowledgements")
            continue

        # first H3/H4 section heading: end of front matter
        if not past_front_matter and s.startswith("### "):
            past_front_matter = True

        # skip front matter: author/affiliation/DOI lines before first section
        if not past_front_matter:
            continue

        # skip duplicate top-level section headings (keep first occurrence)
        # Normalize to lowercase so "ACKNOWLEDGEMENTS" and "Acknowledgements" both dedup
        if s.startswith("### ") and not s.startswith("#### "):
            htxt_lower = s[4:].strip().lower()
            if htxt_lower in seen_headings:
                continue
            seen_headings.add(htxt_lower)

        out.append(raw)

    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# paper-reader engine
# ---------------------------------------------------------------------------

def _build_image_refs_from_jsonl(jsonl_path: Path, images_dir_name: str) -> dict[int, list[str]]:
    """Parse a paper_reader jsonl and build a mapping: page_index -> [image_markdown_line, ...].

    Page breaks are detected as y0 resets (large downward jump in y coordinate).
    For each picture element, looks up the nearest text element containing "Figure N:"
    or "Table N:" on the same page to get the correct label.
    """
    import json

    image_refs: dict[int, list[str]] = {}

    with open(jsonl_path) as f:
        elements: list[dict] = [json.loads(line) for line in f]

    if not elements:
        return image_refs

    # Detect page breaks: y0 jumps DOWN (from near top to near bottom of next page)
    # We use a threshold of 400 units for a 792-point-tall PDF page
    pages: list[list[dict]] = [[]]
    last_y0 = float("inf")
    for obj in elements:
        y0 = obj.get("y0", 0)
        if y0 < last_y0 - 400:
            pages.append([])
        pages[-1].append(obj)
        last_y0 = y0

    # Build image refs per page
    for page_idx, page_objs in enumerate(pages):
        page_img_refs: list[str] = []

        for obj in page_objs:
            if obj.get("class") == "picture" and obj.get("content", "").strip():
                pic_y0 = obj.get("y0", 0)
                caption = ""
                best_dist = float("inf")
                for other in page_objs:
                    if other.get("class") == "text":
                        text = other.get("content", "")
                        m = re.search(r"(Figure [A-Za-z0-9]+|Table [A-Za-z0-9]+):", text)
                        if m:
                            dist = abs(other.get("y0", 0) - pic_y0)
                            if dist < best_dist:
                                best_dist = dist
                                caption = m.group(1)
                filename = re.sub(r"^images/[^/]+/", "", obj.get("content", "").strip())
                label = caption if caption else f"Figure ({page_idx + 1})"
                page_img_refs.append(f"![{label}]({images_dir_name}/{filename})")

        if page_img_refs:
            image_refs[page_idx] = page_img_refs

    return image_refs


def run_paper_reader(
    pdf_path: Path,
    paper_reader_root: Path,
    images_dest: Path | None,
    jsonl_dest: Path | None,
) -> tuple[str, dict[int, list[str]]]:
    """Run CiroZhang/paper_reader on a PDF.

    Copies images/ and jsonl/ to the destination paths INSIDE the temp context
    (before cleanup), so callers can safely use the paths after the function returns.

    Returns (markdown_text, page_image_refs_dict).
    """
    venv_python = paper_reader_root / ".venv" / "bin" / "python"
    if not venv_python.exists():
        sys.stderr.write(
            f"ERROR: paper_reader venv not found at {venv_python}\n"
            f"  Run the setup steps in .cursor/skills/pdf-to-md/SKILL.md\n"
        )
        sys.exit(1)

    stem = pdf_path.stem

    with tempfile.TemporaryDirectory() as tmp_in, tempfile.TemporaryDirectory() as tmp_out:
        tmp_in_path = Path(tmp_in)
        tmp_out_path = Path(tmp_out)

        (tmp_in_path / f"{stem}.pdf").symlink_to(pdf_path)

        cmd = [
            str(venv_python), "main.py",
            str(tmp_in_path),
            str(tmp_out_path),
            "--save-raw-json",
            "--save-removed",
            "--no-auto-download",
        ]
        result = subprocess.run(cmd, cwd=paper_reader_root)
        if result.returncode != 0:
            sys.stderr.write(
                f"paper_reader failed with code {result.returncode}\n"
            )
            sys.exit(result.returncode)

        out_md = tmp_out_path / "outputs" / f"{stem}.md"
        out_images = tmp_out_path / "outputs" / "images" / stem
        out_jsonl = tmp_out_path / "raw_outputs" / f"{stem}.jsonl"

        if not out_md.exists():
            sys.stderr.write(
                f"ERROR: paper_reader produced no markdown output.\n"
                f"  Expected: {out_md}\n"
            )
            sys.exit(1)

        md_text = out_md.read_text()

        # Copy images inside the temp context (before cleanup)
        if images_dest is not None and out_images.exists():
            if images_dest.exists():
                shutil.rmtree(images_dest)
            shutil.copytree(out_images, images_dest)

        # Copy jsonl inside the temp context (before cleanup)
        page_image_refs: dict[int, list[str]] = {}
        if jsonl_dest is not None and out_jsonl.exists():
            shutil.copy2(out_jsonl, jsonl_dest)
            images_dir_name = images_dest.name if images_dest else f"{stem}-images"
            page_image_refs = _build_image_refs_from_jsonl(out_jsonl, images_dir_name)

    return md_text, page_image_refs


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def pdf_stem(path: Path) -> str:
    return path.stem


def parse_briefings(raw_papers: Path) -> dict[str, str]:
    """Scan all *-briefing.md files in raw_papers/ and build a mapping:
    arxiv_id -> <FirstAuthor>-<Year>-<ShortTitle>
    """
    mapping: dict[str, str] = {}
    if not raw_papers.is_dir():
        return mapping

    for bf in sorted(raw_papers.glob("*-briefing.md")):
        name = bf.name.replace("-briefing.md", "")
        parts = name.split("-", 3)
        if len(parts) < 4:
            continue
        author_year_title = "-".join(parts[3:])

        text = bf.read_text(errors="replace")
        for match in re.finditer(r"(?:arxiv|arXiv)[\s:]*(\d{4}\.\d{5})", text):
            mapping[match.group(1)] = author_year_title

    return mapping


def build_output_name(
    pdf_path: Path,
    stamp: str,
    briefing_map: dict[str, str],
) -> str:
    stem = pdf_stem(pdf_path)
    bare_stem = re.sub(r"^arxiv", "", stem, flags=re.IGNORECASE)
    arxiv_id_match = re.match(r"^(\d{4}\.\d{5})", bare_stem)

    if arxiv_id_match:
        arxiv_id = arxiv_id_match.group(1)
        if arxiv_id in briefing_map:
            return f"{stamp}-{briefing_map[arxiv_id]}"
        return f"{stamp}-{arxiv_id}"

    return f"{stamp}-{stem}"


# ---------------------------------------------------------------------------
# markdown post-processing (for paper-reader output)
# ---------------------------------------------------------------------------

# Known subsection titles - promoted to ### in paper-reader output
_SUBSECTION_TITLES: frozenset[str] = frozenset({
    "Experimental Platform", "UAV Design", "Wind Condition Design",
    "Offline Learning and Online Adaptive Control Development",
    "Data Collection and Meta-Learning using DAIML",
    "Baselines and the Variants of Our Method",
    "Trajectory Tracking Performance", "Agile Flight Through Narrow Gates",
    "Task Design", "Performance", "Outdoor Experiments",
    "State-of-the-art Tracking Performance",
    "Challenges Caused by Unknown and Time-varying Wind Conditions",
    "Computational Efficiency of Our Method",
    "Generalization to New Trajectories and New Aircraft",
    "Overview", "Data Collection",
    "Domain Adversarially Invariant Meta-Learning",
    "Design of the DAIML Algorithm",
    "Robust Adaptive Controller Design",
    "Nonlinear Control Law", "Composite Adaptation Law",
    "Stability and Robustness Guarantees", "Implementation Details",
    "Quadrotor Dynamics", "Neural Network Architectures", "Controller Implementation",
    "Gain Tuning", "Force Prediction Performance", "Localization Error Analysis",
    "Relation between Neural-Fly and Conventional Adaptive Control",
    "Related Work for Precise Quadrotor Control",
    "Related Work in Multi-environment Deep Learning for Robot Control",
    "Results", "Discussion",
    "Section S1", "Section S2", "Section S3", "Section S4",
    "Section S5", "Section S6", "Section S7", "Section S8",
})


def _strip_artefacts(text: str) -> str:
    """Strip trailing PDF artefacts (column-break l, li, i suffixes)."""
    ARTEFACT_SUFFIX_RE = re.compile(r"\s+[lLiI]+\s*$")
    ARTEFACT_PREFIX_RE = re.compile(r"^\s+[a-z]\s+(?=[A-Z])")
    text = ARTEFACT_SUFFIX_RE.sub("", text)
    text = ARTEFACT_PREFIX_RE.sub("", text)
    return text


def post_process_paper_reader_markdown(md_text: str) -> str:
    """Clean paper_reader markdown.

    - Fix image paths to use the images dir name
    - Remove duplicate ## headings (paper_reader extracts titles twice)
    - Remove orphan paragraphs after skipped duplicate headings
    - Promote known subsection titles to ###
    - Strip trailing PDF artefacts
    - Strip leading/trailing blank lines
    - Collapse excessive blank lines

    pdf-inspector output does NOT need post-processing (already clean).
    """
    raw_lines = md_text.splitlines()

    # Step 1: split into typed blocks
    blocks: list[tuple[str, str]] = []

    i = 0
    while i < len(raw_lines):
        line = raw_lines[i]
        stripped = line.strip()

        if stripped.startswith("!["):
            blocks.append(("image", stripped))
        elif stripped.startswith("## ") and stripped[3].isupper():
            blocks.append(("heading", stripped))
        elif stripped in _SUBSECTION_TITLES:
            blocks.append(("subsection", stripped))
        else:
            blocks.append(("text", stripped))

        i += 1

    out_blocks: list[tuple[str, str]] = []
    pending_text: list[str] = []

    def flush_paragraph():
        nonlocal pending_text
        if pending_text:
            out_blocks.append(("text", "\n".join(pending_text)))
            pending_text = []

    i = 0
    while i < len(blocks):
        kind, content = blocks[i]

        if kind == "image":
            flush_paragraph()
            out_blocks.append(("image", content))

        elif kind == "heading":
            # paper_reader also emits headings inside text blocks; skip them here
            pass

        elif kind == "subsection":
            flush_paragraph()
            out_blocks.append(("subsection", content))

        elif kind == "text":
            stripped = content.strip()
            if stripped:
                stripped = _strip_artefacts(stripped)

            if stripped in _SUBSECTION_TITLES:
                flush_paragraph()
                out_blocks.append(("subsection", stripped))
            elif stripped:
                pending_text.append(stripped)

        i += 1

    flush_paragraph()

    # Step 2: merge adjacent text blocks
    merged: list[tuple[str, str]] = []
    for kind, content in out_blocks:
        if kind == "text" and merged and merged[-1][0] == "text":
            merged[-1] = ("text", merged[-1][1] + "\n\n" + content)
        else:
            merged.append((kind, content))

    # Step 3: build output lines
    out_lines: list[str] = []
    blank_run = 0

    def emit(line: str):
        nonlocal blank_run
        if line == "":
            blank_run += 1
            if blank_run <= 2:
                out_lines.append("")
        else:
            blank_run = 0
            out_lines.append(line)

    for kind, content in merged:
        if kind == "text":
            for para_line in content.splitlines():
                emit(para_line)
        elif kind == "image":
            emit(content)
        elif kind == "subsection":
            emit(f"### {content}")
        emit("")

    # Step 4: strip trailing / leading blanks
    while out_lines and out_lines[-1] == "":
        out_lines.pop()
    while out_lines and out_lines[0] == "":
        out_lines.pop(0)

    # Step 5: skip duplicate ## headings
    # paper_reader extracts each section title twice (extracted heading + text title).
    # For subsections like "Outdoor Experiments" that belong to a parent section,
    # the second occurrence has orphan paragraph text that should also be skipped.
    heading_counts: dict[str, int] = {}
    deduped: list[str] = []
    j = 0
    while j < len(out_lines):
        line = out_lines[j]
        stripped = line.strip()
        if stripped.startswith("## "):
            heading_text = stripped[4:]
            count = heading_counts.get(heading_text, 0) + 1
            heading_counts[heading_text] = count
            if count > 1:
                # Skip the heading and any following orphan paragraph
                # (non-blank, non-image, non-heading text)
                j += 1
                while j < len(out_lines):
                    next_line = out_lines[j].strip()
                    if not next_line:
                        break
                    if next_line.startswith("![") or next_line.startswith("#"):
                        break
                    j += 1
                continue
        deduped.append(line)
        j += 1
    out_lines = deduped

    return "\n".join(out_lines) + "\n"


# ---------------------------------------------------------------------------
# merge pdf-inspector + paper-reader (both mode)
# ---------------------------------------------------------------------------

def graft_images_into_markdown(
    inspected_md: str,
    page_image_refs: dict[int, list[str]],
    images_dir: str,
) -> str:
    """Graft image references into pdf-inspector markdown.

    page_image_refs: page_index (0-based) -> list of markdown image ref lines.
    images_dir: directory name for the image paths in the markdown refs.

    Strategy: for each page that has images, find the best insertion point in
    the inspected markdown by matching the figure number mentioned in nearby
    text paragraphs, then insert the image line after that paragraph.

    Falls back to inserting at the page's first section heading if no figure
    match is found.
    """
    if not page_image_refs:
        return inspected_md

    inspected_lines = inspected_md.splitlines()
    out_lines = list(inspected_lines)

    # Track last inserted position so images appear in page order
    last_insert_pos = -1

    for page_idx in sorted(page_image_refs.keys()):
        image_lines = page_image_refs[page_idx]
        if not image_lines:
            continue

        # Try to find the first figure reference for this page in the text
        inserted_this_page = False
        for image_line in image_lines:
            # Extract figure number from the image line ref
            fig_match = re.search(r"(?:Figure|Table)\s*(\d+[A-Za-z]?)", image_line)
            if not fig_match:
                continue
            fig_num = fig_match.group(1).lower()

            for j in range(last_insert_pos + 1, len(inspected_lines)):
                line_lower = inspected_lines[j].lower()
                if line_lower.find(f"fig. {fig_num}") != -1 or \
                   line_lower.find(f"figure {fig_num}") != -1 or \
                   line_lower.find(f"table {fig_num}") != -1:
                    # Find end of this paragraph
                    insert_after = j
                    while insert_after + 1 < len(out_lines) and \
                          out_lines[insert_after + 1].strip() and \
                          not out_lines[insert_after + 1].strip().startswith("#") and \
                          not out_lines[insert_after + 1].strip().startswith("!["):
                        insert_after += 1
                    out_lines.insert(insert_after + 1, image_line)
                    last_insert_pos = insert_after + 1
                    inserted_this_page = True
                    break

        # Fallback: insert at the page's first section heading if no figure match
        if not inserted_this_page:
            for j in range(last_insert_pos + 1, len(out_lines)):
                if out_lines[j].startswith("### ") and not out_lines[j].startswith("#### "):
                    out_lines.insert(j + 1, "\n".join(image_lines))
                    last_insert_pos = j + 1 + len(image_lines)
                    break

    return "\n".join(out_lines) + "\n"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__.strip())
    parser.add_argument("pdf", type=Path, help="Path to PDF file")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(__file__).parent.parent / "raw" / "papers",
        help="Destination root (default: raw/papers/)"
    )
    parser.add_argument(
        "--engine",
        choices=["pdf-inspector", "paper-reader", "both"],
        default="pdf-inspector",
        help=(
            "pdf-inspector: fast Rust-based text extraction (default, recommended). "
            "paper-reader: CiroZhang/paper_reader - slower but extracts images. "
            "both: pdf-inspector for text + paper-reader for images."
        )
    )
    parser.add_argument(
        "--paper-reader-root",
        type=Path,
        default=Path.home() / "tools" / "paper_reader",
        help="paper_reader repo root (default: ~/tools/paper_reader)"
    )
    parser.add_argument(
        "--skip-copy",
        action="store_true",
        help="Run engines but do not copy output to raw/papers/ (debug)"
    )
    args = parser.parse_args()

    pdf_path = args.pdf.resolve()
    if not pdf_path.is_file():
        sys.stderr.write(f"ERROR: not a file: {pdf_path}\n")
        sys.exit(1)

    paper_reader_root = args.paper_reader_root.resolve()
    stem = pdf_stem(pdf_path)
    stamp = date.today().isoformat()
    briefing_map = parse_briefings(args.output_root)
    output_name = build_output_name(pdf_path, stamp, briefing_map)
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    # pdf-inspector path
    if args.engine in ("pdf-inspector", "both"):
        print(f"Running pdf-inspector on {pdf_path.name}")
        md_text, info = run_pdf_inspector(pdf_path)
        print(
            f"  type={info['pdf_type']}  pages={info['page_count']}  "
            f"ocr_pages={len(info['pages_needing_ocr'])}  time={info['processing_time_s']}s"
        )
        md_inspected = md_text
        info_inspected = info
        md_inspected = post_process_pdf_inspector_markdown(md_inspected)
    else:
        md_inspected = None
        info_inspected = None

    # paper-reader path
    pr_images_dest: Path | None = None
    pr_jsonl_dest: Path | None = None
    if args.engine in ("paper-reader", "both"):
        pr_images_dest = output_root / f"{output_name}-images"
        pr_jsonl_dest = output_root / f"{output_name}-raw.jsonl"

    if args.engine in ("paper-reader", "both"):
        print(f"Running paper_reader on {pdf_path.name}")
        md_paper_reader, pr_page_image_refs = run_paper_reader(
            pdf_path, paper_reader_root,
            images_dest=pr_images_dest,
            jsonl_dest=pr_jsonl_dest,
        )
        if pr_images_dest.exists():
            print(f"  images/  -> {pr_images_dest.relative_to(output_root.parent.parent)}/")
        if pr_jsonl_dest.exists():
            print(f"  jsonl/   -> {pr_jsonl_dest.relative_to(output_root.parent.parent)}")
    else:
        md_paper_reader = None
        pr_page_image_refs = {}

    # choose final markdown
    if args.engine == "both":
        final_md = graft_images_into_markdown(
            md_inspected,
            pr_page_image_refs,
            f"{output_name}-images",
        )
        print("  Merged pdf-inspector text + paper-reader image references")

    elif args.engine == "pdf-inspector":
        final_md = md_inspected

    else:  # paper-reader
        def fix_image_path(m):
            inner = re.sub(r"^(?:images/)?[^/]+/", "", m.group(2))
            return f"![{m.group(1)}]({output_name}-images/{inner})"
        fixed = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", fix_image_path, md_paper_reader)
        final_md = post_process_paper_reader_markdown(fixed)

    if args.skip_copy:
        sys.stdout.write(f"[--skip-copy] output left in temp dirs\n")
        sys.exit(0)

    # Write final markdown
    md_dest = output_root / f"{output_name}.md"
    md_dest.write_text(final_md)
    print(f"  *.md     -> {md_dest.relative_to(output_root.parent.parent)}")

    print(f"\nDone. {md_dest.name} ({len(final_md.splitlines())} lines)")


if __name__ == "__main__":
    main()
