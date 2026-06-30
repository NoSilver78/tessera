# Wartung — Home-Assistant-Versions-Tracking

Tessera schreibt teils über **nicht-öffentliche HA-Auth-APIs** (z. B. den internen Auth-Store, das
Gruppen-Objektmodell). Home Assistant gibt für diese **keine** Stabilitätsgarantie — sie können sich
zwischen Releases ändern. Das ist die größte Dauer-Belastung des Projekts. Dieses Dokument hält den
Prozess fest, der Tessera trotzdem sicher und installierbar hält.

## Das Risiko in einem Satz

Ein HA-Update kann eine interne API verschieben oder entfernen → Tesseras Schreibpfad bricht →
**im schlimmsten Fall falsche Rechte oder ein Lockout**. Deshalb gibt es mehrere ineinandergreifende
Schutzschichten.

## Schutzschichten

1. **Code-Guard auf die exakt getestete HA-Version.** Der Auth-Schreibpfad prüft im Code gegen die
   getestete HA-Version (derzeit **`2026.6.4`**, `SUPPORTED_HA_AUTH_VERSION`). Auf einer abweichenden
   Version wird der Enforce-/Schreibpfad **fail-closed blockiert** (`compute_enforce_plan` liefert
   einen `blocked`-Plan) — **kein** nativer Write; wirksam bleibt der read-only `monitor`-Zustand.
   Das ist ein bewusst strenger Fail-closed-Block, kein blindes Weiterschreiben.
2. **HACS-Mindestversion (mit dem Release).** Sobald `hacs.json` ausgeliefert wird, pinnt der Key
   `homeassistant` die HA-Mindestversion; HACS blockt dann Installation/Update auf älteren Instanzen.
   *(Hinweis: Diese Schicht greift erst ab dem ersten Release — bis dahin schützt allein der
   Code-Guard aus #1.)*
3. **Fail-safe-to-monitor überall.** Jeder Fehler im Enforce-/Recovery-Pfad fällt auf den
   nicht-eingreifenden `monitor`-Modus zurück (kein Deny-all, kein stiller Halbzustand).

## Prozess pro HA-Release

Für **jedes** neue Home-Assistant-Release:

1. **Testen** — die Integrations-Tests gegen die neue HA-Version laufen lassen (idealerweise per
   nightly/matrix-CI, die mehrere HA-Versionen abdeckt). Besonderes Augenmerk: Auth-Store-Schreiben,
   Rebind, Restore.
2. **Bei grünem Lauf:** `SUPPORTED_HA_AUTH_VERSION` auf die neue getestete Version anheben, ggf. ein
   neues PATCH/MINOR-Release schneiden.
3. **Bei gebrochener interner API:**
   - den Versions-Guard anpassen (neue HA-Version erkennen, Enforce fail-closed blockieren),
   - die HACS-Mindestversion in `hacs.json` anheben,
   - eine neue **MAJOR**-Version veröffentlichen (Bruch der Kompatibilität),
   - den Bruch im Changelog + den Release Notes klar benennen.

## Versions-Invarianten

- **`manifest.json` → `version`** ist **byte-genau** gleich dem GitHub-Release-Tag. HACS nutzt das
  jüngste Release als Update-Ziel; eine Abweichung führt zu inkonsistenten Update-Anzeigen.
- **Semantische Versionierung:** `MAJOR.MINOR.PATCH`. MAJOR = Kompatibilitätsbruch (auch ein
  angehobenes HA-Minimum), MINOR = Feature, PATCH = Fix.
- **Releases statt nur Tags:** Nutzer pinnen auf konkrete Releases, die zu ihrer HA-Version passen.

## Changelog

Jedes Release dokumentiert in [`CHANGELOG.md`](../CHANGELOG.md): neue getestete HA-Version(en), die
HA-Mindestversion, und jeden Bruch einer internen API. So können Nutzer eine Tessera-Version wählen,
die zu ihrer HA-Instanz passt.
