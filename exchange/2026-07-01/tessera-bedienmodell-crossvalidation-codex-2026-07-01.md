# Tessera Bedienmodell Crossvalidation - Codex - 2026-07-01

Status: REVIEW / AUFLAGEN
Quelle: `exchange/2026-07-01/tessera-bedienmodell-2026-07-01.md`, `exchange/2026-07-01/tessera-bedienmodell-crossvalidation-request-codex-2026-07-01.md`
Scope: read-only Code-/Doku-Pruefung gegen Tessera `main` nach Commit `52bc92c`, mit zwei unabhaengigen Gegenpruef-Agenten.
Secret-Status: keine Secrets gelesen oder berichtet; keine Live-/Restore-/Auth-Store-Writes ausgefuehrt.

## Gesamturteil

Das Bedienmodell ist als Produkt-/UX-Richtung tragfaehig, aber nicht ohne Auflagen baubar. Die drei wichtigsten Korrekturen sind:

1. `by_user`-Membership-Writer ist der richtige erste Soak-Unblocker, aber nur als admin-only Store-Writer mit zentralem Recompile/Apply-Pfad, Redaction und Fail-Closed-Tests.
2. Der Authentik-/`by_group`-Parallelpfad darf parallel spezifiziert und implementiert werden, aber nicht scharfgeschaltet werden, bevor Claim-Hook, Effective-Union, Linter/Preflight-Union, Owner-Lockout-Guard gegen leere/kaputte Claims und D12-Live-Beweis bestehen.
3. `compute_enforce_plan` ist noch kein renderbarer PASS-Preflight. Es blockt wichtige Risiken, liefert aber fuer erfolgreiche Plaene noch keine vollstaendige Checklisten-Evidenz zu D9, Linter, Auth-Version, Owner-survives und Allow-only.

Damit: ACCEPT fuer Modellrichtung, AUFLAGEN fuer Bauplanung, NO-GO fuer sofortige `by_group`-De-Inertness.

## Dimension 1 - Code-Behauptungen

Verdikt: teils bestaetigt, teils angefochten.

Bestaetigt: `monitor.py` liefert nur Aggregatdaten, keinen Deny-Log. `MonitorPreview` enthaelt Counts wie Rollen, Entities, Read/Control und Lint; `monitor_preview`/Logging geben keine per-Event- oder per-Entity-Deny-Evidenz aus. Damit ist die Modellforderung nach Deny-/Effective-Evidenz berechtigt.

Bestaetigt: `by_group` ist nicht nur UX-seitig, sondern strukturell inert. `compiler.py` setzt `BY_GROUP_PROJECTION_MODE = "v1-inert"`; `mode_manager.py` bildet Bindings aktuell aus `membership.by_user`; `linter.py` iteriert ebenfalls `by_user`; ADR 0005 fordert At-Login-Hook, D12-Live-Beweis und Re-Gate vor `by_group`-Aktivierung.

Bestaetigt: D9-Ack-Services existieren und sind admin-gated. Die Registrierung nutzt `async_register_admin_service`; Tests decken Ack-Service-Persistenz und Gate-Verhalten ab. Caveat: Ein Panel-/UX-Ort fuer diese Acks ist noch nicht vorhanden.

Angefochten: Die Aussage, `compute_enforce_plan` koenne bereits die vollstaendige Safety-Checkliste rendern, ist ueberhoeht. Der Plan gate't Version, Store/Resolver, D9, Linter und Auth-Reads, aber die erfolgreiche Rueckgabe enthaelt im Wesentlichen Groups, Bindings, Orphans und Block-Felder. Owner-survives und Allow-only laufen stark im Apply-Pfad, sind aber noch keine expliziten PASS-Felder fuer UI/Review.

## Dimension 2 - Vollstaendigkeit

Verdikt: Luecke.

Das Modell deckt Rollen, Matrix, Membership, Effective View, Authentik und Wizard grob ab. Fuer den realen Admin-Alltag fehlen aber noch sichtbare oder priorisierte Aufgaben:

- `entity_overrides` sind Schema-/Compiler-/Linter-real, aber im aktuellen Panel nicht editierbar.
- Rollen umbenennen, duplizieren, loeschen mit sauberem Cleanup und Massen-Zuweisung sind noch nicht als konkrete Backend-/UI-Flows abgesichert.
- Drift-/Orphan-Cleanup, Import/Export, Migration/Reset und Umgang mit Service-/unmanaged Accounts sind in Doku/Anforderungen sichtbar, aber nicht in einem harten ersten Bauplan.
- D9-Ack-UI und Effective-/Deny-Evidenz fehlen als Nutzerfuehrung.

