from pathlib import Path

from .contracts import IngestionDocument


def load_pdf(path: str | Path, source_type: str = "PDF") -> IngestionDocument:
    pdf_path = Path(path)
    if not pdf_path.exists():
        raise FileNotFoundError(str(pdf_path))

    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "PDF ingestion requires the optional package 'pypdf'. "
            "Install it only when PDF crawling is enabled."
        ) from exc

    reader = PdfReader(str(pdf_path))
    pages = [page.extract_text() or "" for page in reader.pages]
    content = "\n\n".join(page.strip() for page in pages if page.strip())

    return IngestionDocument(
        source_type=source_type,
        source_id=pdf_path.stem,
        title=pdf_path.stem,
        content=content,
        source_url=str(pdf_path),
        metadata={"page_count": len(reader.pages)},
    )
