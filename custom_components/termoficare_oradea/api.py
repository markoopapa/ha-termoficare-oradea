"""API Client for Termoficare Oradea online portal."""
import asyncio
from datetime import datetime
import logging
import re
from typing import Any, Dict, List, Optional
import aiohttp
from bs4 import BeautifulSoup

from .const import BASE_URL, LOGIN_URL, FACTURI_URL, FACTURI_STEP2_URL, FISA_URL, CLIENTI_URL, CITIRI_URL, PLATA_URL

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

    def __init__(self, username: str = "", password: str = "", session: Optional[aiohttp.ClientSession] = None, **kwargs):
        self.username = username or kwargs.get("username", "")
        self.password = password or kwargs.get("password", "")
        self.session = session or kwargs.get("session")
        if not self.session and "session" in kwargs:
            self.session = kwargs["session"]
        self._is_logged_in = False

    async def authenticate(self) -> bool:
        """Authenticate user against portal."""
        try:
            # 1. Warm up cookie jar with GDPR acceptance
            self.session.cookie_jar.update_cookies(
                {"GDPR": "1"},
                response_url=aiohttp.client.URL(BASE_URL)
            )

            # 2. Visit login page to obtain initial session cookie
            async with self.session.get(
                LOGIN_URL,
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=20),
                ssl=False
            ) as resp:
                await resp.text()

            # 3. Post login form with correct Romanian field names (utilizator & parola)
            payload = {
                "action": "login",
                "utilizator": self.username,
                "user": self.username,
                "parola": self.password,
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
                if '<form name="login"' in text and 'class="critical"' in text:
                    m_crit = re.search(r'class=["\']?critical["\']?[^>]*>([\s\S]*?)</table>', text, re.I)
                    err_msg = ""
                    if m_crit:
                        err_soup = BeautifulSoup(m_crit.group(1), "html.parser")
                        err_msg = err_soup.get_text(" ", strip=True)
                    _LOGGER.warning("Termoficare Oradea login rejected with alert: %s", err_msg)
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

        # Check for filter form with id_client_ace (select or input)
        soup = BeautifulSoup(html, "html.parser")
        elem_ace = soup.find(attrs={"name": "id_client_ace"}) or soup.find(attrs={"id": "id_client_ace"})
        if elem_ace:
            opt_val = None
            if elem_ace.name == "select":
                options = elem_ace.find_all("option")
                for opt in options:
                    v = opt.get("value")
                    if v and v != "0":
                        opt_val = v
                        break
                if not opt_val and options:
                    opt_val = options[0].get("value")
            else:
                opt_val = elem_ace.get("value")

            if opt_val:
                hash_val = ""
                m_hash = re.search(rf'optionsHash\[["\']?{re.escape(str(opt_val))}["\']?\]\s*=\s*["\']([^"\']+)["\']', html)
                if not m_hash:
                    m_hash = re.search(rf'["\']?{re.escape(str(opt_val))}["\']?\s*:\s*["\']([^"\']+)["\']', html)
                if m_hash:
                    hash_val = m_hash.group(1)

                form = elem_ace.find_parent("form") or soup.find("form")
                post_data = {}
                if form:
                    for inp in form.find_all("input"):
                        n = inp.get("name")
                        if n:
                            post_data[n] = inp.get("value", "")

                now = datetime.now()
                start_val = post_data.get("start") or "01.09.2013"
                stop_val = post_data.get("stop") or f"{now.day:02d}.{now.month:02d}.{now.year}"
                post_data.update({
                    "action": "facturi",
                    "step": "2",
                    "id_client_ace": opt_val,
                    "hash": hash_val,
                    "start_zi": "01",
                    "start_luna": "09",
                    "start_an": "2013",
                    "start": start_val,
                    "stop_zi": f"{now.day:02d}",
                    "stop_luna": f"{now.month:02d}",
                    "stop_an": str(now.year),
                    "stop": stop_val,
                })
                _LOGGER.debug("Submitting facturi filter POST to %s: %s", FACTURI_STEP2_URL, post_data)
                try:
                    async with self.session.post(
                        FACTURI_STEP2_URL,
                        data=post_data,
                        headers=HEADERS,
                        timeout=aiohttp.ClientTimeout(total=20),
                        ssl=False,
                    ) as resp:
                        res_text = await resp.text()
                        if "NR FACTURA" in res_text.upper():
                            return res_text
                except Exception as err:
                    _LOGGER.warning("Error posting facturi filter to step2: %s", err)

                try:
                    async with self.session.post(
                        FACTURI_URL,
                        data=post_data,
                        headers=HEADERS,
                        timeout=aiohttp.ClientTimeout(total=20),
                        ssl=False,
                    ) as resp:
                        res_text = await resp.text()
                        if "NR FACTURA" in res_text.upper():
                            return res_text
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
        elem_ace = soup.find(attrs={"name": "id_client_ace"}) or soup.find(attrs={"id": "id_client_ace"})
        if elem_ace:
            opt_val = None
            if elem_ace.name == "select":
                options = elem_ace.find_all("option")
                for opt in options:
                    v = opt.get("value")
                    if v and v != "0":
                        opt_val = v
                        break
                if not opt_val and options:
                    opt_val = options[0].get("value")
            else:
                opt_val = elem_ace.get("value")

            if opt_val:
                hash_val = ""
                m_hash = re.search(rf'optionsHash\[["\']?{re.escape(str(opt_val))}["\']?\]\s*=\s*["\']([^"\']+)["\']', html)
                if not m_hash:
                    m_hash = re.search(rf'["\']?{re.escape(str(opt_val))}["\']?\s*:\s*["\']([^"\']+)["\']', html)
                if m_hash:
                    hash_val = m_hash.group(1)

                form = elem_ace.find_parent("form") or soup.find("form")
                post_data = {}
                if form:
                    for inp in form.find_all("input"):
                        n = inp.get("name")
                        if n:
                            post_data[n] = inp.get("value", "")

                now = datetime.now()
                post_data.update({
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
                })
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

    async def _fetch_plata_data(self) -> str:
        """Fetch online payment page (index.php?action=plata) to get active unpaid invoices."""
        try:
            html = await self._fetch_url(PLATA_URL)
            if 'form name="login"' in html:
                await self.authenticate()
                html = await self._fetch_url(PLATA_URL)
            return html
        except Exception as err:
            _LOGGER.warning("Error fetching plata page: %s", err)
            return ""

    def _parse_plata(self, html: str) -> Dict[str, Any]:
        """Parse unpaid invoices and balance from index.php?action=plata."""
        res: Dict[str, Any] = {
            "unpaid_invoices": [],
            "total_unpaid": 0.0,
        }
        if not html:
            return res

        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            if not rows:
                continue

            header_cols = [th.get_text(strip=True).upper() for th in table.find_all(["th", "td"])[:10]]
            header_text = " ".join(header_cols)
            if "RESTANTA" in header_text or "FACTURI RESTANTE" in html.upper():
                for row in rows:
                    tds = row.find_all("td")
                    if len(tds) >= 4:
                        texts = [td.get_text(strip=True) for td in tds]
                        first = texts[0].upper()
                        if any(h in first for h in ["GESTIUNE", "TOTAL", "REST DE PLATA", "SE RATEAZA"]):
                            continue
                        nr_fact = texts[1] if len(texts) > 1 else ""
                        if re.search(r"\d{4,}", nr_fact):
                            data_fact = texts[2] if len(texts) > 2 else ""
                            tot_init = parse_amount(texts[3]) if len(texts) > 3 else 0.0
                            restant = parse_amount(texts[4]) if len(texts) > 4 else tot_init
                            res["unpaid_invoices"].append({
                                "gestiune": texts[0],
                                "nr_factura": nr_fact,
                                "data_factura": data_fact,
                                "total_initial": tot_init,
                                "restanta": restant,
                            })

        m_rest = re.search(r"Rest de plat[aă][^\d]*([\d\.\,]+)", html, re.I)
        if m_rest:
            res["total_unpaid"] = parse_amount(m_rest.group(1))
        elif res["unpaid_invoices"]:
            res["total_unpaid"] = sum(inv["restanta"] for inv in res["unpaid_invoices"])

        return res

    async def get_data(self) -> Dict[str, Any]:
        """Fetch invoices, balance, and account overview."""
        await self._ensure_logged_in()

        client_info = await self._fetch_client_info()

        # 1. Invoices list from facturi (with step=2)
        try:
            facturi_html = await self._fetch_facturi_data()
        except Exception as err:
            _LOGGER.warning("Failed to fetch facturi: %s", err)
            facturi_html = ""
        invoices = self._parse_facturi(facturi_html)

        # 2. Unpaid bills and balance from plata online
        plata_html = await self._fetch_plata_data()
        plata_data = self._parse_plata(plata_html)

        # 3. Financial overview from fisa_financiara
        try:
            fisa_html = await self._fetch_fisa_data()
            fisa_data = self._parse_fisa(fisa_html)
        except Exception as err:
            _LOGGER.debug("Failed to fetch fisa_financiara: %s", err)
            fisa_data = {}

        if not invoices and fisa_data.get("invoices"):
            invoices = fisa_data["invoices"]

        # Merge results
        latest_inv = invoices[0] if invoices else {}

        # Ground truth balance: plata_data reflects active invoices ready for payment
        total_balance = plata_data.get("total_unpaid", 0.0)
        if total_balance == 0.0 and fisa_data.get("sold_final") is not None:
            total_balance = fisa_data.get("sold_final", 0.0)

        restant = plata_data.get("total_unpaid", 0.0)
        if restant == 0.0 and fisa_data.get("restant") is not None:
            restant = fisa_data.get("restant", 0.0)

        data = {
            "client_name": client_info.get("client_name") or fisa_data.get("client_name") or self.username,
            "client_code": client_info.get("client_code") or fisa_data.get("client_code"),
            "total_balance": round(total_balance, 2),
            "sold_initial": fisa_data.get("sold_initial", 0.0),
            "restant": round(restant, 2),
            "is_overdue": (restant > 0.01),
            "latest_invoice": latest_inv,
            "invoices": invoices[:15],
            "unpaid_invoices": plata_data.get("unpaid_invoices", []),
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

            header_cols = [th.get_text(strip=True).upper() for th in rows[0].find_all(["th", "td"])]
            header_text = " ".join(header_cols)
            if "FACTURA" in header_text or "NR FACTURA" in header_text:
                nr_idx = 0
                data_idx = 1
                val_idx = 2
                tva_idx = 3
                tot_idx = 4
                gest_idx = None
                
                for i, h in enumerate(header_cols):
                    if "GESTIUNE" in h:
                        gest_idx = i
                    elif "NR" in h and "FACTURA" in h:
                        nr_idx = i
                    elif "DATA" in h:
                        data_idx = i
                    elif "VALOARE" in h:
                        val_idx = i
                    elif "TVA" in h:
                        tva_idx = i
                    elif "TOTAL" in h and "FACTURA" in h:
                        tot_idx = i

                for row in rows[1:]:
                    cols = row.find_all("td")
                    if len(cols) > max(nr_idx, data_idx, tot_idx):
                        texts = [c.get_text(strip=True) for c in cols]
                        nr_fact = texts[nr_idx]
                        if not re.search(r"\d{4,}", nr_fact):
                            continue

                        data_fact = texts[data_idx]
                        val_fara_tva = parse_amount(texts[val_idx]) if val_idx < len(texts) else 0.0
                        tva = parse_amount(texts[tva_idx]) if tva_idx < len(texts) else 0.0
                        total_fact = parse_amount(texts[tot_idx]) if tot_idx < len(texts) else 0.0
                        gestiune = texts[gest_idx] if gest_idx is not None and gest_idx < len(texts) else "ENERGIE TERMICA"

                        pdf_link = None
                        pdf_tag = row.find("a", href=re.compile(r"\.pdf|get_pdf|download|action=pdf|id_factura", re.I))
                        if pdf_tag and pdf_tag.get("href"):
                            href = pdf_tag["href"]
                            pdf_link = href if href.startswith("http") else f"{BASE_URL}/{href.lstrip('/')}"

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

        # Also parse invoices from fisa table if present
        fisa_invoices = []
        soup = BeautifulSoup(html, "html.parser")
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) >= 4:
                texts = [td.get_text(strip=True) for td in tds]
                first = texts[0].upper()
                if any(h in first for h in ["GESTIUNE", "NR FACTURA", "CLIENT", "SOLD", "TOTAL", "TIP"]):
                    continue
                if len(texts) >= 4 and texts[1].isdigit() and ("." in texts[2] or "/" in texts[2]):
                    gestiune = texts[0]
                    nr_fact = texts[1]
                    data_fact = texts[2]
                    tot_fact = parse_amount(texts[3])
                    if tot_fact > 0:
                        pdf_link = None
                        pdf_tag = tr.find("a", href=re.compile(r"\.pdf|get_pdf|download|action=pdf|id_factura", re.I))
                        if pdf_tag and pdf_tag.get("href"):
                            href = pdf_tag["href"]
                            pdf_link = href if href.startswith("http") else f"{BASE_URL}/{href.lstrip('/')}"
                        fisa_invoices.append({
                            "gestiune": gestiune,
                            "nr_factura": nr_fact,
                            "data_factura": data_fact,
                            "valoare_fara_tva": tot_fact,
                            "total_tva": 0.0,
                            "total_factura": tot_fact,
                            "pdf_url": pdf_link,
                        })
        res["invoices"] = fisa_invoices

        return res
