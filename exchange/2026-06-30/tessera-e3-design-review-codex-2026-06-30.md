# Tessera E3-Design Review — Codex

Stand: 2026-06-30

Review-Ziel: `docs/spec-e3-design.md` als Vor-Scharf-Architektur gegen `docs/spec-e3-enforce.md`, `CONTRACT.md` und lokale HA-API-Anker prüfen.

Secret-Redaction-Status: PASS. Es wurden keine Secrets, Token, `.storage`-Werte oder `/Volumes/config`-Inhalte gelesen oder geschrieben.

## Entscheidung

MODIFY

Teil A/E2.5 ist als non-scharfer Produkt-D9-Gate-Schritt grundsätzlich sinnvoll und baubar. Teil B/C sind als E3-Vorentscheidung plausibel. Es gibt aber einen sicherheitsrelevanten Blocker in der D9-ALLOW-Semantik: die aktuelle Formulierung lässt kuratierte Tabellen-ALLOWs zu, ohne dass die Tabelle ihren Runtime-Beleg und die geprüfte Surface-Basis zwingend mittragen muss.

## Findings

### BLOCKER — D9-ALLOW kann bei unvollständiger Surface-Erkennung zu breit werden

Beleg:
- `docs/spec-e3-design.md:24-30` definiert Default-UNKNOWN, Tabelle/Ack und eine Surface-Heuristik.
- `docs/spec-e3-design.md:46-48` fordert Tests für Default-UNKNOWN und ALLOW via Tabelle/Ack, aber keinen Regressionstest für eine versteckte Oberfläche ohne Manifest-Hinweis.
- Lokaler HA-Anker: `homeassistant/loader.py:316-334` liefert installierte Custom Components gecached; `homeassistant/loader.py:845-868` liefert `integration_type` und `has_services`, aber nicht “registriert HTTP-View/WS-Command zur Laufzeit”.
- Lokaler Scratchpad-Proof `proof_d9.py` modelliert genau den Fall `sneaky_http`: keine `http`-Dependency, kein `services.yaml`, entity-artiger Typ, aber tatsächliche View/WS-Oberfläche. Eine rein deklarative Surface-Heuristik erkennt das nicht.

Risiko:
Eine Komponente kann nach Manifest/Top-Level-Dateien harmlos aussehen, aber im Runtime-Setup Views, WS-Commands oder System-Kontext-Pfade registrieren. Wenn `d9_classification.py` einen solchen Domain-Eintrag als ALLOW führt, ohne verpflichtenden Runtime-Beleg und Surface-Basis, wird der D9-Gate-Blocker unterlaufen. Das verletzt die Spec-Invariante aus `spec-e3-enforce.md:14` und `spec-e3-enforce.md:27-31`: D9 muss vor jedem Write fail-closed blockieren.

Auflage:
- `d9_classification.py` darf ALLOW nur mit explizitem Belegtyp tragen, z. B. `runtime_verified_allow`, `no_surface_verified`, `tier2_accepted`, jeweils mit Version/Range und Grund.
- Tabellen-ALLOW muss fail-closed sein, wenn die aktuelle Komponente eine nicht im Eintrag erwartete Oberfläche zeigt oder wenn der Eintrag keinen Runtime-/Surface-Belegtyp enthält.
- Tests ergänzen: “table ALLOW + nicht deklarierte/neu erkannte Oberfläche => UNKNOWN_BLOCK_ENFORCE”, “Manifest ohne http/ws/services reicht nie als positiver ALLOW-Beweis”, Ack bleibt versionsgebunden und darf DENY nicht still überschreiben.

### HIGH — Ack-Semantik für DENY ist widersprüchlich

Beleg:
- `docs/spec-e3-design.md:27` sagt Ack wird wie ALLOW behandelt.
- `docs/spec-e3-design.md:36` beschreibt `blocking` als “alle UNKNOWN_BLOCK_ENFORCE + DENY ohne Ack”.

Risiko:
Wenn `DENY` per Ack freigeschaltet werden kann, ist DENY faktisch nur UNKNOWN mit anderem Namen. Für sicherheitskritische bekannte Bypässe sollte DENY nicht per normalem Admin-Ack zu ALLOW werden, sondern maximal als expliziter Tier-2-/Out-of-scope-Entscheid mit Human-Gate.

Auflage:
Semantik trennen: `UNKNOWN_BLOCK_ENFORCE` kann per versionsgebundenem Ack akzeptiert werden; `DENY` bleibt blockierend oder braucht einen separaten, höherwertigen Sign-off-Typ mit klarer Dokumentation.

### MEDIUM — Re-Evaluation-Trigger sind zu weich spezifiziert

Beleg:
- `docs/spec-e3-design.md:41` nennt Ack, Komponenten-Install/Update, `hass.config.components`/Reload und Recompile.

Risiko:
`hass.config.components` bildet geladene Domains ab, während `async_get_custom_components` installierte Custom-Integrationen liefert. Ein neu installierter, aber noch nicht geladener Custom-Ordner kann dadurch bis zum nächsten expliziten Recompile unentdeckt bleiben, obwohl E3 vor Writes auf installierte Komponenten fail-closed sein soll.

Auflage:
D9 unmittelbar vor jedem Enforce-Write vollständig aus `async_get_custom_components(hass)` evaluieren. Listener sind nur Cache-Invalidierung/Preview-Komfort, nicht die Sicherheitsquelle.

## Positive Befunde

- `async_get_custom_components(hass)` ist als read-only Enumerationsanker plausibel: HA lädt Custom Components über `async_add_executor_job`, also ohne off-loop Scan im Tessera-Code.
- Lifecycle-Delete-Reihenfolge `Rebind -> Remove` ist konservativ und passt zum No-Drop-/No-Lockout-Vertrag.
- C1 ist ehrlich: System-Kontext als dokumentierter Trust-Boundary-Ausschluss ist besser als eine nicht belegbare Monkeypatch-Scheinsicherheit.
- C3 persistent in `.storage/tessera.state` ist für Restore/Uninstall/Crash-Sicherheit die richtige Richtung.

## Ergebnis

Kein E3-Go aus diesem Dokument. E2.5 kann nach obigen D9-Auflagen als non-scharfer, read-only PR spezifiziert werden. E3-Scharf bleibt gesperrt bis D10, Human-Go, Soak, Secret-/Restore-/Target-Isolation-Gates und ein Panel-Gate für E2.5/E3.
