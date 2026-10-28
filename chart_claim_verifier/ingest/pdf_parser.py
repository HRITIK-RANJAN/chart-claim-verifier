"""PDF -> Report(figures, sentences) (implementation.md §6.2).

PyMuPDF gives text blocks with positions and the embedded images. A figure's
caption is the text block just below it that starts with "Figure N" / "Fig. N".
Figures are also OCR'd once here (legend, ticks, titles) for retrieval and the
parser, and their axis span is measured for the disagreement floor.
"""
from __future__ import annotations

import re
from pathlib import Path

import pymupdf

from ..schemas import Figure, Report, Sentence
from ..tools.axis import ChartReadError, analyse
from ..tools.chart_ocr import ocr_lines
from .chart_type import detect_chart_type

CAPTION_RE = re.compile(r"^\s*(?:Figure|Fig\.)\s*(\d+)\s*[:.]", re.I)
HEADING_RE = re.compile(r"^\s*\d+(?:\.\d+)*\s+[A-Z][\w ]{0,40}$")
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    # do not split after "Fig." / "e.g." / "i.e."
    protected = re.sub(r"\b(Fig|e\.g|i\.e|et al)\.", lambda m: m.group().replace(".", "§"), text)
    return [s.replace("§", ".").strip() for s in SENT_SPLIT.split(protected) if s.strip()]


def merge_continued(blocks: list[tuple]) -> list[tuple]:
    """Join a paragraph that a page break (or a figure) cut in the middle of a sentence.

    Blocks are (page, y0, y1, text) in reading order. A block that is a full line of prose and stops without a full
    stop ("... higher on IMDB than on") continues in the next block ("SVHN (Figure 4)."). Left unjoined, the first
    half parsed as a different claim and was flagged (2 of the 3 wrong flags on holdout2 had this cause, §24.7).
    Short blocks (page numbers, headers), headings and captions are never joined.
    """
    out: list[tuple] = []
    for b in blocks:
        prev = out[-1] if out else None
        if (prev and len(prev[3]) >= 30 and prev[3][-1] not in ".!?:" and not HEADING_RE.match(prev[3])
                and not CAPTION_RE.match(prev[3]) and not CAPTION_RE.match(b[3]) and not HEADING_RE.match(b[3])):
            out[-1] = (prev[0], prev[1], prev[2] if b[0] != prev[0] else b[2], prev[3] + " " + b[3])
        else:
            out.append(b)
    return out


def parse_pdf(pdf_path: str | Path, out_dir: str | Path, report_id: str | None = None,
              analyse_figures: bool = True) -> Report:
    pdf_path, out_dir = Path(pdf_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_id = report_id or pdf_path.parent.name
    doc = pymupdf.open(str(pdf_path))

    images, blocks = [], []      # (page, y0, y1, path) / (page, y0, y1, text)
    for pno, page in enumerate(doc):
        for img in page.get_images(full=True):
            xref = img[0]
            rects = page.get_image_rects(xref)
            if not rects:
                continue
            data = doc.extract_image(xref)
            path = out_dir / f"p{pno}_x{xref}.{data['ext']}"
            path.write_bytes(data["image"])
            images.append((pno, rects[0].y0, rects[0].y1, str(path)))
        for b in page.get_text("blocks"):
            if b[6] == 0 and b[4].strip():
                blocks.append((pno, b[1], b[3], " ".join(b[4].split())))
    images.sort()
    blocks = merge_continued(sorted(blocks))

    figures: list[Figure] = []
    caption_ids = set()
    for k, (pno, y0, y1, path) in enumerate(images):
        cap, number = "", None
        below = [(b, i) for i, b in enumerate(blocks) if b[0] == pno and b[1] >= y1 - 5 and CAPTION_RE.match(b[3])
                 and i not in caption_ids]
        if not below:
            # figure at the bottom of a page: its caption may open the next page
            first_img_next = min((im[1] for im in images if im[0] == pno + 1), default=1e9)
            below = [(b, i) for i, b in enumerate(blocks) if b[0] == pno + 1 and b[2] <= first_img_next
                     and CAPTION_RE.match(b[3]) and i not in caption_ids]
        if below:
            b, i = min(below, key=lambda bi: bi[0][1])
            caption_ids.add(i)
            number = int(CAPTION_RE.match(b[3]).group(1))
            cap = CAPTION_RE.sub("", b[3]).strip()
        fid = f"fig{number}" if number else f"img{k + 1}"
        fig = Figure(figure_id=fid, report_id=report_id, image_path=path, caption=cap, number=number, page=pno)
        if analyse_figures:
            fig.chart_type = detect_chart_type(path)
            fig.text_lines = [ln.text for ln in ocr_lines(path)]
            try:
                geo = analyse(path)
                fig.y_span = geo.y_span
                # legend entries found via their colour handles are more reliable than full-image OCR
                fig.text_lines += list(geo.legend) + [t for _, t in geo.xticks]
            except ChartReadError:
                fig.y_span = None
        figures.append(fig)

    sentences: list[Sentence] = []
    for i, (pno, y0, y1, text) in enumerate(blocks):
        if i in caption_ids or HEADING_RE.match(text):
            continue
        # the last figure before this block in reading order (used by the "nearest figure" ablation)
        before = [(im[0], im[2], f) for f, im in zip(figures, images) if (im[0], im[2]) <= (pno, y0 + 1)]
        nearest = max(before, key=lambda t: (t[0], t[1]))[2].figure_id if before else None
        for s in split_sentences(text):
            sentences.append(Sentence(sentence_id=f"{report_id}_s{len(sentences)}", report_id=report_id,
                                      text=s, page=pno, nearest_figure_id=nearest))
    return Report(report_id=report_id, pdf_path=str(pdf_path), figures=figures, sentences=sentences)
