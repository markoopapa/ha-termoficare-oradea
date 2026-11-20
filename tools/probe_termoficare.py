"""Local development probe for Termoficare Oradea web client.

Runs custom_components/termoficare_oradea/api.py directly outside Home Assistant
so you can test your credentials and inspect real parsed invoice & balance data.

Usage:
    python tools/probe_termoficare.py <utilizator_sau_email> <parola>
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
    ha_const = types.ModuleType("homeassistant.const")
    ha_const.Platform = types.SimpleNamespace(SENSOR="sensor", BINARY_SENSOR="binary_sensor")
    sys.modules["homeassistant.const"] = ha_const
    const_spec.loader.exec_module(const_mod)

    sys.modules["termoficare_oradea"] = types.ModuleType("termoficare_oradea")
    sys.modules["termoficare_oradea.const"] = const_mod

    api_spec = importlib.util.spec_from_file_location("termoficare_oradea.api", os.path.join(PKG_DIR, "api.py"))
    api_mod = importlib.util.module_from_spec(api_spec)
    api_spec.loader.exec_module(api_mod)
    return api_mod

async def main():
    if len(sys.argv) < 3:
        print("\nUtilizare:")
        print("  python tools/probe_termoficare.py <utilizator_sau_email> <parola>\n")
        return

    username = sys.argv[1]
    password = sys.argv[2]

    api_mod = load_api_module()
    TermoficareApiClient = api_mod.TermoficareApiClient

    print(f"\n[1/3] Conectare la portalul termoficare-oradea.ro ca '{username}'...")
    cookie_jar = aiohttp.CookieJar(unsafe=True)
    async with aiohttp.ClientSession(cookie_jar=cookie_jar) as session:
        client = TermoficareApiClient(username, password, session)

        print("[2/3] Autentificare în curs...")
        success = await client.authenticate()
        if not success:
            print("\n❌ AUTENTIFICARE EȘUATĂ!")
            print("Verificați dacă utilizatorul și parola sunt corecte!")
            return

        print("✅ AUTENTIFICARE CU SUCCES!\n")
        print("[3/3] Preluare situație financiară și facturi...")
        try:
            data = await client.get_data()
            print("\n" + "=" * 55)
            print("TERMOFICARE ORADEA — SITUAȚIE CLIENT")
            print("=" * 55)
            print(f"Nume client:        {data.get('client_name')}")
            print(f"Sold total de plată:{data.get('total_balance')} RON")
            print(f"Sold restant:       {data.get('restant')} RON")
            print(f"Restant existent:   {'DA (Atenție debite restante!)' if data.get('is_overdue') else 'NU (Situație la zi)'}")
            
            latest = data.get("latest_invoice", {})
            if latest:
                print("\n--- Detalii Ultima Factură ---")
                print(f"Număr factură:      {latest.get('nr_factura')}")
                print(f"Data facturii:      {latest.get('data_factura')}")
                print(f"Gestiune:           {latest.get('gestiune')}")
                print(f"Valoare fără TVA:   {latest.get('valoare_fara_tva')} RON")
                print(f"Total TVA:          {latest.get('total_tva')} RON")
                print(f"Total factură:      {latest.get('total_factura')} RON")
                if latest.get("pdf_url"):
                    print(f"Descărcare PDF:     {latest.get('pdf_url')}")
            else:
                print("\nNu există facturi înregistrate.")

            invoices = data.get("invoices", [])
            print(f"\nTotal facturi în istoric: {len(invoices)}")
            print("=" * 55)
        except Exception as e:
            print(f"Eroare la preluarea datelor: {e}")

if __name__ == "__main__":
    asyncio.run(main())
