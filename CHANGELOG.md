# Changelog

Alle nennenswerten Änderungen an Tessera werden hier dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), und das
Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

## [Unreleased]

## [0.5.0] — 2026-07-01

### Hinzugefügt
- **Area-Board (Matrix-Panel):** je Rolle zwei Provenance-Spalten **`Floor | Area`** — die
  Floor-Zelle zeigt das von der Etage geerbte Recht (bisher im Panel unsichtbar), die Area-Zelle den
  direkten Grant (klickbar/editierbar wie gehabt). Deckt eine Area beide Quellen, wird die Zeile als
  **`doppelt`** markiert (redundante Doppelvergabe). Jede Area-Zeile ist **aufklappbar** und listet
  die von Tessera aufgelösten Entities (die das Area-Recht erben, daher ohne eigene Wertespalten).
- **Matrix-WS** (`tessera/matrix/get`) liefert dafür Grants **nach Quelle getrennt** (`floor_grants`
  je Area zusätzlich zu den bestehenden `grants` = Area-Quelle), `area_floor` (Etage je Area) und
  `entities_by_area` (für das Aufklappen).

### Behoben
- **Floor-Grants waren im Panel unsichtbar** — das Panel las bisher nur `area_grants`, sodass
  floor-abgedeckte Areas irreführend „none" zeigten. Die Floor-Spalte macht die Herkunft sichtbar.

## [0.4.0] — 2026-07-01

### Hinzugefügt
- **`tessera.set_mode`** — Admin-Service zum Setzen des Betriebsmodus (`off`/`monitor`/`enforce`).
  Läuft über denselben guarded `_compile_for_mode_safely`-Pfad wie der Options-Flow: `enforce`
  rechnet/journalt/appliet nativ, das Verlassen von `enforce` restauriert den Pre-Install-Snapshot,
  jeder Fehler fällt sicher auf `monitor` zurück. Admin-only.

### Behoben
- **Enforce-Modus war über die HA-UI nicht erreichbar.** Das Matrix-Panel ist als Config-Panel der
  Integration registriert → das Zahnrad öffnet das Panel statt des Options-Flows, und das ⋮-Menü hat
  kein „Konfigurieren"; der `set_mode`-Options-Flow-Schritt war damit verwaist. `tessera.set_mode`
  macht den Modus wieder regulär bedienbar (via `ha_call_service` / Entwicklerwerkzeuge). Auf der
  Dev-Instanz nie aufgefallen, weil der Modus dort per Storage-Seed + Restart geflippt wurde.

## [0.3.0] — 2026-07-01

### Hinzugefügt
- **`tessera.preflight`** — read-only Enforce-Readiness-Check (admin-only). Führt die
  Enforce-Planung vollständig **read-only** aus (kein nativer Write, kein Mode-Wechsel) und gibt als
  Service-Response zurück: ob `enforce` durchliefe, die **vollständige D9-Component-Blockerliste**
  (welche Custom-Components vetoen und warum), die Cross-Rollen-Linter-Konflikte und eine
  Modell-Zusammenfassung. Redacted (keine content-hashes, gekürzte user_ids). Abfragbar via
  `ha_call_service(return_response=true)` — das „würde enforce laufen, und was blockt?"-Werkzeug.

## [0.2.0] — 2026-07-01

Erste getaggte Auslieferung (Dogfood/Soak-Stand). Enthält den vollständigen Kern, den
Monitor-Modus, die adversarial gegatete Enforce-Maschinerie und die deklarative
Modell-Pflege. (Version `0.1.0` war interner Vorbereitungsstand und wurde nie getaggt.)

### Hinzugefügt
- **Core** — Store (Source of Truth), Compiler (Bereich → Entity-Expansion), Linter, Schema, Config-Flow.
- **Monitor-Modus** — read-only Vorschau der kompilierten Permissions + Area×Rolle-Admin-Panel.
- **Enforce-Maschinerie (E3.1–E3.5)** — Plan, Bindings, Write+Guards, Restore/Recovery, im Setup-Pfad
  verdrahtet: `mode=enforce` löst die Durchsetzungs-Sequenz aus (compute → Snapshot/Journal → Apply →
  clear; Crash-Recovery beim Start) und **schreibt** nativen Auth-Zustand; jeder Fehler fällt sicher
  auf `monitor` zurück.
- **D9-Vorprüfung v2 (auth-scoped)** — nur auth-mutierende oder nicht statisch analysierbare Components
  veto'en `enforce`; per Ack/Klassifikation überstimmbar (siehe SECURITY.md).
- **D9-Ack-Admin-Services** — `tessera.acknowledge_component` / `tessera.revoke_component_ack`
  (admin-only, versions- und hash-gebunden; Ack verfällt bei Änderung der Component).
- **`by_user`-Mitgliedschaft** — `tessera.set_membership` (admin-only) weist lokale Nicht-Admin-User
  einer oder mehreren Rollen zu.
- **Floor-Grant-Selektor** — Policy-Dimension `floor_grants` + `tessera.set_floor_grant`: ein
  Etagen-Grant expandiert additiv über die Area-Registry auf alle Entities der Etage (allow-only,
  fail-closed).
- **Deklarativer Modell-Import** — `tessera.import` (admin-only) provisioniert das ganze Modell
  (Rollen inkl. `is_admin`, `by_user`-Memberships, area/floor-Grants, Entity-Overrides) in **einem**
  idempotenten, fail-closed Call; bereitgestellte Dimensionen ersetzen, ausgelassene bleiben erhalten,
  Betriebsfelder (`mode`, `d9_acks`) werden nie angetastet.
- **HACS-Aktivierung** — `hacs.json`, Validierungs-CI (hassfest + HACS), Inline-Brand-Icon.

### Behoben
- **Matrix-Panel schreibt in `enforce` nativ nach** — ein über das Panel gesetzter Grant löst in
  `enforce` sofort einen guarded nativen Re-Apply aus (Lockout/D9/allow-only), statt nur die read-only
  Vorschau zu aktualisieren.
- **Store-Mutationen serialisiert** — alle Store-Schreibpfade laufen unter einem prozessweiten
  Mutation-Lock; parallele Edits (z.B. schnelles Multi-Zell-Toggeln im Panel) verlieren keine Grants
  mehr (behobenes last-write-wins Lost-Update).

### In Arbeit
- **Praxis-Validierung von `enforce`** — Monitor-Soak an der Zielinstanz + Dogfood, vor `enforce`-als-Default.