Empfehlung: First Wave eng halten: `by_user`-Writer plus Effective-Read/Preflight-DTO; danach Deny-Evidence und Entity-Overrides.

## Dimension 3 - Home-Assistant-Machbarkeit

Verdikt: bestaetigt mit Drift-Risiko.

Options Flow ist fuer einfache sequentielle Konfiguration geeignet, aber nicht fuer Matrix, Massenrollen, Effective Attribution oder Preflight-Diff. Der bestehende Custom Panel-Ansatz passt zur Bedienlogik. Die im Modell genannten HA-Frontend-Elemente wie `ha-data-table`/`hass-tabs-subpage-data-table` sollten jedoch nicht als stabile externe API behandelt werden. Der aktuelle Code nutzt bewusst ein eigenes einfaches HTML-Table-Rendering.

Empfehlung: Panel als kanonischen Ort fuer Matrix, Membership, Effective View und Preflight. Interne HA-Webcomponents nur hinter einem duennen Adapter oder vermeiden.

## Dimension 4 - Authentik / `by_group`

Verdikt: Luecke / nicht sofort scharf.

Additive Union ist als Zielmodell richtig: `by_user` muss lokale Breakglass-/Owner-Sicherheit bewahren, `by_group` darf nur zusaetzliche valide Rollen beitragen. Der aktuelle Code bildet diese Union aber noch nirgends: Binding-Plan und Linter arbeiten auf `by_user`.

Mindest-Gates vor Aktivierung:

- At-Login- oder Session-Claim-Hook mit redacted Verarbeitung.
- Normalisierte Gruppen-Identifier, bevorzugt Slug/stabile ID, aber erst nach D12-Live-Beweis verbindlich entscheiden.
- Effective Rollenbildung `by_user ∪ valid_by_group` mit Quellenattribution.
- Linter und Preflight muessen dieselbe Effective-Union pruefen wie der Compiler/Apply-Pfad.
- Missing/empty/malformed `groups` darf nicht still Rollen entfernen oder Default-Deny schreiben; enforce muss blocken oder fail-safe gehen.
- Tests fuer lokale User ohne Claim, kaputte Claims, Owner/Admin-Survival, by_user-Preservation, System-Generated/Owner-Rejection und keine fremden nativen Gruppen.

Damit ist der parallele Authentik-Track nur als Spezifikations-/Implementierungszweig gruen, nicht als Enforce-Feature.

## Dimension 5 - Sicherheit neuer Write-Pfade

Verdikt: Auflagen.

Ein `by_user`-Writer schreibt zwar zunaechst nur Tessera-Konfiguration, wird in `enforce` aber sicherheitswirksam, weil Recompile/Apply native HA-Gruppen aendern kann. Er darf deshalb nicht als harmloser Store-Setter behandelt werden.

Pflicht fuer `tessera/membership/set`:

- WebSocket-Service admin-only (`require_admin`) und kein direkter native Auth Write.
- Schema-validierter Store-Write, unbekannte User/Roles fail-closed.
- In `enforce` zwingend derselbe zentrale `_compile_for_mode_safely`/Apply-Guard-Pfad wie Matrix-Updates.
- Redacted Audit: User-ID/Role-IDs ja, keine Tokens/Claims/Secrets.
- Tests: unknown domain/user/role, last-admin/owner-risk, owner/system-generated target rejection, no native write on block, recompile failure fail-safe.

Bestehende Allow-only-, Version-, D9-, Linter- und Lockout-Gates sind stark; neue Authentik- oder Membership-Pfade duerfen sie nicht umgehen.

## Dimension 6 - Wizard

Verdikt: spaet und schmal.

Ein Wizard ist als First-Run- oder Enforce-Ramp-Hilfe sinnvoll, aber nicht als erster Bauanker. Fuer den Ein-Owner-Homelab-Fall reichen frueher: Empty-State, Preset-Seed, Membership-Writer, Effective View und Preflight. Ein Wizard, der Rollen-CRUD, Matrix, Membership, Authentik und D9 buendelt, wuerde das Alltags-UI duplizieren und die Sicherheitslogik verstecken.

Empfehlung: Wizard zuletzt; keine Authentik-Aktivierung im Wizard vor bestandenen `by_group`-Gates.

