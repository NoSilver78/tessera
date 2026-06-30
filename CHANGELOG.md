# Changelog

Alle nennenswerten Änderungen an Tessera werden hier dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), und das
Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

## [Unreleased]

### In Arbeit
- **Enforce-Verdrahtung** — `mode=enforce` löst die gebaute Durchsetzungs-Sequenz tatsächlich aus;
  anschließend End-to-End-Validierung gegen eine Dev-Instanz + Soak.

## [0.1.0] — noch nicht veröffentlicht

Vorbereitung der ersten öffentlichen Auslieferung.

- **Core** — Store (Source of Truth), Compiler (Bereich → Entity-Expansion), Linter, Schema, Config-Flow.
- **Monitor-Modus** — read-only Vorschau der kompilierten Permissions + Matrix-Admin-Panel.
- **Enforce-Maschinerie** — Plan, Bindings, Write+Guards, Restore/Recovery — gebaut und adversarial
  gegated, aber **ruhend** (noch nicht verdrahtet).

> Hinweis: Es gibt noch **kein** getaggtes Release. Dieser Eintrag wird beim ersten Release mit dem
> Tag `0.1.0` finalisiert — dann byte-genau passend zu `manifest.json` → `version`.
