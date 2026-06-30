# Sicherheitsrichtlinie

Tessera verändert Home-Assistant-Zugriffsrechte und schreibt in den Auth-Store. Sicherheit hat
darum hohe Priorität. Danke, dass du hilfst, Tessera sicher zu halten.

## Eine Lücke melden

**Bitte melde Sicherheitslücken NICHT als öffentliches Issue.**

Nutze **GitHub Private Vulnerability Reporting**: Repo → Tab **Security** → **Report a vulnerability**.
So bleibt die Meldung privat, bis ein Fix verfügbar ist.

Bitte beschreibe nach Möglichkeit:
- betroffene Tessera-Version + Home-Assistant-Version,
- Modus (`off` / `monitor` / `enforce`),
- Reproduktionsschritte und die beobachtete vs. erwartete Wirkung,
- ob Rechte fälschlich **gewährt** (Privilege Escalation) oder Nutzer fälschlich **ausgesperrt**
  (Lockout) wurden.

Wir bestätigen den Eingang zeitnah, halten dich über den Fortschritt auf dem Laufenden und nennen
dich auf Wunsch in den Release Notes.

## Im Scope (besonders relevant)

- **Privilege Escalation** — ein Nutzer erhält Zugriff, den seine Rollen nicht gewähren.
- **Lockout** — eine legitime Owner-/Admin-Wiederherstellung wird unmöglich.
- **Guard-Umgehung** — Umgehen der allow-only-Assertion, des Lockout-Prechecks oder der
  Owner/System-Konten-Schonung.
- **Secret-Leak** — Tessera schreibt Geheimnisse/Token in Logs, State oder Repairs.
- **Fehlerhafte Restore-/Recovery-Logik** — ein abgebrochener `enforce`-Lauf hinterlässt einen
  unsicheren oder nicht wiederherstellbaren Zustand.

## Bekannte Grenzen (kein Bug — by design dokumentiert)

Diese Punkte sind **bekannt und dokumentiert**; bitte melde sie nicht als neue Lücke (Verbesserungs-
ideen sind aber willkommen):

- **Leak-Pfade:** `render_template` / Template-Sensoren, Logbook/History und Assist/Conversation
  können HA-intern die Permission-Schicht teilweise umgehen. Tessera ist **keine** vollständige
  Daten-Isolation (siehe [README](README.md#dokumentierte-leak-pfade-bekannte-grenzen)).
- **`change` ist global:** bildet HAs `is_admin` ab, nicht bereichs-scoped.
- **Private HA-APIs:** Tessera schreibt teils über nicht-öffentliche Auth-APIs; ein HA-Upgrade kann
  sie brechen. Schutz über Versions-Pin + Fallback auf `monitor`
  (siehe [docs/MAINTENANCE.md](docs/MAINTENANCE.md)).

## Unterstützte Versionen

Tessera ist in aktiver Vor-Release-Entwicklung. Bis zum ersten stabilen Release wird **nur der
aktuelle `main`-Stand** mit Sicherheitsfixes versorgt. Die aktuell getestete HA-Version ist
**2026.6.4** (im Code-Guard `SUPPORTED_HA_AUTH_VERSION` verankert); mit dem ersten Release wird sie
zusätzlich über `hacs.json` (`homeassistant`) gepinnt.

## Verantwortungsvolle Offenlegung

Bitte gib uns angemessene Zeit, einen Fix zu veröffentlichen, bevor du Details öffentlich machst.
Wir handeln zügig und transparent.
