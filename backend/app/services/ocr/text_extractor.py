"""
PDF Text Extraction Service
Handles both digital PDFs and scanned documents using OCR

Supports:
- PyMuPDF (fitz) for digital PDFs (fast, free)
- AWS Textract for scanned documents (accurate, paid)
- Tesseract OCR as fallback
"""

import asyncio
import io
import re
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass

import fitz  # PyMuPDF
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


@dataclass
class ExtractedDocument:
    """Result of text extraction from a document"""
    text: str
    page_count: int
    extraction_method: str
    confidence: float
    has_images: bool
    metadata: dict


@dataclass
class PageContent:
    """Content extracted from a single page"""
    page_number: int
    text: str
    has_text: bool
    has_images: bool
    image_count: int


class TextExtractorService:
    """
    Intelligent text extraction from PDFs.

    Strategy:
    1. Try digital text extraction first (fast)
    2. If text is sparse, use OCR (slower but accurate)
    3. Clean and normalise extracted text
    """

    # Minimum text density to consider a page "text-based"
    MIN_TEXT_DENSITY = 100  # characters per page

    # Common planning document patterns to preserve
    PRESERVE_PATTERNS = [
        r"Policy\s+[A-Z]\d+",  # Camden policies
        r"NPPF\s+\d+",  # National Planning Policy Framework
        r"\d{4}/\d{4,5}/[A-Z]+",  # Case references
        r"Section\s+\d+",  # Legal sections
    ]

    def __init__(self):
        self.use_aws_textract = settings.use_aws_textract
        self._textract_client = None

    @property
    def textract_client(self):
        """Lazy initialisation of AWS Textract client"""
        if self._textract_client is None and self.use_aws_textract:
            import boto3
            self._textract_client = boto3.client(
                "textract",
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_region,
            )
        return self._textract_client

    async def extract_text(
        self,
        pdf_path: Path,
        force_ocr: bool = False
    ) -> ExtractedDocument:
        """
        Extract text from a PDF document.

        Args:
            pdf_path: Path to the PDF file
            force_ocr: Force OCR even if digital text is available

        Returns:
            ExtractedDocument with extracted text and metadata
        """
        logger.info("extracting_text", path=str(pdf_path))

        try:
            # First, try digital extraction
            if not force_ocr:
                result = await self._extract_digital(pdf_path)
                if result and result.confidence > 0.7:
                    return result

            # If digital extraction failed or was poor, try OCR
            if self.use_aws_textract:
                result = await self._extract_with_textract(pdf_path)
            else:
                result = await self._extract_with_tesseract(pdf_path)

            return result

        except Exception as e:
            logger.error("text_extraction_failed", path=str(pdf_path), error=str(e))
            raise

    async def _extract_digital(self, pdf_path: Path) -> Optional[ExtractedDocument]:
        """Extract text from a digital PDF using PyMuPDF"""
        try:
            doc = fitz.open(str(pdf_path))
            pages: List[PageContent] = []
            total_text = []

            for page_num in range(len(doc)):
                page = doc[page_num]

                # Extract text
                text = page.get_text("text")

                # Count images
                image_list = page.get_images()

                page_content = PageContent(
                    page_number=page_num + 1,
                    text=text,
                    has_text=len(text.strip()) > self.MIN_TEXT_DENSITY,
                    has_images=len(image_list) > 0,
                    image_count=len(image_list)
                )
                pages.append(page_content)
                total_text.append(text)

            doc.close()

            # Calculate confidence based on text density
            text_pages = sum(1 for p in pages if p.has_text)
            confidence = text_pages / len(pages) if pages else 0

            combined_text = "\n\n".join(total_text)
            cleaned_text = self._clean_text(combined_text)

            # Check if this looks like a scanned document
            has_significant_images = any(p.image_count > 0 for p in pages)
            is_likely_scanned = confidence < 0.5 and has_significant_images

            if is_likely_scanned:
                logger.info("document_appears_scanned", path=str(pdf_path))
                return None  # Signal to use OCR

            return ExtractedDocument(
                text=cleaned_text,
                page_count=len(pages),
                extraction_method="digital",
                confidence=confidence,
                has_images=has_significant_images,
                metadata={
                    "text_pages": text_pages,
                    "image_pages": sum(1 for p in pages if p.has_images),
                }
            )

        except Exception as e:
            logger.error("digital_extraction_failed", error=str(e))
            return None

    async def _extract_with_textract(self, pdf_path: Path) -> ExtractedDocument:
        """Extract text using AWS Textract"""
        logger.info("using_textract", path=str(pdf_path))

        try:
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()

            # For PDFs, we need to use async document analysis
            # First, upload to S3 or use direct bytes for small files
            if len(pdf_bytes) < 5 * 1024 * 1024:  # 5MB limit for sync
                response = self.textract_client.detect_document_text(
                    Document={"Bytes": pdf_bytes}
                )
            else:
                # For larger files, would need S3 + async processing
                # This is a simplified version
                response = await self._textract_async(pdf_bytes)

            # Extract text blocks
            text_blocks = []
            for block in response.get("Blocks", []):
                if block["BlockType"] == "LINE":
                    text_blocks.append(block["Text"])

            combined_text = "\n".join(text_blocks)
            cleaned_text = self._clean_text(combined_text)

            # Calculate confidence from Textract confidence scores
            confidences = [
                block.get("Confidence", 0) / 100
                for block in response.get("Blocks", [])
                if block["BlockType"] == "LINE"
            ]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0

            return ExtractedDocument(
                text=cleaned_text,
                page_count=1,  # Textract doesn't give page count easily
                extraction_method="textract",
                confidence=avg_confidence,
                has_images=True,
                metadata={"block_count": len(text_blocks)}
            )

        except Exception as e:
            logger.error("textract_extraction_failed", error=str(e))
            # Fall back to Tesseract
            return await self._extract_with_tesseract(pdf_path)

    async def _textract_async(self, pdf_bytes: bytes) -> dict:
        """Handle async Textract processing for large documents"""
        # This would use S3 + StartDocumentTextDetection
        # Simplified for now
        raise NotImplementedError("Large document async processing not implemented")

    async def _extract_with_tesseract(self, pdf_path: Path) -> ExtractedDocument:
        """Extract text using Tesseract OCR (free alternative)"""
        logger.info("using_tesseract", path=str(pdf_path))

        try:
            import pytesseract
            from pdf2image import convert_from_path

            # Convert PDF pages to images
            images = convert_from_path(str(pdf_path), dpi=300)

            text_blocks = []
            for i, image in enumerate(images):
                # Run OCR on each page
                page_text = pytesseract.image_to_string(
                    image,
                    lang="eng",
                    config="--psm 1"  # Automatic page segmentation
                )
                text_blocks.append(page_text)

            combined_text = "\n\n".join(text_blocks)
            cleaned_text = self._clean_text(combined_text)

            return ExtractedDocument(
                text=cleaned_text,
                page_count=len(images),
                extraction_method="tesseract",
                confidence=0.8,  # Tesseract doesn't provide confidence easily
                has_images=True,
                metadata={"pages_processed": len(images)}
            )

        except Exception as e:
            logger.error("tesseract_extraction_failed", error=str(e))
            raise

    def _clean_text(self, text: str) -> str:
        """Clean and normalise extracted text"""
        if not text:
            return ""

        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text)

        # Fix common OCR errors
        text = self._fix_ocr_errors(text)

        # Remove headers/footers (common patterns)
        text = self._remove_headers_footers(text)

        # Normalise line breaks
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Preserve important patterns
        text = self._preserve_patterns(text)

        return text.strip()

    def _fix_ocr_errors(self, text: str) -> str:
        """Fix common OCR misreadings"""
        corrections = {
            # Common planning terms
            "poiicy": "policy",
            "Poiicy": "Policy",
            "pian": "plan",
            "Pian": "Plan",
            "councii": "council",
            "Councii": "Council",
            "buiiding": "building",
            "Buiiding": "Building",
            "approvai": "approval",
            "Approvai": "Approval",
            "refusai": "refusal",
            "Refusai": "Refusal",
            "materiai": "material",
            "Materiai": "Material",
            "residentiai": "residential",
            "Residentiai": "Residential",
            # Number/letter confusion
            "0ffice": "Office",
            "1isted": "listed",
            "1ocation": "location",
        }

        for wrong, correct in corrections.items():
            text = text.replace(wrong, correct)

        return text

    def _remove_headers_footers(self, text: str) -> str:
        """Remove common headers and footers from planning documents"""
        patterns = [
            r"Page \d+ of \d+",
            r"Camden Council Planning",
            r"www\.camden\.gov\.uk",
            r"Document Reference:.*\n",
            r"Printed on:.*\n",
            r"OFFICIAL",
        ]

        for pattern in patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        return text

    def _preserve_patterns(self, text: str) -> str:
        """Ensure important patterns are preserved correctly"""
        # Fix case references that may have been mangled
        text = re.sub(
            r"(\d{4})\s*/\s*(\d{4,5})\s*/\s*([A-Z]+)",
            r"\1/\2/\3",
            text
        )

        # Fix policy references
        text = re.sub(
            r"Policy\s+([A-Z])\s*(\d+)",
            r"Policy \1\2",
            text,
            flags=re.IGNORECASE
        )

        return text

    async def extract_from_bytes(
        self,
        pdf_bytes: bytes,
        filename: str = "document.pdf"
    ) -> ExtractedDocument:
        """Extract text from PDF bytes (for uploaded files)"""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            temp_path = Path(f.name)

        try:
            result = await self.extract_text(temp_path)
            return result
        finally:
            temp_path.unlink()

    def extract_sections(self, text: str) -> dict:
        """Extract key sections from a planning document"""
        sections = {
            "proposal": "",
            "site_description": "",
            "planning_history": "",
            "policy_context": "",
            "assessment": "",
            "conclusion": "",
            "conditions": "",
        }

        # Common section headers in Camden reports
        section_patterns = {
            "proposal": r"(?:Proposal|Description of Development|The Proposal)(.*?)(?=\n[A-Z][A-Z\s]+\n|$)",
            "site_description": r"(?:Site and Surroundings|Site Description|The Site)(.*?)(?=\n[A-Z][A-Z\s]+\n|$)",
            "planning_history": r"(?:Planning History|Relevant History)(.*?)(?=\n[A-Z][A-Z\s]+\n|$)",
            "policy_context": r"(?:Policy Context|Planning Policy|Relevant Policies)(.*?)(?=\n[A-Z][A-Z\s]+\n|$)",
            "assessment": r"(?:Assessment|Planning Assessment|Considerations)(.*?)(?=\n[A-Z][A-Z\s]+\n|$)",
            "conclusion": r"(?:Conclusion|Recommendation|Decision)(.*?)(?=\n[A-Z][A-Z\s]+\n|$)",
            "conditions": r"(?:Conditions|Schedule of Conditions)(.*?)(?=\n[A-Z][A-Z\s]+\n|$)",
        }

        for section_name, pattern in section_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                sections[section_name] = match.group(1).strip()[:2000]

        return sections

    def extract_officer_quotes(self, text: str) -> List[str]:
        """Extract notable officer statements from the text"""
        quotes = []

        # Patterns for officer conclusions and key statements
        patterns = [
            r"(?:officer\s+considers|it\s+is\s+considered|in\s+the\s+officer'?s\s+view)[^.]+\.",
            r"(?:the\s+proposal\s+(?:is|would\s+be))[^.]+(?:acceptable|appropriate|satisfactory)[^.]*\.",
            r"(?:no\s+(?:harm|adverse|negative))[^.]+\.",
            r"(?:the\s+development\s+(?:complies|accords))[^.]+\.",
            r"(?:the\s+scheme|design|materials?)[^.]+(?:sympathetic|appropriate|acceptable)[^.]*\.",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            quotes.extend(matches[:3])  # Limit to 3 per pattern

        return quotes[:10]  # Return max 10 quotes
