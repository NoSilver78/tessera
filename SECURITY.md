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

## D9-Vorprüfung (Enforce-Gate) — Sicherheitsmodell

Bevor `enforce` aktiviert wird, klassifiziert die **D9-Vorprüfung** alle installierten
Custom-Components. Ihr Zweck ist **Konflikt-Vermeidung**, kein Malware-Sandbox:

- **Threat-Model:** HA-Custom-Components führen beliebigen, voll privilegierten Python-Code aus.
  Eine *bösartige* Komponente kann jeden statischen Gate aushebeln — dagegen schützt D9 nicht und
  gibt das auch nicht vor. D9 verhindert **versehentliche Konflikte** (eine andere Komponente, die
  parallel denselben Auth-/Gruppen-Zustand verwaltet) und vermeidet ein falsches Sicherheitsgefühl.
- **Default-Posture (bewusste Entscheidung):** Nur Components, die den **verwalteten Auth-Zustand
  mutieren können** (erkannte Auth-API-Marker), **oder nicht statisch analysierbar** sind
  (kompiliert `.so/.pyd`, unparsebar/dynamisch), blockieren `enforce` — und auch das nur, solange
  sie nicht per **Ack** (Domain+Version+Content-Hash) oder kuratierter Klassifikation freigegeben
  sind. **Alles andere — generische UI-Surfaces (HTTP/Service/WebSocket) und unbekannte Components
  ohne Auth-Surface — läuft per Default.** Das ist bewusst eine *fail-open*-Haltung für
  Nicht-Auth-Surfaces; sie ersetzt die ursprüngliche „alles blockiert"-Haltung, die `enforce` auf
  realen Installationen unbenutzbar machte. Der Verlass liegt damit auf der **Vollständigkeit der
  Auth-Marker-Liste** (introspektiv gegen die installierte HA-Auth-API gepflegt).
- **Statische-Scan-Grenzen:** Die Auth-Erkennung ist ein Token-basierter AST-Scan echter
  HA-Auth-API-Namen. Ehrliche **Over-Matches** (z. B. ein reiner Type-Hint auf `UserMeta`) sind
  **sichere Über-Blockaden** und per Ack auflösbar. Bewusste Verschleierung ist — gemäß Threat-Model
  — out of scope. Fehlende Marker für echte HA-Auth-Mutations-Pfade sind hingegen **im Scope**
  (bitte melden).

## Unterstützte Versionen

Tessera ist in aktiver Vor-Release-Entwicklung. Bis zum ersten stabilen Release wird **nur der
aktuelle `main`-Stand** mit Sicherheitsfixes versorgt. Die aktuell getestete HA-Version ist
**2026.6.4** (im Code-Guard `SUPPORTED_HA_AUTH_VERSION` verankert); mit dem ersten Release wird sie
zusätzlich über `hacs.json` (`homeassistant`) gepinnt.

## Verantwortungsvolle Offenlegung

Bitte gib uns angemessene Zeit, einen Fix zu veröffentlichen, bevor du Details öffentlich machst.
Wir handeln zügig und transparent.
