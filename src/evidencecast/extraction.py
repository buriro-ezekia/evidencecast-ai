# Extracts structured text from uploaded PDF, Markdown and plain-text research sources.
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader


class ExtractionError(RuntimeError):
    """Raised when a supported source cannot yield usable text."""


@dataclass(frozen=True)
class ExtractedSegment:
    """A text segment linked to its source page when page data is available."""

    page_number: int | None
    text: str


@dataclass(frozen=True)
class ExtractionResult:
    """Normalised source text and provenance metadata."""

    filename: str
    media_type: str
    method: str
    page_count: int | None
    character_count: int
    full_text: str
    segments: tuple[ExtractedSegment, ...]

    def metadata(self) -> dict[str, object]:
        """Return JSON-serialisable extraction metadata without duplicating full text."""

        return {
            "filename": self.filename,
            "media_type": self.media_type,
            "method": self.method,
            "page_count": self.page_count,
            "character_count": self.character_count,
            "segments": [asdict(segment) for segment in self.segments],
        }


def _normalise_text(value: str) -> str:
    value = value.replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[\t\f\v]+", " ", value)
    value = re.sub(r"[ ]{2,}", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ExtractionError("The uploaded text file could not be decoded safely.")


def _extract_pdf(filename: str, data: bytes) -> ExtractionResult:
    try:
        reader = PdfReader(BytesIO(data))
    except Exception as exc:
        raise ExtractionError(f"The PDF could not be opened: {exc}") from exc

    segments: list[ExtractedSegment] = []
    for page_index, page in enumerate(reader.pages, start=1):
        try:
            page_text = _normalise_text(page.extract_text() or "")
        except Exception as exc:
            raise ExtractionError(
                f"Text extraction failed on PDF page {page_index}: {exc}"
            ) from exc
        if page_text:
            segments.append(ExtractedSegment(page_number=page_index, text=page_text))

    full_text = "\n\n".join(segment.text for segment in segments).strip()
    if not full_text:
        raise ExtractionError(
            "No selectable text was found in the PDF. It may be a scanned document; "
            "OCR is intentionally deferred to a later EvidenceCast milestone."
        )

    return ExtractionResult(
        filename=filename,
        media_type="application/pdf",
        method="pypdf",
        page_count=len(reader.pages),
        character_count=len(full_text),
        full_text=full_text,
        segments=tuple(segments),
    )


def _extract_text_file(filename: str, media_type: str, data: bytes) -> ExtractionResult:
    text = _normalise_text(_decode_text(data))
    if not text:
        raise ExtractionError("The uploaded text file is empty after normalisation.")

    return ExtractionResult(
        filename=filename,
        media_type=media_type,
        method="text-decoder",
        page_count=None,
        character_count=len(text),
        full_text=text,
        segments=(ExtractedSegment(page_number=None, text=text),),
    )


def extract_source(filename: str, media_type: str | None, data: bytes) -> ExtractionResult:
    """Extract text from one supported source while preserving page-level provenance."""

    suffix = Path(filename).suffix.lower()
    resolved_media_type = (media_type or "").lower()

    if suffix == ".pdf" or resolved_media_type == "application/pdf":
        return _extract_pdf(filename, data)
    if suffix in {".txt", ".md", ".markdown"} or resolved_media_type.startswith("text/"):
        default_type = "text/markdown" if suffix in {".md", ".markdown"} else "text/plain"
        return _extract_text_file(filename, resolved_media_type or default_type, data)

    raise ExtractionError(
        "Unsupported source type. Upload a PDF, Markdown document or plain-text file."
    )
