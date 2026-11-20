"""Local development probe for Termoficare Oradea web client.

Runs custom_components/termoficare_oradea/api.py directly outside Home Assistant
so you can test your credentials and inspect real parsed invoice & balance data.

Usage:
    python tools/probe_termoficare.py <felhasználónév_vagy_email> <jelszó>
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import types
import aiohttp

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PKG_DIR = os.path.join(ROOT, "custom_components", "termoficare_oradea")

def load_api_module():
    """Load const and api without importing Home Assistant."""
    const_spec = importlib.util.spec_from_file_location("const", os.path.join(PKG_DIR, "const.py"))
    const_mod = importlib.util.module_from_spec(const_spec)
    # Mock Platform for const.py
    ha_const = types.ModuleType("homeassistant.const")
    ha_const.Platform = types.SimpleNamespace(SENSOR="sensor", BINARY_SENSOR="binary_sensor")
    sys.modules["homeassistant.const"] = ha_const
    const_spec.loader.exec_module(const_mod)

    # Register in sys.modules so api.py can do 'from .const import ...'
    sys.modules["termoficare_oradea"] = types.ModuleType("termoficare_oradea")
    sys.modules["termoficare_oradea.const"] = const_mod

    api_spec = importlib.util.spec_from_file_location("termoficare_oradea.api", os.path.join(PKG_DIR, "api.py"))
    api_mod = importlib.util.module_from_spec(api_spec)
    api_spec.loader.exec_module(api_mod)
    return api_mod

async def main():
    if len(sys.argv) < 3:
        print("\nHasználat:")
        print("  python tools/probe_termoficare.py <felhasználónév_vagy_email> <jelszó>\n")
        return

    username = sys.argv[1]
    password = sys.argv[2]

    api_mod = load_api_module()
    TermoficareApiClient = api_mod.TermoficareApiClient

    print(f"\n[1/3] Csatlakozás a termoficare-oradea.ro portálhoz mint '{username}'...")
    cookie_jar = aiohttp.CookieJar(unsafe=True)
    async with aiohttp.ClientSession(cookie_jar=cookie_jar) as session:
        client = TermoficareApiClient(username, password, session)

        print("[2/3] Bejelentkezési kísérlet...")
        success = await client.authenticate()
        if not success:
            print("\n❌ SIKERTELEN BEJELENTKEZÉS!")
            print("Kérlek ellenőrizd a felhasználónevet és a jelszót!")
            return

        print("✅ SIKERES BEJELENTKEZÉS!\n")
        print("[3/3] Számlaadatok és pénzügyi helyzet letöltése...")
        try:
            data = await client.get_data()
            print("\n" + "=" * 50)
            print("TERMOFICARE ORADEA — EREDMÉNY")
            print("=" * 50)
            print(f"Ügyfél neve:        {data.get('client_name')}")
            print(f"Fizetendő egyenleg: {data.get('total_balance')} RON")
            print(f"Kintlévőség:        {data.get('restant')} RON")
            print(f"Tartozás fennáll:   {'IGEN (Figyelmeztetés!)' if data.get('is_overdue') else 'NEM (Rendezve)'}")
            
            latest = data.get("latest_invoice", {})
            if latest:
                print("\n--- Legutóbbi Számla ---")
                print(f"Számlaszám:         {latest.get('nr_factura')}")
                print(f"Dátum:              {latest.get('data_factura')}")
                print(f"Szolgáltatás:       {latest.get('gestiune')}")
                print(f"Nettó összeg:       {latest.get('valoare_fara_tva')} RON")
                print(f"ÁFA összeg:         {latest.get('total_tva')} RON")
                print(f"Bruttó végösszeg:   {latest.get('total_factura')} RON")
                if latest.get("pdf_url"):
                    print(f"PDF letöltés:       {latest.get('pdf_url')}")
            else:
                print("\nNincs megjeleníthető számla a táblázatban.")

            invoices = data.get("invoices", [])
            print(f"\nÖsszesen {len(invoices)} számla található az előzményekben.")
            print("=" * 50)
        except Exception as e:
            print(f"Hiba a lekérdezés során: {e}")

if __name__ == "__main__":
    asyncio.run(main())
