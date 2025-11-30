#!/usr/bin/env python3
"""
Initial data scraping script for Planning Precedent AI

This script performs the initial scrape of Camden's planning portal
to populate the database with historical decisions.

Usage:
    python scripts/initial_scrape.py --start-date 2015-01-01 --end-date 2024-12-31
"""

import asyncio
import argparse
from datetime import date, datetime
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.db.supabase_client import SupabaseDB, get_supabase_client
from app.services.scraper import CamdenPlanningScraperService
from app.services.ocr import TextExtractorService
from app.services.embeddings import EmbeddingService

logger = get_logger(__name__)


async def process_decision(
    scraped_app,
    scraper: CamdenPlanningScraperService,
    extractor: TextExtractorService,
    embedder: EmbeddingService,
    db: SupabaseDB,
):
    """Process a single scraped decision"""
    try:
        # Check if already exists
        if await db.decision_exists(scraped_app.case_reference):
            logger.debug("decision_exists", case_ref=scraped_app.case_reference)
            return False

        # Download and extract text from PDF
        full_text = ""
        if scraped_app.decision_notice_url:
            pdf_path = await scraper.download_pdf(scraped_app.decision_notice_url)
            if pdf_path:
                extracted = await extractor.extract_text(pdf_path)
                full_text = extracted.text

        if not full_text and scraped_app.officer_report_url:
            pdf_path = await scraper.download_pdf(scraped_app.officer_report_url)
            if pdf_path:
                extracted = await extractor.extract_text(pdf_path)
                full_text = extracted.text

        if not full_text:
            logger.warning("no_text_extracted", case_ref=scraped_app.case_reference)
            full_text = scraped_app.description

        # Convert to database model
        decision_create = scraper.convert_to_decision_create(scraped_app, full_text)

        # Create the decision
        decision = await db.create_decision(decision_create)

        # Chunk and embed the text
        chunks = embedder.chunk_document(full_text)
        if chunks:
            doc_chunks = await embedder.embed_chunks(chunks)
            for chunk in doc_chunks:
                chunk.decision_id = decision.id
            await db.create_chunks(decision.id, doc_chunks)

        logger.info(
            "decision_processed",
            case_ref=scraped_app.case_reference,
            chunk_count=len(chunks)
        )
        return True

    except Exception as e:
        logger.error(
            "decision_processing_failed",
            case_ref=scraped_app.case_reference,
            error=str(e)
        )
        return False


async def main(start_date: date, end_date: date, wards: list[str] = None):
    """Main scraping function"""
    setup_logging()

    logger.info(
        "starting_initial_scrape",
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        wards=wards or "all"
    )

    # Initialise services
    db = SupabaseDB(get_supabase_client())
    extractor = TextExtractorService()
    embedder = EmbeddingService()

    processed = 0
    failed = 0

    async with CamdenPlanningScraperService() as scraper:
        async for app in scraper.scrape_decisions(
            start_date=start_date,
            end_date=end_date,
            wards=wards,
        ):
            success = await process_decision(
                app, scraper, extractor, embedder, db
            )
            if success:
                processed += 1
            else:
                failed += 1

            # Progress update
            if (processed + failed) % 100 == 0:
                logger.info(
                    "scrape_progress",
                    processed=processed,
                    failed=failed
                )

    logger.info(
        "initial_scrape_complete",
        total_processed=processed,
        total_failed=failed
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Initial scrape of Camden planning decisions"
    )
    parser.add_argument(
        "--start-date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=date(2015, 1, 1),
        help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end-date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=date.today(),
        help="End date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--wards",
        nargs="+",
        help="Specific wards to scrape (default: all target wards)"
    )

    args = parser.parse_args()

    asyncio.run(main(args.start_date, args.end_date, args.wards))
