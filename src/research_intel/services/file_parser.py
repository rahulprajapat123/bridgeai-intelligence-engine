from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from pypdf import PdfReader
from bs4 import BeautifulSoup


SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx", ".html", ".htm", ".rtf"}


class UnsupportedBriefFile(ValueError):
    pass


class BriefFileParser:
    """
    Enhanced file parser supporting multiple document formats.
    Extracts text from PDFs, Word docs, HTML, and more.
    """
    
    def parse(self, filename: str, content: bytes) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise UnsupportedBriefFile(
                f"Unsupported format '{suffix}'. Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}"
            )
        if suffix in {".txt", ".md"}:
            return self._decode_text(content)
        if suffix == ".pdf":
            return self._parse_pdf(content)
        if suffix == ".docx":
            return self._parse_docx(content)
        if suffix in {".html", ".htm"}:
            return self._parse_html(content)
        if suffix == ".rtf":
            return self._parse_rtf(content)
        raise UnsupportedBriefFile("Unsupported brief format.")

    def _decode_text(self, content: bytes) -> str:
        for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                return content.decode(encoding).strip()
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="ignore").strip()

    def _parse_pdf(self, content: bytes) -> str:
        """Enhanced PDF parsing with better text extraction."""
        try:
            reader = PdfReader(io.BytesIO(content))
            pages = []
            
            for page_num, page in enumerate(reader.pages):
                # Try to extract text with layout preservation
                text = page.extract_text(extraction_mode="layout") or ""
                
                if not text.strip():
                    # Fallback to plain extraction
                    text = page.extract_text() or ""
                
                # Add page separator for context
                if text.strip():
                    pages.append(f"--- Page {page_num + 1} ---\n{text}")
            
            full_text = "\n\n".join(pages)
            
            # Try to extract metadata
            metadata = reader.metadata or {}
            if metadata:
                meta_text = f"Document Metadata:\n"
                if metadata.get("/Title"):
                    meta_text += f"Title: {metadata['/Title']}\n"
                if metadata.get("/Author"):
                    meta_text += f"Author: {metadata['/Author']}\n"
                if metadata.get("/Subject"):
                    meta_text += f"Subject: {metadata['/Subject']}\n"
                full_text = meta_text + "\n" + full_text
            
            return self._clean(full_text)
            
        except Exception as e:
            # Fallback to basic extraction
            reader = PdfReader(io.BytesIO(content))
            pages = [page.extract_text() or "" for page in reader.pages]
            return self._clean("\n\n".join(pages))

    def _parse_docx(self, content: bytes) -> str:
        """Enhanced DOCX parsing with better structure preservation."""
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            try:
                xml = archive.read("word/document.xml")
            except KeyError as exc:
                raise UnsupportedBriefFile("DOCX file is missing word/document.xml.") from exc
        
        root = ElementTree.fromstring(xml)
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        
        elements: list[str] = []
        
        # Extract paragraphs with style information
        for paragraph in root.findall(".//w:p", namespace):
            texts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
            if texts:
                para_text = "".join(texts)
                
                # Check if it's a heading (simplified check)
                style = paragraph.find(".//w:pStyle", namespace)
                if style is not None and "Heading" in style.get("{" + namespace["w"] + "}val", ""):
                    para_text = f"\n## {para_text} ##\n"
                
                elements.append(para_text)
        
        # Extract tables
        for table in root.findall(".//w:tbl", namespace):
            elements.append("\n[TABLE]")
            for row in table.findall(".//w:tr", namespace):
                cells = []
                for cell in row.findall(".//w:tc", namespace):
                    cell_texts = [node.text or "" for node in cell.findall(".//w:t", namespace)]
                    cells.append(" ".join(cell_texts))
                if cells:
                    elements.append(" | ".join(cells))
            elements.append("[/TABLE]\n")
        
        return self._clean("\n".join(elements))
    
    def _parse_html(self, content: bytes) -> str:
        """Parse HTML content and extract text."""
        text = self._decode_text(content)
        soup = BeautifulSoup(text, "html.parser")
        
        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()
        
        # Get text with some structure preservation
        text = soup.get_text(separator="\n", strip=True)
        return self._clean(text)
    
    def _parse_rtf(self, content: bytes) -> str:
        """Basic RTF parsing (strips RTF codes)."""
        text = self._decode_text(content)
        
        # Remove RTF control words and groups
        # This is a simplified parser - for production use a proper RTF library
        text = re.sub(r'\\[a-z]+\d*\s?', ' ', text)  # Remove control words
        text = re.sub(r'[{}]', '', text)  # Remove braces
        text = re.sub(r'\\\'[0-9a-fA-F]{2}', '', text)  # Remove hex codes
        
        return self._clean(text)

    def _clean(self, text: str) -> str:
        """Clean and normalize extracted text."""
        # Remove excessive whitespace
        text = re.sub(r' +', ' ', text)
        # Normalize line breaks
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Remove common artifacts
        text = re.sub(r'\f', '\n', text)  # Form feed to newline
        text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', '', text)  # Remove control chars
        return text.strip()


class DocumentExtractor:
    """
    Advanced document extraction for research papers and technical documents.
    Extracts structured information beyond just text.
    """
    
    @staticmethod
    def extract_metadata_from_pdf(content: bytes) -> dict[str, str | list[str]]:
        """Extract metadata from PDF."""
        try:
            reader = PdfReader(io.BytesIO(content))
            metadata = reader.metadata or {}
            
            return {
                "title": metadata.get("/Title", ""),
                "author": metadata.get("/Author", ""),
                "subject": metadata.get("/Subject", ""),
                "keywords": metadata.get("/Keywords", ""),
                "creator": metadata.get("/Creator", ""),
                "producer": metadata.get("/Producer", ""),
                "creation_date": metadata.get("/CreationDate", ""),
                "page_count": len(reader.pages),
            }
        except Exception:
            return {}
    
    @staticmethod
    def extract_tables_from_pdf(content: bytes) -> list[list[list[str]]]:
        """Extract tables from PDF (basic implementation)."""
        # For production, consider using libraries like:
        # - camelot-py
        # - tabula-py
        # - pdfplumber
        return []
    
    @staticmethod
    def extract_sections(text: str) -> dict[str, str]:
        """Extract common document sections."""
        sections = {}
        
        # Common section patterns
        patterns = {
            "abstract": r"(?i)(?:abstract|summary)[\s\n]*[:.-]?\s*(.*?)(?=\n\s*(?:introduction|keywords|1\.|$))",
            "introduction": r"(?i)(?:introduction|background)[\s\n]*[:.-]?\s*(.*?)(?=\n\s*(?:method|related work|2\.|$))",
            "methodology": r"(?i)(?:method|methodology|approach)[\s\n]*[:.-]?\s*(.*?)(?=\n\s*(?:results|experiment|3\.|$))",
            "results": r"(?i)(?:results|findings|evaluation)[\s\n]*[:.-]?\s*(.*?)(?=\n\s*(?:discussion|conclusion|4\.|$))",
            "conclusion": r"(?i)(?:conclusion|summary)[\s\n]*[:.-]?\s*(.*?)(?=\n\s*(?:references|acknowledgment|$))",
        }
        
        for section_name, pattern in patterns.items():
            match = re.search(pattern, text, re.DOTALL | re.MULTILINE)
            if match:
                sections[section_name] = match.group(1).strip()[:2000]  # Limit length
        
        return sections

