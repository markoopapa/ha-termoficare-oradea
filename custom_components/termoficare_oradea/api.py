"""API Client for Termoficare Oradea online portal."""
import asyncio
import logging
import re
from typing import Any, Dict, List, Optional
import aiohttp
from bs4 import BeautifulSoup

from .const import BASE_URL, LOGIN_URL, FACTURI_URL, FISA_URL, CITIRI_URL

_LOGGER = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ro-RO,ro;q=0.9,hu-HU,hu;q=0.8,en-US;q=0.7,en;q=0.6",
}

def parse_amount(val: Any) -> float:
    """Parse Romanian currency format (e.g. 1.026,01) to float."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).strip()
    if not val_str or val_str == "-" or val_str == "&nbsp;":
        return 0.0
    try:
        # Remove thousand separator dots and replace decimal comma with dot
        cleaned = val_str.replace(" ", "").replace(".", "").replace(",", ".")
        # Match only valid number part
        m = re.search(r"[-+]?[0-9]*\.?[0-9]+", cleaned)
        if m:
            return float(m.group(0))
        return 0.0
    except (ValueError, TypeError):
        return 0.0

class TermoficareApiClient:
    """Interacts with the termoficare-oradea.ro portal."""

    def __init__(self, username: str, password: str, session: aiohttp.ClientSession):
        self.username = username
        self.password = password
        self.session = session
        self._is_logged_in = False

    async def authenticate(self) -> bool:
        """Authenticate with the portal."""
        # 1. Establish session and set GDPR consent cookie
        try:
            self.session.cookie_jar.update_cookies({"GDPR": "1"}, response_url=aiohttp.helpers.URL(BASE_URL))
        except Exception:
            pass

        try:
            # First hit login page to initialize PHP session
            async with self.session.get(LOGIN_URL, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15), ssl=False) as resp:
                await resp.text()

            # Submit login form
            payload = {
                "action": "login",
                "utilizator": self.username,
                "parola": self.password,
            }
            login_headers = {
                **HEADERS,
                "Referer": LOGIN_URL,
                "Content-Type": "application/x-www-form-urlencoded",
            }

            async with self.session.post(LOGIN_URL, data=payload, headers=login_headers, timeout=aiohttp.ClientTimeout(total=15), ssl=False) as resp:
                text = await resp.text()
                
                # Check for known failure message
                if "Combinatia utilizator/parola nu exista" in text or "contul este inactiv" in text:
                    _LOGGER.warning("Termoficare Oradea login failed: invalid username or password")
                    self._is_logged_in = False
                    return False
                
                # If we see login form again with error
                if '<form name="login"' in text and '<table' in text and 'class="critical"' in text:
                    _LOGGER.warning("Termoficare Oradea login rejected with critical alert")
                    self._is_logged_in = False
                    return False

                self._is_logged_in = True
                _LOGGER.info("Termoficare Oradea login successful for user: %s", self.username)
                return True

        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Termoficare Oradea connection error during auth: %s", err)
            raise

    async def _ensure_logged_in(self):
        """Ensure session is authenticated."""
        if not self._is_logged_in:
            success = await self.authenticate()
            if not success:
                raise ValueError("Autentificare eșuată la Termoficare Oradea")

    async def get_data(self) -> Dict[str, Any]:
        """Fetch invoices, balance, and account overview."""
        await self._ensure_logged_in()

        # Fetch both invoices and financial overview
        try:
            facturi_html = await self._fetch_url(FACTURI_URL)
            # If session timed out and redirected to login, re-authenticate once
            if 'form name="login"' in facturi_html:
                _LOGGER.debug("Session expired, re-authenticating...")
                await self.authenticate()
                facturi_html = await self._fetch_url(FACTURI_URL)

            fisa_html = await self._fetch_url(FISA_URL)
        except Exception as err:
            _LOGGER.error("Failed to fetch Termoficare pages: %s", err)
            raise

        invoices = self._parse_facturi(facturi_html)
        fisa_data = self._parse_fisa(fisa_html)

        # Merge results
        latest_inv = invoices[0] if invoices else {}
        total_balance = fisa_data.get("sold_final")
        
        # If sold_final was not found in fisa, fallback to total_factura or restant
        if total_balance is None:
            total_balance = fisa_data.get("restant", 0.0)
            if total_balance == 0.0 and latest_inv:
                total_balance = latest_inv.get("total_factura", 0.0)

        data = {
            "client_name": fisa_data.get("client_name") or self.username,
            "client_code": fisa_data.get("client_code"),
            "total_balance": round(total_balance or 0.0, 2),
            "sold_initial": fisa_data.get("sold_initial", 0.0),
            "restant": round(fisa_data.get("restant", 0.0), 2),
            "is_overdue": (fisa_data.get("restant", 0.0) > 0.01),
            "latest_invoice": latest_inv,
            "invoices": invoices[:10],  # Keep last 10 invoices in attributes
        }
        return data

    async def _fetch_url(self, url: str) -> str:
        """Fetch a page HTML with current session cookies."""
        async with self.session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=20), ssl=False) as resp:
            return await resp.text()

    def _parse_facturi(self, html: str) -> List[Dict[str, Any]]:
        """Parse invoices table from index.php?action=facturi."""
        invoices = []
        soup = BeautifulSoup(html, "html.parser")
        
        tables = soup.find_all("table")
        for table in tables:
            headers = [th.get_text(strip=True).upper() for th in table.find_all(["th", "td"])[:10]]
            # Look for table header containing FACTURA
            if any("NR FACTURA" in h or "NR. FACTURA" in h for h in headers) or any("TOTAL FACTURA" in h for h in headers):
                rows = table.find_all("tr")
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) >= 5:
                        texts = [c.get_text(strip=True) for c in cols]
                        # Skip header rows
                        if "NR FACTURA" in texts[0].upper() or "GESTIUNE" in texts[0].upper():
                            continue
                        
                        # Extract PDF link if available
                        pdf_link = None
                        pdf_tag = row.find("a", href=re.compile(r"\.pdf|get_pdf|download", re.I))
                        if pdf_tag and pdf_tag.get("href"):
                            href = pdf_tag["href"]
                            pdf_link = href if href.startswith("http") else f"{BASE_URL}/{href.lstrip('/')}"

                        # Structure: GESTIUNE, NR FACTURA, DATA FACTURA, TOTAL VALOARE, TOTAL TVA, TOTAL FACTURA
                        inv = {
                            "gestiune": texts[0] if len(texts) > 0 else "",
                            "nr_factura": texts[1] if len(texts) > 1 else "",
                            "data_factura": texts[2] if len(texts) > 2 else "",
                            "valoare_fara_tva": parse_amount(texts[3]) if len(texts) > 3 else 0.0,
                            "total_tva": parse_amount(texts[4]) if len(texts) > 4 else 0.0,
                            "total_factura": parse_amount(texts[5]) if len(texts) > 5 else 0.0,
                            "pdf_url": pdf_link,
                        }
                        if inv["nr_factura"] and inv["total_factura"] > 0:
                            invoices.append(inv)
                break
        return invoices

    def _parse_fisa(self, html: str) -> Dict[str, Any]:
        """Parse financial situation table from index.php?action=fisa."""
        res: Dict[str, Any] = {
            "sold_initial": 0.0,
            "sold_final": 0.0,
            "restant": 0.0,
            "client_name": None,
            "client_code": None,
        }

        # Look for Client name
        m_client = re.search(r"Client\s*</td>\s*<td[^>]*>([^\<]+)", html, re.I)
        if not m_client:
            m_client = re.search(r"Client[\s\:]+([A-Z0-9\.\-\_\s]{3,40})", html, re.I)
        if m_client:
            res["client_name"] = m_client.group(1).strip()

        # Look for Sold initial (often followed by date e.g. Sold initial 03.02.2026 16.227,92)
        m_initial = re.search(r"Sold\s*initial(?:\s*<[^>]+>)*\s*(?:\d{2}\.\d{2}\.\d{4})?[^\d]*([\d\.\,]+)", html, re.I)
        if m_initial:
            res["sold_initial"] = parse_amount(m_initial.group(1))

        # Look for SOLD FINAL (table footer or text: SOLD FINAL 04.08.2026 1.113,38)
        m_final = re.search(r"SOLD\s*FINAL[^\<]*<\/td>[\s\S]*?<td[^>]*>[\s\S]*?([\d\.\,]+)\s*<\/td>", html, re.I)
        if not m_final:
            m_final = re.search(r"SOLD\s*FINAL(?:\s*<[^>]+>)*\s*(?:\d{2}\.\d{2}\.\d{4})?[^\d]*([\d\.\,]+)", html, re.I)
        if m_final:
            res["sold_final"] = parse_amount(m_final.group(1))

        # Look for RESTANT
        restant_matches = re.findall(r"RESTANT[\s\S]*?<td[^>]*>[\s\S]*?([\d\.\,]+)\s*<\/td>", html, re.I)
        if restant_matches:
            total_restant = sum(parse_amount(r) for r in restant_matches)
            res["restant"] = total_restant
        else:
            # Fallback regex
            m_restant = re.search(r"RESTANT[^\d]*([\d\.\,]+)", html, re.I)
            if m_restant:
                res["restant"] = parse_amount(m_restant.group(1))

        return res
