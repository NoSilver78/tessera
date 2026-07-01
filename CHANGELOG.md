# Changelog

Alle nennenswerten Änderungen an Tessera werden hier dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), und das
Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

## [Unreleased]

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
