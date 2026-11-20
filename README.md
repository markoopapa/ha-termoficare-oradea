# Termoficare Oradea — Integrare Home Assistant (HACS)

<p align="center">
  <img src="brand/icon@2x.png" width="140" height="140" alt="Termoficare Oradea Icon"><br>
  <img src="brand/logo.png" width="280" alt="Termoficare Oradea Logo">
</p>

Integrare personalizată Home Assistant pentru preluarea automată a soldului, facturilor și restanțelor din portalul online al furnizorului **Termoficare Oradea S.A.** (`https://termoficare-oradea.ro`).

---

## 🌟 Funcționalități

- **Autentificare directă**: Se conectează securizat direct la portalul de clienți `termoficare-oradea.ro`.
- **Sold total de plată**: Monitorizează în timp real suma totală rămasă de achitat.
- **Detalii ultima factură**: Valoare totală, valoare fără TVA, TVA, număr factură, data emiterii și link direct pentru descărcarea facturii în format PDF.
- **Alertă factură restantă**: Senzor binar (`binary_sensor`) ce indică dacă există debite sau facturi cu scadența depășită.
- **Interfață completă în limba română**: Toate denumirile senzorilor și formularele de configurare sunt nativ în limba română.
- **Actualizare automată**: Datele sunt reîmprospătate în fundal la fiecare 4 ore (interval configurabil).

---

## 📊 Entități create

| Entitate | Tip | Descriere |
|---|---|---|
| `sensor.termoficare_oradea_sold_total_de_plata` | Senzor monetar (`RON`) | Soldul total de plată la zi |
| `sensor.termoficare_oradea_ultima_factura` | Senzor monetar (`RON`) | Valoarea ultimei facturi emise |
| `sensor.termoficare_oradea_numar_factura` | Senzor text | Numărul ultimei facturi emise |
| `sensor.termoficare_oradea_data_facturii` | Senzor dată | Data emiterii ultimei facturi |
| `binary_sensor.termoficare_oradea_factura_restanta` | Senzor binar (`problem`) | `On` dacă există facturi restante neachitate |

---

## 📥 Instalare

### Metoda 1: Prin HACS (Recomandat)

1. În Home Assistant accesați meniul **HACS** (Community Store).
2. Apăsați pe cele **3 puncte** din colțul din dreapta sus și selectați **Custom repositories** (Depozite personalizate).
3. Introduceți adresa URL a depozitului:
   `https://github.com/markoopapa/ha-termoficare-oradea`
4. La categorie alegeți: **Integration** (Integrare).
5. Apăsați pe **Add** (Adaugă), apoi căutați **Termoficare Oradea** și apăsați pe **Download** (Descarcă).
6. **Reporniți Home Assistant**.

### Metoda 2: Instalare manuală

1. Copiați dosarul `custom_components/termoficare_oradea` în directorul `/config/custom_components/` al instanței dvs. de Home Assistant:
   `/config/custom_components/termoficare_oradea/`
2. **Reporniți Home Assistant**.

---

## ⚙️ Configurare

1. În Home Assistant navigați la **Setări** -> **Dispozitive și servicii** -> **Adaugă integrare**.
2. Căutați **Termoficare Oradea**.
3. Introduceți datele de conectare folosite pe portalul `termoficare-oradea.ro`:
   - **Utilizator**: Numele de utilizator sau adresa de e-mail.
   - **Parolă**: Parola contului.
   - **Interval actualizare**: Implicit 240 minute (4 ore).
4. Apăsați pe **Trimite**.

---

## 📱 Exemplu card Lovelace

```yaml
type: entities
title: Termoficare Oradea
show_header_toggle: false
entities:
  - entity: sensor.termoficare_oradea_sold_total_de_plata
    name: Sold total de plată
  - entity: sensor.termoficare_oradea_ultima_factura
    name: Valoare ultimă factură
  - entity: sensor.termoficare_oradea_numar_factura
    name: Număr factură
  - entity: sensor.termoficare_oradea_data_facturii
    name: Data emiterii
  - entity: binary_sensor.termoficare_oradea_factura_restanta
    name: Factură restantă
```


---

## ☕ Susținere / Donații

Dacă această integrare vă este utilă și doriți să susțineți mentenanța și dezvoltarea viitoare a proiectului, puteți oferi o cafea:

- ☕ **Buy Me a Coffee**: [buymeacoffee.com](https://www.buymeacoffee.com)
- 💳 **Revolut**: [revolut.me](https://revolut.me)
- 🅿️ **PayPal**: [paypal.me](https://paypal.me)

Dacă vă este de ajutor proiectul, lăsați o steluță ⭐ pe [GitHub](https://github.com/markoopapa/ha-termoficare-oradea) — ajută comunitatea să descopere mai ușor integrarea!