## Dimension 7 - Reihenfolge

Verdikt: leicht angefochten.

Der staerkste erste Bau-Schritt ist `by_user`-Membership-Writer plus minimale Effective-Access-Read-Schicht. Deny-Log ist wichtig, aber nicht zwingend der allererste Blocker fuer Monitor-Soak. Vor einem Enforce-Flip braucht es jedoch entweder echte Deny-Evidence oder einen klar als hypothetisch markierten Effective-Diff; ein rein gruen wirkender Preflight ohne Herkunft/Effekt waere psychologisch riskant.

Empfohlene Reihenfolge:

1. `by_user`-Writer admin-only, recompile-safe, fail-closed.
2. Effective-Access-Read/Preflight-DTO mit Quellen und PASS/BLOCK-Gates.
3. Deny-/Would-Block-Evidence, zuerst synthetisch aus Resolver/Plan, spaeter echte Traffic-Hooks mit Retention-Policy.
4. Entity-Overrides und Rollenpflege.
5. Authentik `by_group` nach D12/Re-Gate.
6. Wizard/Onboarding.

## Dimension 8 - Offene Entscheidungen

Deny-Log-Quelle: zuerst synthetisch/hypothetisch aus Resolver und Plan; reale Runtime-Ereignisse spaeter, redacted und mit Retention.

Membership-UI-Ort: Panel, nicht Options-Flow/Subentries. Grund: Massen-Zuweisung, Herkunftsanzeige und Effective-Diff brauchen eine zusammenhaengende Oberflaeche.

Preset-Personas: nur als Seed/Templates, keine Default-Grants ohne lokalen Bestand und keine automatische Enforce-Aktivierung.

Authentik Slug/Name: Slug/stabile ID bevorzugt, aber als unbewiesen markieren, bis D12 den realen Claim-Inhalt bestaetigt. Name nur Display-Label.

`by_group`-UI: Mapping darf vorbereitet werden, aber Aktivierung/Projektion bleibt gesperrt, bis Claim-Gates und Linter/Preflight-Union fertig sind.

## Neue Risiken gegenueber dem Modell

1. Erfolgreiche Preflight-UI braucht ein neues DTO; sonst kann die UI aus Apply-Gates ein falsches PASS-Signal ableiten.
2. `by_group`-De-Inertness betrifft Compiler, Mode-Manager, Linter, Effective View und Tests; nur das Compiler-Flag zu drehen waere gefaehrlich.
3. Konzept/Doku und Code divergieren beim Umgang mit Usern ohne wirksame Rolle: Code faellt auf Default-Rolle zurueck, Konzept fordert fuer bestimmte Faelle enforce refusal. Das muss vor Authentik-Aktivierung entschieden werden.
4. `entity_overrides` sind sicherheitsrelevant und backend-real, aber UX-seitig unsichtbar.
5. HA-Frontend-Internals duerfen nicht als stabile Produktgrundlage angenommen werden.

## Schnittmenge / Divergenz zur Claude-Vorlage

Schnittmenge:

- Monitor liefert nur Aggregate; Deny-/Effective-Evidenz fehlt.
- `by_group` ist v1-inert und braucht D12/Re-Gate.
- D9-Acks existieren und sind admin-gated, aber ohne Panel-UX.
- `by_user`-Membership-Writer fehlt und ist der Soak-Unblocker.
- Panel ist der richtige Ort fuer Matrix/Effective/Membership.
- Wizard ist nachrangig und sollte schmal bleiben.

Divergenz:

- `compute_enforce_plan` ist noch kein vollstaendig renderbarer Safety-PASS.
- Authentik parallel ist nicht nur spaeter zu bauen, sondern vor Aktivierung strikt claim-/union-/linter-/lockout-gate-pflichtig.
- Der erste Bau-Schritt sollte `by_user` plus Effective-Read sein; Deny-Log kann danach oder parallel folgen.
- Slug-vs-Name ist eine plausible Praeferenz, aber ohne D12 noch nicht beweisfest.

## Schluss

Codex empfiehlt: Bedienmodell mit Auflagen weiterfuehren. Naechster umsetzbarer PR-Scope sollte `by_user`-Membership-Writer + minimale Effective-/Preflight-Erweiterung sein. Der Authentik-Pfad darf parallel spezifiziert werden, bleibt aber bis D12/Re-Gate und Claim-Failure-Tests nicht scharf.
