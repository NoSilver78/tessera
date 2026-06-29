# ADR 0004 — Monitor-Mode vor Enforce-Schreibpfad
Stand 2026-06-29 · Status: **aktiv** · Entscheidung: Michael (2026-06-29)

## Kontext
Der Core hat Store→Schema→Resolver→Compiler (in-memory Policy). Die nächsten Schritte berühren die **Enforce-Grenze** (Auth-Adapter schreibt native HA-Policies). Das tatsächliche Scharfschalten hängt aber am Spike **Welle B/C/D** (D5-Rescue/Lockout-Schutz, Leak-Matrix, D9) — die sind noch offen.

## Entscheidung
**Zuerst Monitor-Mode-Wiring (rein lesend), dann erst der native Schreibpfad.**
- Core wird end-to-end verdrahtet: Store → Resolver → Compiler → **Log „was wäre"** (Monitor), **kein** Write in `hass.auth`.
- Der **Auth-Adapter / Enforce** (nativer Write) wird **erst gebaut**, wenn Spike Welle B/C/D grün ist (Schreibpfad inkl. Rescue/Lockout voll validiert).

## Begründung
„Sicherheit, wo sie zählt": Kein nativer Auth-Write-Code im Produkt, bevor der Spike Rescue + No-Lockout beweist. Monitor-Mode zeigt den Core lauffähig + risikolos.

## Konsequenz
Schritt-Reihenfolge angepasst: **Monitor-Wiring → (Spike Welle B/C/D) → Auth-Adapter → Authentik by_group → Enforce/Mode-Manager → Panel.**
