"""
Camden Council Planning Portal Scraper
Extracts planning decisions from camdocs.camden.gov.uk

This scraper is designed to:
1. Navigate the Camden planning portal
2. Search for planning decisions by date range and ward
3. Download decision notices and officer reports (PDFs)
4. Extract metadata from each application

IMPORTANT: This scraper respects rate limits and includes delays
to avoid overloading the council's servers. It should be run
during off-peak hours and with appropriate rate limiting.
"""

import asyncio
import os
import re
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import structlog

from app.core.config import settings
from app.models.planning import (
    PlanningDecisionCreate,
    Outcome,
    DevelopmentType,
    ConservationAreaStatus,
)

logger = structlog.get_logger(__name__)


@dataclass
class ScrapedApplication:
    """Raw scraped application data before processing"""
    case_reference: str
    address: str
    ward: str
    postcode: Optional[str]
    decision_date: date
    outcome: str
    application_type: str
    description: str
    decision_notice_url: Optional[str]
    officer_report_url: Optional[str]
    raw_html: Optional[str] = None


class CamdenPlanningScraperService:
    """
    Scraper for Camden Council's planning portal.

    The Camden planning portal uses a combination of search forms
    and document management system (HPE Content Manager/TRIM).

    Key URLs:
    - Main portal: https://www.camden.gov.uk/planning-applications
    - Document search: https://camdocs.camden.gov.uk/HPRMWebDrawer/PlanRec
    - Application search: https://planningrecords.camden.gov.uk/
    """

    BASE_URL = "https://planningrecords.camden.gov.uk"
    SEARCH_URL = f"{BASE_URL}/Northgate/PlanningExplorer/GeneralSearch.aspx"
    DOCS_URL = "https://camdocs.camden.gov.uk/HPRMWebDrawer/PlanRec"

    # Rate limiting
    REQUEST_DELAY = 2.0  # Seconds between requests
    MAX_RETRIES = 3

    # Camden wards of interest (North and West Camden focus)
    TARGET_WARDS = [
        "Hampstead Town",
        "Belsize",
        "Frognal",
        "Swiss Cottage",
        "West Hampstead",
        "Fortune Green",
        "Kilburn",
        "Gospel Oak",
        "Kentish Town",
        "Camden Town",
        "Highgate",
        "Haverstock",
    ]

    def __init__(self):
        self.driver: Optional[webdriver.Chrome] = None
        self.http_client: Optional[httpx.AsyncClient] = None
        self.download_dir = Path(tempfile.mkdtemp(prefix="camden_planning_"))
        self._request_count = 0
        self._last_request_time: Optional[datetime] = None

    async def __aenter__(self):
        """Async context manager entry"""
        await self._init_driver()
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "PlanningPrecedentAI/1.0 (Research Tool)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.driver:
            self.driver.quit()
        if self.http_client:
            await self.http_client.aclose()

    async def _init_driver(self):
        """Initialise Chrome WebDriver with headless options"""
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--user-agent=PlanningPrecedentAI/1.0")

        # Set download directory
        prefs = {
            "download.default_directory": str(self.download_dir),
            "download.prompt_for_download": False,
            "plugins.always_open_pdf_externally": True,
        }
        options.add_experimental_option("prefs", prefs)

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.implicitly_wait(10)

    async def _rate_limit(self):
        """Enforce rate limiting between requests"""
        if self._last_request_time:
            elapsed = (datetime.now() - self._last_request_time).total_seconds()
            if elapsed < self.REQUEST_DELAY:
                await asyncio.sleep(self.REQUEST_DELAY - elapsed)
        self._last_request_time = datetime.now()
        self._request_count += 1

    async def scrape_decisions(
        self,
        start_date: date,
        end_date: date,
        wards: Optional[List[str]] = None,
        outcomes: Optional[List[str]] = None,
    ) -> AsyncGenerator[ScrapedApplication, None]:
        """
        Scrape planning decisions for the given date range.

        Args:
            start_date: Start of date range
            end_date: End of date range
            wards: List of ward names to filter (default: all target wards)
            outcomes: List of outcomes to filter (default: Granted and Refused)

        Yields:
            ScrapedApplication objects for each found decision
        """
        wards = wards or self.TARGET_WARDS
        outcomes = outcomes or ["Granted", "Refused"]

        logger.info(
            "starting_scrape",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            wards=wards,
            outcomes=outcomes
        )

        # Split date range into monthly chunks for pagination
        current_start = start_date
        while current_start < end_date:
            current_end = min(
                current_start + timedelta(days=30),
                end_date
            )

            for ward in wards:
                for outcome in outcomes:
                    try:
                        async for app in self._scrape_period(
                            current_start, current_end, ward, outcome
                        ):
                            yield app
                    except Exception as e:
                        logger.error(
                            "scrape_period_failed",
                            ward=ward,
                            start=current_start.isoformat(),
                            error=str(e)
                        )
                        continue

            current_start = current_end + timedelta(days=1)

    async def _scrape_period(
        self,
        start_date: date,
        end_date: date,
        ward: str,
        outcome: str
    ) -> AsyncGenerator[ScrapedApplication, None]:
        """Scrape a specific period/ward/outcome combination"""
        await self._rate_limit()

        try:
            # Navigate to search page
            self.driver.get(self.SEARCH_URL)
            await asyncio.sleep(1)

            # Wait for form to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "cboWardCode"))
            )

            # Fill search form
            await self._fill_search_form(start_date, end_date, ward, outcome)

            # Submit and wait for results
            search_button = self.driver.find_element(By.ID, "csbtnSearch")
            search_button.click()

            await asyncio.sleep(2)

            # Process results pages
            page_num = 1
            while True:
                results = await self._parse_results_page()

                for result in results:
                    yield result

                # Check for next page
                if not await self._go_to_next_page():
                    break

                page_num += 1
                await self._rate_limit()

            logger.info(
                "period_scrape_complete",
                ward=ward,
                outcome=outcome,
                pages_scraped=page_num
            )

        except TimeoutException:
            logger.warning(
                "search_timeout",
                ward=ward,
                start_date=start_date.isoformat()
            )
        except Exception as e:
            logger.error(
                "scrape_error",
                ward=ward,
                error=str(e)
            )
            raise

    async def _fill_search_form(
        self,
        start_date: date,
        end_date: date,
        ward: str,
        outcome: str
    ):
        """Fill in the planning search form"""
        try:
            # Ward selection
            ward_select = Select(self.driver.find_element(By.ID, "cboWardCode"))
            ward_select.select_by_visible_text(ward)

            # Date range - Decision Date
            date_from = self.driver.find_element(By.ID, "txtDateDecidedFrom")
            date_from.clear()
            date_from.send_keys(start_date.strftime("%d/%m/%Y"))

            date_to = self.driver.find_element(By.ID, "txtDateDecidedTo")
            date_to.clear()
            date_to.send_keys(end_date.strftime("%d/%m/%Y"))

            # Outcome/Status
            status_select = Select(self.driver.find_element(By.ID, "cboStatusCode"))
            if outcome == "Granted":
                status_select.select_by_visible_text("Decided - Grant")
            elif outcome == "Refused":
                status_select.select_by_visible_text("Decided - Refuse")

        except NoSuchElementException as e:
            logger.error("form_element_not_found", error=str(e))
            raise

    async def _parse_results_page(self) -> List[ScrapedApplication]:
        """Parse the current results page"""
        results = []

        try:
            # Wait for results table
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "searchresults"))
            )

            soup = BeautifulSoup(self.driver.page_source, "lxml")
            rows = soup.select("table.searchresults tr")

            for row in rows[1:]:  # Skip header row
                cells = row.find_all("td")
                if len(cells) < 5:
                    continue

                try:
                    app = await self._parse_result_row(cells)
                    if app:
                        results.append(app)
                except Exception as e:
                    logger.warning("row_parse_error", error=str(e))
                    continue

        except TimeoutException:
            logger.warning("no_results_found")

        return results

    async def _parse_result_row(
        self,
        cells: List
    ) -> Optional[ScrapedApplication]:
        """Parse a single result row into a ScrapedApplication"""
        try:
            # Extract basic info
            case_ref_link = cells[0].find("a")
            if not case_ref_link:
                return None

            case_reference = case_ref_link.get_text(strip=True)
            detail_url = case_ref_link.get("href")

            address = cells[1].get_text(strip=True)
            description = cells[2].get_text(strip=True)
            decision_text = cells[3].get_text(strip=True)
            date_text = cells[4].get_text(strip=True)

            # Parse decision date
            try:
                decision_date = datetime.strptime(date_text, "%d/%m/%Y").date()
            except ValueError:
                decision_date = date.today()

            # Determine outcome
            outcome = self._parse_outcome(decision_text)

            # Extract postcode from address
            postcode = self._extract_postcode(address)

            # Get additional details
            doc_urls = await self._get_document_urls(detail_url)

            return ScrapedApplication(
                case_reference=case_reference,
                address=address,
                ward=self._extract_ward_from_address(address),
                postcode=postcode,
                decision_date=decision_date,
                outcome=outcome,
                application_type=self._determine_application_type(description),
                description=description,
                decision_notice_url=doc_urls.get("decision_notice"),
                officer_report_url=doc_urls.get("officer_report"),
            )

        except Exception as e:
            logger.error("row_parse_failed", error=str(e))
            return None

    def _parse_outcome(self, text: str) -> str:
        """Parse the outcome from decision text"""
        text_lower = text.lower()
        if "grant" in text_lower or "approve" in text_lower:
            return Outcome.GRANTED.value
        elif "refuse" in text_lower or "reject" in text_lower:
            return Outcome.REFUSED.value
        elif "withdraw" in text_lower:
            return Outcome.WITHDRAWN.value
        else:
            return Outcome.PENDING.value

    def _extract_postcode(self, address: str) -> Optional[str]:
        """Extract UK postcode from address string"""
        # UK postcode regex
        pattern = r"([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})"
        match = re.search(pattern, address.upper())
        if match:
            postcode = match.group(1)
            # Normalise spacing
            if len(postcode.replace(" ", "")) >= 5:
                postcode = postcode.replace(" ", "")
                return postcode[:-3] + " " + postcode[-3:]
        return None

    def _extract_ward_from_address(self, address: str) -> str:
        """Attempt to determine ward from address"""
        address_lower = address.lower()

        ward_indicators = {
            "hampstead": "Hampstead Town",
            "belsize": "Belsize",
            "frognal": "Frognal",
            "swiss cottage": "Swiss Cottage",
            "west hampstead": "West Hampstead",
            "fortune green": "Fortune Green",
            "kilburn": "Kilburn",
            "gospel oak": "Gospel Oak",
            "kentish town": "Kentish Town",
            "camden town": "Camden Town",
            "highgate": "Highgate",
        }

        for indicator, ward in ward_indicators.items():
            if indicator in address_lower:
                return ward

        return "Unknown"

    def _determine_application_type(self, description: str) -> str:
        """Determine application type from description"""
        desc_lower = description.lower()

        if "full planning" in desc_lower:
            return "Full Planning"
        elif "householder" in desc_lower:
            return "Householder"
        elif "listed building" in desc_lower:
            return "Listed Building Consent"
        elif "conservation" in desc_lower:
            return "Conservation Area Consent"
        elif "prior approval" in desc_lower:
            return "Prior Approval"
        elif "lawful development" in desc_lower or "certificate" in desc_lower:
            return "Certificate of Lawfulness"
        elif "tree" in desc_lower:
            return "Tree Works"
        elif "advertisement" in desc_lower:
            return "Advertisement Consent"
        else:
            return "Planning Permission"

    async def _get_document_urls(
        self,
        detail_url: str
    ) -> Dict[str, Optional[str]]:
        """Get URLs for decision notice and officer report PDFs"""
        urls = {
            "decision_notice": None,
            "officer_report": None,
        }

        if not detail_url:
            return urls

        try:
            await self._rate_limit()

            full_url = urljoin(self.BASE_URL, detail_url)
            response = await self.http_client.get(full_url)

            if response.status_code != 200:
                return urls

            soup = BeautifulSoup(response.text, "lxml")

            # Look for document links
            doc_links = soup.find_all("a", href=True)
            for link in doc_links:
                href = link.get("href", "")
                text = link.get_text(strip=True).lower()

                if "decision" in text and ".pdf" in href.lower():
                    urls["decision_notice"] = urljoin(self.BASE_URL, href)
                elif "report" in text and ".pdf" in href.lower():
                    urls["officer_report"] = urljoin(self.BASE_URL, href)

        except Exception as e:
            logger.warning("document_url_fetch_failed", error=str(e))

        return urls

    async def _go_to_next_page(self) -> bool:
        """Navigate to next results page if available"""
        try:
            next_link = self.driver.find_element(
                By.XPATH,
                "//a[contains(text(), 'Next') or contains(@class, 'next')]"
            )
            if next_link and next_link.is_enabled():
                next_link.click()
                await asyncio.sleep(1)
                return True
        except NoSuchElementException:
            pass
        return False

    async def download_pdf(self, url: str) -> Optional[Path]:
        """Download a PDF document and return the local path"""
        if not url:
            return None

        try:
            await self._rate_limit()

            response = await self.http_client.get(url)
            if response.status_code != 200:
                return None

            # Generate filename from URL
            filename = os.path.basename(urlparse(url).path)
            if not filename.endswith(".pdf"):
                filename = f"document_{hash(url)}.pdf"

            filepath = self.download_dir / filename
            filepath.write_bytes(response.content)

            logger.debug("pdf_downloaded", path=str(filepath))
            return filepath

        except Exception as e:
            logger.error("pdf_download_failed", url=url, error=str(e))
            return None

    def classify_development_type(
        self,
        description: str
    ) -> Optional[DevelopmentType]:
        """Classify the development type from description"""
        desc_lower = description.lower()

        classifications = [
            (["rear extension", "back extension"], DevelopmentType.REAR_EXTENSION),
            (["side extension", "side return"], DevelopmentType.SIDE_EXTENSION),
            (["loft", "attic", "roof space"], DevelopmentType.LOFT_CONVERSION),
            (["dormer", "roof light", "rooflight"], DevelopmentType.DORMER_WINDOW),
            (["basement", "subterranean", "excavat", "cellar"], DevelopmentType.BASEMENT),
            (["roof extension", "roof terrace", "mansard"], DevelopmentType.ROOF_EXTENSION),
            (["change of use", "convert from", "convert to"], DevelopmentType.CHANGE_OF_USE),
            (["new build", "new dwelling", "erection of"], DevelopmentType.NEW_BUILD),
            (["demolit"], DevelopmentType.DEMOLITION),
            (["alter", "modif", "internal works"], DevelopmentType.ALTERATIONS),
            (["listed building"], DevelopmentType.LISTED_BUILDING),
            (["tree", "tpo"], DevelopmentType.TREE_WORKS),
            (["advert", "sign", "hoarding"], DevelopmentType.ADVERTISEMENT),
        ]

        for keywords, dev_type in classifications:
            if any(kw in desc_lower for kw in keywords):
                return dev_type

        return DevelopmentType.OTHER

    def identify_conservation_area(
        self,
        address: str,
        postcode: Optional[str]
    ) -> ConservationAreaStatus:
        """Identify conservation area from address/postcode"""
        # This would ideally use the Camden conservation area boundary data
        # For now, use address matching

        address_lower = address.lower()

        conservation_indicators = {
            "hampstead": ConservationAreaStatus.HAMPSTEAD,
            "belsize": ConservationAreaStatus.BELSIZE,
            "south hampstead": ConservationAreaStatus.SOUTH_HAMPSTEAD,
            "frognal": ConservationAreaStatus.REDINGTON_FROGNAL,
            "redington": ConservationAreaStatus.REDINGTON_FROGNAL,
            "netherhall": ConservationAreaStatus.FITZJOHNS_NETHERHALL,
            "fitzjohn": ConservationAreaStatus.FITZJOHNS_NETHERHALL,
            "swiss cottage": ConservationAreaStatus.SWISS_COTTAGE,
            "primrose hill": ConservationAreaStatus.PRIMROSE_HILL,
            "chalk farm": ConservationAreaStatus.CHALK_FARM,
            "camden town": ConservationAreaStatus.CAMDEN_TOWN,
            "kentish town": ConservationAreaStatus.KENTISH_TOWN,
            "bloomsbury": ConservationAreaStatus.BLOOMSBURY,
        }

        for indicator, ca in conservation_indicators.items():
            if indicator in address_lower:
                return ca

        return ConservationAreaStatus.NONE

    def convert_to_decision_create(
        self,
        scraped: ScrapedApplication,
        full_text: str
    ) -> PlanningDecisionCreate:
        """Convert scraped data to a PlanningDecisionCreate model"""
        return PlanningDecisionCreate(
            case_reference=scraped.case_reference,
            address=scraped.address,
            ward=scraped.ward,
            postcode=scraped.postcode,
            decision_date=scraped.decision_date,
            outcome=Outcome(scraped.outcome),
            application_type=scraped.application_type,
            development_type=self.classify_development_type(scraped.description),
            description=scraped.description,
            conservation_area=self.identify_conservation_area(
                scraped.address, scraped.postcode
            ),
            full_text=full_text,
            decision_notice_url=scraped.decision_notice_url,
            officer_report_url=scraped.officer_report_url,
        )
