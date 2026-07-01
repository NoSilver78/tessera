# Changelog

Alle nennenswerten Änderungen an Tessera werden hier dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), und das
Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

## [Unreleased]

### Hinzugefügt
- **Enforce-Verdrahtung (E3.5)** — `mode=enforce` löst die Durchsetzungs-Sequenz tatsächlich aus
  (compute → Snapshot/Journal → Apply → clear; Crash-Recovery beim Start) und **schreibt** nativen
  Auth-Zustand; jeder Fehler fällt sicher auf `monitor` zurück.
- **D9-Vorprüfung v2 (auth-scoped)** — nur auth-mutierende oder nicht statisch analysierbare
  Components veto'en `enforce`; per Ack/Klassifikation überstimmbar (siehe SECURITY.md).
- **D9-Ack-Admin-Services** — `tessera.acknowledge_component` und `tessera.revoke_component_ack`
  (admin-only) erfassen bzw. widerrufen einen versions- und hash-gebundenen Ack, mit dem ein Admin
  den D9-Veto einer auth-berührenden Component bewusst überstimmt; der Ack verfällt automatisch,
  sobald sich Version oder Inhalt der Component ändern.
- **HACS-Aktivierung** — `hacs.json`, Validierungs-CI (hassfest + HACS), Inline-Brand-Icon.

### Behoben
- **Matrix-Panel schreibt in `enforce` nativ nach** — ein über das Area×Rolle-Panel gesetzter Grant
  löst in `enforce` jetzt sofort einen nativen Re-Apply über den zentralen fail-safe Pfad aus
  (compute → Apply mit Lockout/D9/allow-only-Guards); vorher wurde nur die Policy + die read-only
  Vorschau aktualisiert, ohne Wirkung auf die Live-Permissions bis zum nächsten Reload.

### In Arbeit
- **Praxis-Validierung von `enforce`** — End-to-End gegen eine separate Dev-Instanz + Soak + Dogfood.

## [0.1.0] — noch nicht veröffentlicht

Vorbereitung der ersten öffentlichen Auslieferung.

- **Core** — Store (Source of Truth), Compiler (Bereich → Entity-Expansion), Linter, Schema, Config-Flow.
- **Monitor-Modus** — read-only Vorschau der kompilierten Permissions + Matrix-Admin-Panel.
- **Enforce-Maschinerie** — Plan, Bindings, Write+Guards, Restore/Recovery — gebaut, adversarial
  gegated und im Setup-Pfad verdrahtet (schreibt nativen Auth bei `mode=enforce`; fail-safe auf
  `monitor`).

> Hinweis: Es gibt noch **kein** getaggtes Release. Dieser Eintrag wird beim ersten Release mit dem
> Tag `0.1.0` finalisiert — dann byte-genau passend zu `manifest.json` → `version`.
