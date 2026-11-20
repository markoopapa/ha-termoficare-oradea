# Termoficare Oradea — Home Assistant Integráció (HACS)

Egyedi Home Assistant komponens a **Termoficare Oradea S.A.** távhőszolgáltató számlaadatainak, aktuális egyenlegének és kintlévőségeinek automatikus lekérdezésére közvetlenül a hivatalos webes portálról (`https://termoficare-oradea.ro`).

![Termoficare Oradea](custom_components/termoficare_oradea/brand/logo.png)

---

## Jellemzők

- **Automatikus bejelentkezés**: Közvetlenül kapcsolódik a `termoficare-oradea.ro` ügyfélportálhoz (nem igényel külső köztes szolgáltatást, mint a Pago).
- **Fizetendő egyenleg (Sold Total)**: Folyamatosan mutatja a fennálló fizetendő összeget (`sensor.termoficare_oradea_fizetendo_egyenleg`).
- **Utolsó számla részletei**: Számla összege, számlaszám, kibocsátási dátum, áfa, és közvetlen letöltési PDF link.
- **Kintlévőség / Tartozás figyelés**: Bináris szenzor (`binary_sensor.termoficare_oradea_tartozas_kintlevoseg`), ami azonnal jelez, ha lejárt számla van.
- **Többnyelvű támogatás**: Magyar (HU), Román (RO) és Angol (EN) felhasználói felület.
- **HACS kompatibilis**: Telepíthető közvetlenül HACS Egyéni adattárként vagy manuálisan a `/config/custom_components` mappába másolva.

---

## Létrejövő Entitások

| Entitás | Típus | Leírás |
|---|---|---|
| `sensor.termoficare_oradea_fizetendo_egyenleg` | Szenzor (MONETARY, RON) | Aktuális teljes fizetendő egyenleg (Sold de plată) |
| `sensor.termoficare_oradea_utolso_szamla` | Szenzor (MONETARY, RON) | Utolsó kiállított számla végösszege |
| `sensor.termoficare_oradea_utolso_szamlaszam` | Szenzor | Utolsó számla sorszáma |
| `sensor.termoficare_oradea_utolso_szamla_kibocsatasa` | Szenzor | Utolsó számla kiállításának dátuma |
| `binary_sensor.termoficare_oradea_tartozas_kintlevoseg` | Bináris szenzor (PROBLEM) | `Be` (On) ha lejárt tartozás vagy kifizetetlen számla van |

---

## Telepítés

### 1. Módszer: HACS Egyéni Adattárként (Ajánlott)

1. A Home Assistantban nyisd meg a **HACS** (vagy Közösségi Áruház) menüt.
2. Kattints a jobb felső sarokban található **3 pontra** és válaszd az **Egyéni adattárak** (Custom repositories) lehetőséget.
3. Másold be a GitHub tárhely URL-jét:
   `https://github.com/markoopapa/ha-termoficare-oradea`
4. Kategóriának válaszd: **Integráció** (Integration).
5. Kattints a **Hozzáadás** (Add) gombra, majd keresd meg a listában és kattints a **Letöltés** gombra.
6. **Indítsd újra a Home Assistantot**.

### 2. Módszer: Kézi telepítés (File Editor vagy Studio Code Server)

1. Másold a `custom_components/termoficare_oradea` mappát a Home Assistant `/config/custom_components/` könyvtárába:
   `/config/custom_components/termoficare_oradea/`
2. **Indítsd újra a Home Assistantot**.

---

## Konfigurálás

1. Home Assistantban lépj a **Beállítások** -> **Eszközök és Szolgáltatások** -> **Integráció hozzáadása** menübe.
2. Keress rá: **Termoficare Oradea**.
3. Add meg a bejelentkezési adataidat:
   - **Felhasználónév**: a `termoficare-oradea.ro` oldalon használt felhasználónév vagy e-mail cím.
   - **Jelszó**: a fiókod jelszava.
   - **Frissítési időköz**: alapértelmezett 240 perc (4 óra).
4. Kattints a **Küldés** gombra.

---

## Mintakártya a Dashboardhoz (Lovelace)

```yaml
type: entities
title: Termoficare Oradea
entities:
  - entity: sensor.termoficare_oradea_fizetendo_egyenleg
    name: Fizetendő Egyenleg
  - entity: sensor.termoficare_oradea_utolso_szamla
    name: Legutóbbi Számla
  - entity: sensor.termoficare_oradea_utolso_szamlaszam
    name: Számlaszám
  - entity: sensor.termoficare_oradea_utolso_szamla_kibocsatasa
    name: Kibocsátás Dátuma
  - entity: binary_sensor.termoficare_oradea_tartozas_kintlevoseg
    name: Lejárt Tartozás
```
