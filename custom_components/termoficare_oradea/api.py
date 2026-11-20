"""API Client for Termoficare Oradea online portal."""
import asyncio
from datetime import datetime
import logging
import re
from typing import Any, Dict, List, Optional
import aiohttp
from bs4 import BeautifulSoup

from .const import BASE_URL, LOGIN_URL, FACTURI_URL, FISA_URL, CLIENTI_URL, CITIRI_URL

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
    val_str = re.sub(r"[^\d\,\.\-]", "", val_str)
    if not val_str:
        return 0.0
    if "." in val_str and "," in val_str:
        val_str = val_str.replace(".", "").replace(",", ".")
    elif "," in val_str:
        val_str = val_str.replace(",", ".")
    try:
        return float(val_str)
    except ValueError:
        return 0.0

class TermoficareApiClient:
    """Handles communication and session with termoficare-oradea.ro."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str):
        self.session = session
        self.username = username
        self.password = password
        self._is_logged_in = False

    async def authenticate(self) -> bool:
        """Authenticate user against portal."""
        try:
            # 1. Warm up cookie jar with GDPR acceptance
            self.session.cookie_jar.update_cookies(
                {"GDPR": "1"},
                response_url=aiohttp.client.URL(BASE_URL)
            )

            # 2. Visit login page
            async with self.session.get(
                LOGIN_URL,
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=20),
                ssl=False
            ) as resp:
                await resp.text()

            # 3. Post login form
            payload = {
                "user": self.username,
                "parola": self.password,
                "action": "login",
            }
            async with self.session.post(
                LOGIN_URL,
                data=payload,
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=20),
                allow_redirects=True,
                ssl=False
            ) as resp:
                text = await resp.text()

                # Check for bad credentials warning
                if "Parola sau utilizator gresit" in text or "Utilizator inexistent" in text:
                    _LOGGER.warning("Termoficare Oradea login failed: utilizator sau parola gresita")
                    self._is_logged_in = False
                    return False
                
                # Check for critical alert on login form
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

    async def _fetch_url(self, url: str) -> str:
        """Fetch a page HTML with current session cookies."""
        async with self.session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=20), ssl=False) as resp:
            return await resp.text()

    async def _fetch_client_info(self) -> Dict[str, Any]:
        """Fetch attached contracts page (clienti_ace) to warm up session and extract contract details."""
        info: Dict[str, Any] = {}
        try:
            html = await self._fetch_url(CLIENTI_URL)
            if 'form name="login"' in html:
                await self.authenticate()
                html = await self._fetch_url(CLIENTI_URL)

            soup = BeautifulSoup(html, "html.parser")
            for tr in soup.find_all("tr"):
                tds = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(tds) >= 2:
                    for text in tds:
                        if re.search(r"P\s*\d+\s*\d+", text):
                            info["client_code"] = text.strip()
                        elif len(text) > 5 and any(n in text.upper() for n in ["SZEKELY", "MARK"]):
                            info["client_name"] = text.strip()
        except Exception as err:
            _LOGGER.debug("Could not parse clienti_ace: %s", err)
        return info

    async def _fetch_facturi_data(self) -> str:
        """Fetch invoices page and submit date/contract filter if form is present."""
        html = await self._fetch_url(FACTURI_URL)
        if 'form name="login"' in html:
            await self.authenticate()
            html = await self._fetch_url(FACTURI_URL)

        # If invoices table is already rendered, return directly
        if "tbldata" in html and ("NR FACTURA" in html.upper() or "TOTAL FACTURA" in html.upper()):
            return html

        # Check for filter form with id_client_ace
        soup = BeautifulSoup(html, "html.parser")
        select_ace = soup.find("select", {"name": "id_client_ace"}) or soup.find("select", {"id": "id_client_ace"})
        if select_ace:
            options = select_ace.find_all("option")
            opt_val = None
            for opt in options:
                v = opt.get("value")
                if v and v != "0":
                    opt_val = v
                    break
            if not opt_val and options:
                opt_val = options[0].get("value")

            if opt_val:
                hash_val = ""
                m_hash = re.search(rf'optionsHash\[["\']?{re.escape(str(opt_val))}["\']?\]\s*=\s*["\']([^"\']+)["\']', html)
                if not m_hash:
                    m_hash = re.search(rf'["\']?{re.escape(str(opt_val))}["\']?\s*:\s*["\']([^"\']+)["\']', html)
                if m_hash:
                    hash_val = m_hash.group(1)

                now = datetime.now()
                post_data = {
                    "id_client_ace": opt_val,
                    "hash": hash_val,
                    "start_zi": "01",
                    "start_luna": "01",
                    "start_an": str(now.year - 2),
                    "start": f"01.01.{now.year - 2}",
                    "stop_zi": "31",
                    "stop_luna": "12",
                    "stop_an": str(now.year + 1),
                    "stop": f"31.12.{now.year + 1}",
                }
                _LOGGER.debug("Submitting facturi filter POST: %s", post_data)
                try:
                    async with self.session.post(
                        FACTURI_URL,
                        data=post_data,
                        headers=HEADERS,
                        timeout=aiohttp.ClientTimeout(total=20),
                        ssl=False,
                    ) as resp:
                        return await resp.text()
                except Exception as err:
                    _LOGGER.warning("Error posting facturi filter: %s", err)

        return html

    async def _fetch_fisa_data(self) -> str:
        """Fetch financial situation page and submit filter if form is present."""
        html = await self._fetch_url(FISA_URL)
        if 'form name="login"' in html:
            await self.authenticate()
            html = await self._fetch_url(FISA_URL)

        if "SOLD FINAL" in html.upper() or "RESTANT" in html.upper():
            return html

        soup = BeautifulSoup(html, "html.parser")
        select_ace = soup.find("select", {"name": "id_client_ace"}) or soup.find("select", {"id": "id_client_ace"})
        if select_ace:
            options = select_ace.find_all("option")
            opt_val = None
            for opt in options:
                v = opt.get("value")
                if v and v != "0":
                    opt_val = v
                    break
            if not opt_val and options:
                opt_val = options[0].get("value")

            if opt_val:
                hash_val = ""
                m_hash = re.search(rf'optionsHash\[["\']?{re.escape(str(opt_val))}["\']?\]\s*=\s*["\']([^"\']+)["\']', html)
                if not m_hash:
                    m_hash = re.search(rf'["\']?{re.escape(str(opt_val))}["\']?\s*:\s*["\']([^"\']+)["\']', html)
                if m_hash:
                    hash_val = m_hash.group(1)

                now = datetime.now()
                post_data = {
                    "id_client_ace": opt_val,
                    "hash": hash_val,
                    "start_zi": "01",
                    "start_luna": "01",
                    "start_an": str(now.year - 2),
                    "start": f"01.01.{now.year - 2}",
                    "stop_zi": "31",
                    "stop_luna": "12",
                    "stop_an": str(now.year + 1),
                    "stop": f"31.12.{now.year + 1}",
                }
                try:
                    async with self.session.post(
                        FISA_URL,
                        data=post_data,
                        headers=HEADERS,
                        timeout=aiohttp.ClientTimeout(total=20),
                        ssl=False,
                    ) as resp:
                        return await resp.text()
                except Exception as err:
                    _LOGGER.warning("Error posting fisa filter: %s", err)

        return html

    async def get_data(self) -> Dict[str, Any]:
        """Fetch invoices, balance, and account overview."""
        await self._ensure_logged_in()

        client_info = await self._fetch_client_info()

        # Fetch both invoices and financial overview
        try:
            facturi_html = await self._fetch_facturi_data()
            fisa_html = await self._fetch_fisa_data()
        except Exception as err:
            _LOGGER.error("Failed to fetch Termoficare pages: %s", err)
            raise

        invoices = self._parse_facturi(facturi_html)
        fisa_data = self._parse_fisa(fisa_html)

        # Merge results
        latest_inv = invoices[0] if invoices else {}
        total_balance = fisa_data.get("sold_final")
        
        # If sold_final was not found in fisa, fallback to restant or latest_invoice
        if total_balance is None:
            total_balance = fisa_data.get("restant", 0.0)
            if total_balance == 0.0 and latest_inv:
                total_balance = latest_inv.get("total_factura", 0.0)

        data = {
            "client_name": client_info.get("client_name") or fisa_data.get("client_name") or self.username,
            "client_code": client_info.get("client_code") or fisa_data.get("client_code"),
            "total_balance": round(total_balance or 0.0, 2),
            "sold_initial": fisa_data.get("sold_initial", 0.0),
            "restant": round(fisa_data.get("restant", 0.0), 2),
            "is_overdue": (fisa_data.get("restant", 0.0) > 0.01),
            "latest_invoice": latest_inv,
            "invoices": invoices[:10],
        }
        return data

    def _parse_facturi(self, html: str) -> List[Dict[str, Any]]:
        """Parse invoices table from index.php?action=facturi."""
        invoices = []
        soup = BeautifulSoup(html, "html.parser")
        
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            if not rows:
                continue

            header_text = " ".join([th.get_text(strip=True).upper() for th in table.find_all(["th", "td"])[:12]])
            if "FACTURA" in header_text or "TOTAL VALOARE" in header_text or "NR. FACTURA" in header_text:
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) >= 4:
                        texts = [c.get_text(strip=True) for c in cols]
                        first_col = texts[0].upper()
                        if any(h in first_col for h in ["GESTIUNE", "NR FACTURA", "NR.", "SERIE", "DATA"]):
                            continue

                        pdf_link = None
                        pdf_tag = row.find("a", href=re.compile(r"\.pdf|get_pdf|download|action=pdf|id_factura", re.I))
                        if pdf_tag and pdf_tag.get("href"):
                            href = pdf_tag["href"]
                            pdf_link = href if href.startswith("http") else f"{BASE_URL}/{href.lstrip('/')}"

                        gestiune = ""
                        nr_fact = ""
                        data_fact = ""
                        val_fara_tva = 0.0
                        tva = 0.0
                        total_fact = 0.0

                        if len(texts) >= 6:
                            gestiune = texts[0]
                            nr_fact = texts[1]
                            data_fact = texts[2]
                            val_fara_tva = parse_amount(texts[3])
                            tva = parse_amount(texts[4])
                            total_fact = parse_amount(texts[5])
                        elif len(texts) >= 4:
                            nr_fact = texts[0]
                            data_fact = texts[1]
                            val_fara_tva = parse_amount(texts[2])
                            total_fact = parse_amount(texts[3])

                        if nr_fact and total_fact > 0:
                            invoices.append({
                                "gestiune": gestiune,
                                "nr_factura": nr_fact,
                                "data_factura": data_fact,
                                "valoare_fara_tva": val_fara_tva,
                                "total_tva": tva,
                                "total_factura": total_fact,
                                "pdf_url": pdf_link,
                            })
                if invoices:
                    break
        return invoices

    def _parse_fisa(self, html: str) -> Dict[str, Any]:
        """Parse financial situation table from index.php?action=fisa_financiara."""
        res: Dict[str, Any] = {
            "sold_initial": 0.0,
            "sold_final": 0.0,
            "restant": 0.0,
            "client_name": None,
            "client_code": None,
        }

        m_client = re.search(r"Client\s*</td>\s*<td[^>]*>([^\<]+)", html, re.I)
        if not m_client:
            m_client = re.search(r"Client[\s\:]+([A-Z0-9\.\-\_\s]{3,40})", html, re.I)
        if m_client:
            res["client_name"] = m_client.group(1).strip()

        m_code = re.search(r"(?:Contract|Cod client)[\s\:]+([A-Z0-9\.\-\_\s]{3,30})", html, re.I)
        if m_code:
            res["client_code"] = m_code.group(1).strip()

        m_initial = re.search(r"Sold\s*initial(?:\s*<[^>]+>)*\s*(?:\d{2}\.\d{2}\.\d{4})?[^\d]*([\d\.\,]+)", html, re.I)
        if m_initial:
            res["sold_initial"] = parse_amount(m_initial.group(1))

        m_final = re.search(r"SOLD\s*FINAL[^\<]*<\/td>[\s\S]*?<td[^>]*>[\s\S]*?([\d\.\,]+)\s*<\/td>", html, re.I)
        if not m_final:
            m_final = re.search(r"SOLD\s*FINAL(?:\s*<[^>]+>)*\s*(?:\d{2}\.\d{2}\.\d{4})?[^\d]*([\d\.\,]+)", html, re.I)
        if m_final:
            res["sold_final"] = parse_amount(m_final.group(1))

        restant_matches = re.findall(r"RESTANT[\s\S]*?<td[^>]*>[\s\S]*?([\d\.\,]+)\s*<\/td>", html, re.I)
        if restant_matches:
            total_restant = sum(parse_amount(r) for r in restant_matches)
            res["restant"] = total_restant
        else:
            m_restant = re.search(r"RESTANT[^\d]*([\d\.\,]+)", html, re.I)
            if m_restant:
                res["restant"] = parse_amount(m_restant.group(1))

        return res
