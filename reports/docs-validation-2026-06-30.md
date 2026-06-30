Die Findings sind bereits belegt und konsolidiert. Ich gebe die Einschätzung und Gruppierung direkt aus.

---

**EINSCHÄTZUNG: READY MIT FIXES**

Die Doku ist inhaltlich tragfähig und der ehrliche Status-Rahmen (Warnbox, Statustabelle) ist vorhanden. Aber mehrere sicherheitskritische Claims (Version-Guard, HACS-Pin) versprechen Schutz, der im Repo noch nicht existiert — das muss VOR der Public-Schaltung stimmen, sonst verliert ein technischer Erst-Leser sofort Vertrauen. Kein Blocker ist konzeptionell, alle sind durch Datei-anlegen oder Text-präzisieren behebbar.

---

### HIGH (Public-Blocker)

**1. Version-Guard / HACS-Pin nicht im Repo vorhanden**
`README.md` (+ `docs/MAINTENANCE.md`, `SECURITY.md`, `manifest.json`)
- Problem: README (Z.91-92), MAINTENANCE ("Schutzschichten" #1) und SECURITY (Z.46-50) bewerben eine HACS-Mindestversionssperre als erste/äußere Schutzschicht im Präsens. Tatsächlich: **keine `hacs.json`**, **kein `homeassistant`-Key in `manifest.json`**. Die beworbene Sperre existiert nicht. SECURITY Z.50 verweist zudem explizit auf die nicht existierende `hacs.json` → Auditor läuft ins Leere.
- Fix: Entweder `hacs.json` (`"homeassistant": "<Version>"`) + manifest-`homeassistant`-Key tatsächlich anlegen (steht ohnehin als To-do), ODER alle drei Docs auf Futur umstellen ("wird vor dem ersten Release gepinnt"). Solange beides fehlt: kein Präsens-Claim.

**2. Falsche/inkonsistente HA-Mindestversion**
`README.md`
- Problem: README Z.54 nennt "Mindestversion 2026.3.0" als untere Grenze. Der einzige reale Auth-Guard (`auth_adapter.py`: `SUPPORTED_HA_AUTH_VERSION = "2026.6.4"`, exakt-Gleichheit, raised sonst) akzeptiert 2026.3.0 gar nicht. 2026.3.0 stammt laut RELEASE_READINESS (Z.77/207/331) aus einem **Brand-Icon-Feature-Gate** ("HA 2026.3+"), nicht aus dem Auth-Pfad. README verwechselt Frontend-Icon-Gate mit sicherheitskritischem Auth-Guard.
- Fix: Mindestversion an der getesteten Auth-Realität ausrichten (exakt 2026.6.4); Brand-Icon-Anforderung (2026.3+) sprachlich trennen. Klar sagen: Auth-Schreibpfad prüft auf exakt getestete Version, nicht auf Minimum.

**3. NIST-Referenz fachlich falsch**
`ROADMAP.md` (Z.16)
- Problem: "Tessera folgt dem NIST-RBAC-Referenzmodell (SP 800-162)" — SP 800-162 ist der **ABAC**-Guide, nicht RBAC. Die im selben Block gezeigte PAP→PDP→PEP-Kette ist genau die ABAC-Funktionspunkt-Kette aus 800-162. RBAC = INCITS 359. Die eigene `concept.md` (1.3 vs. 1.4) trennt das korrekt. Fachkundige Leser bemerken das sofort.
- Fix: "NIST-RBAC-Rollenmodell (INCITS 359) + ABAC-Funktionspunkt-Trennung aus NIST SP 800-162 (PAP/PDP/PEP)". `concept.md` ist die Vorlage.

**4. Veraltete GAP-Analyse (erledigte Blocker als offen)**
`RELEASE_READINESS.md` (§2/§4)
- Problem: Mehrere `[ ]`-Blocker sind auf release-prep erledigt: LICENSE (Z.173/291) existiert (MIT, 1071 B); SECURITY.md (Z.181) existiert (2716 B); GDPR-README-Notiz (Z.185) existiert (Abschnitt "Datenschutz"). Gate-1 (Z.287 ff.) listet "LICENSE fehlt" weiter als ROT-Blocker. Dokument datiert "Stand 2026-06-30" → trifft falsche Aussagen über den Repo-Zustand.
- Fix: LICENSE/SECURITY.md/GDPR auf `[x]`; aus Gate-1 entfernen. Echte Restblocker bleiben: hacs.json, Release/Tag, Brand-Icon, hacs/hassfest-Workflows, Repo-Description/Topics.

---

### MEDIUM

**5. Fallback-Mechanismus überzeichnet**
`README.md` (Z.94-95) + `docs/MAINTENANCE.md`
- Problem: "degradiert auf monitor ... statt hart zu crashen" suggeriert graceful Version-Degrade. Im Code: `_assert_supported_auth_version` **raised** `UnsupportedAuthVersion`; `compute_enforce_plan` fängt das und liefert "blocked"-Plan (mode_manager.py Z.130-132). Effektiv fail-closed Block, kein graziöser Degrade.
- Fix: "bei nicht unterstützter HA-Version wird der Enforce-/Schreibpfad fail-closed blockiert (kein nativer Write), wirksam bleibt read-only monitor". "Degradiert automatisch" nur bei echtem versionsabhängigem Auto-Fallback.

**6. Modulzahl falsch**
`RELEASE_READINESS.md` (Z.218)
- Problem: "20 Modulen" — tatsächlich 16 Python-Dateien (15 Module + `__init__.py`). Zahl 20 nicht belegbar.
- Fix: "16 Python-Dateien (15 Module + `__init__.py`)" oder neutral "~16 Module". Falls Nicht-.py-Artefakte mitgezählt: explizit so benennen.

**7. Stale README-Bestandsaufnahme**
`RELEASE_READINESS.md` (Z.160)
- Problem: README als "existiert (2752 B), user-facing machen" beschrieben — ist inzwischen überarbeitet (6889 B) und voll user-facing. Suggeriert fälschlich offenen Umbau.
- Fix: Z.160 auf user-facing/`[x]` setzen; veraltete Byte-Angabe entfernen.

**8. Mindestversion nirgends maschinell verankert**
`RELEASE_READINESS.md` / `README.md` / `docs/MAINTENANCE.md`
- Problem: README Z.54 sagt fix "2026.3.0", RELEASE_READINESS/MAINTENANCE abstrakt "<niedrigste getestete Version>" in noch nicht existenter `hacs.json`. Doppelnutzung von 2026.3.0 (Brands-Schwelle vs. getestete Untergrenze) verwirrt.
- Fix: `hacs.json` mit `"homeassistant": "2026.3.0"` anlegen (sofern das die getestete Untergrenze ist — vgl. Konflikt mit Finding 2, hier zuerst klären); konkrete Untergrenze explizit nennen; gegen Brands-Schwelle abgrenzen.

**9. Interner Jargon leakt an externe Leser**
`README.md` (Z.40-41) → `ROADMAP.md`
- Problem: README schickt jeden Leser nachdrücklich in die ROADMAP ("ganze Geschichte ... steht in der ROADMAP"); ROADMAP nutzt "E3.5", "Produkt-Gate (D9)", "dormant" unerklärt — Insider-Notizen des Bauprozesses, abschreckend fürs erste Public-Repo.
- Fix: Codes bei Erstnennung auflösen ("E3.5 – interner Schritt-Code") oder für die öffentliche Fassung ersetzen; "dormant" einmal erklären; README-Satz so rahmen, dass ROADMAP "Entwickler-Roadmap" ist, nicht Pflichtlektüre.

---

### LOW

**10. enforce-Modus-Tabelle vs. Laufzeitrealität**
`README.md` (Z.64)
- Problem: Tabelle beschreibt enforce als "schreibt aktiv ... greift real ein". Auf main inert: `__init__.py:_compile_for_mode` behandelt `MODE_ENFORCE` wie monitor, loggt "enforce ... not implemented yet". `mode=enforce` → monitor-Vorschau + Warnung, kein Write. Statustabelle sagt es, Modus-Tabelle selbst nicht.
- Fix: In/unter der Modus-Tabelle Hinweis: enforce auf main noch nicht verdrahtet (→ monitor-Vorschau + Warnung), bis E3.5 gemergt + E2E-validiert.

**11. Einleitungssatz Präsens-Overclaim**
`README.md` (Z.7-9)
- Problem: "schreibt sie in den HA-Auth-Store" liest isoliert als heute produktiv; faktisch nur enforce, das dormant ist. Erst Warnbox/Status ordnet ein.
- Fix: Modus-Vorbehalt schon im Satz: "...schreibt sie — im Modus enforce — in den Auth-Store" oder "kann ... schreiben".

**12. Inline-Brand-Pfad evtl. falsch (Singular)**
`RELEASE_READINESS.md` (Z.77/78/106)
- Problem: Pfad `custom_components/tessera/brand/icon.png` (Singular). HA/HACS-Standard erwartet `brands/` (Plural). Verzeichnis fehlt ohnehin. ⚠️ gegen Brands-Proxy-Quelle verifizieren.
- Fix: Pfad gegen Brands-Proxy-API (Z.79/331) prüfen, auf `brands/` korrigieren. README nennt keinen Pfad → keine Folgeänderung.

**13. CHANGELOG.md referenziert, fehlt, nicht als Gap gelistet**
`ROADMAP.md` / `RELEASE_READINESS.md` / `docs/MAINTENANCE.md`
- Problem: Drei Docs verweisen auf CHANGELOG.md (ROADMAP Z.80, RELEASE_READINESS §3, MAINTENANCE); Datei existiert nicht, fehlt aber in der GAP-Analyse (§2) — anders als hacs.json/LICENSE.
- Fix: CHANGELOG.md als offenen Punkt in §2 aufnehmen (Keep-a-Changelog-Stub mit Unreleased/0.1.0).

**14. KI-Bau-Modell ohne Wert-Einordnung**
`README.md` (Z.116-122) + `CONTRIBUTING.md` (Z.8-23)
- Problem: "Claude (Architektur/Gate) + Codex (Implementierung)" prominent, ohne den Sicherheitswert zu benennen; direkt daneben "nie real E2E-getestet". Kombination kann bei sicherheitskritischer Auth-Integration abschrecken statt Vertrauen schaffen.
- Fix: Mehrwert explizit ("jeder Auth-Schreibpfad von mehreren skeptischen Review-Durchläufen + Mutationstests angegriffen; Audit-Trail offen in `reports/`"); Ehrlichkeit beibehalten, dass Gating reales E2E nicht ersetzt.

**15. CI-Gates vs. rotes main**
`CONTRIBUTING.md` (Z.30/40) + `manifest.json`
- Problem: Setup fordert `mypy --strict` + `pytest` als harte Gates; Status sagt "CI gerade rot, im Fix". Erst-Beitragender, der dem Block wörtlich folgt, läuft in rote Checks ohne Warnung.
- Fix: Hinweis, dass main vor-Release zeitweise rot sein kann (analog Status-Tabelle); Setup-Block als "Ziel-Zustand" rahmen; prüfen, dass ruff/black/mypy/pytest wirklich die verwendeten Tools sind.

---

### NIT

**16. Headline-Satz Präsens** — `README.md` (Z.7-9): "schreibt ... in den Auth-Store" liest isoliert als "schon jetzt". Fix: optional "kann ... schreiben" / "(im enforce-Modus)". (Überlappt mit #11.)

**17. release-prep noch nicht in main** — `RELEASE_READINESS.md` (Z.8): Docs/LICENSE liegen auf `release-prep`; `origin/main` trägt alte README. Kein Textfehler. Fix: als Release-Schritt "release-prep → main mergen" sicherstellen/ergänzen, sonst greift HACS/GitHub die alte main-README ab.

**18. Help-wanted ohne klickbare Issues + Deutsch-only** — `README.md` (Z.105-109) / `CONTRIBUTING.md`: "Good first issues" nur prosaisch, keine echten GitHub-Issues; Contributor-Doku Deutsch-only, während CONTRIBUTING (Z.61) selbst um "en"-Übersetzung bittet. Fix: 2-3 echte `good first issue`-Issues anlegen; englischen Hinweis/README.en.md erwägen.

---

**Kern-Botschaft:** Die vier HIGH-Findings (Version-Guard/HACS-Pin nicht im Repo, falsche Mindestversion, NIST-Verwechslung, stale GAP-Analyse) sind echte Public-Blocker und alle in ein bis zwei Stunden behebbar — entweder Datei anlegen oder Text ehrlich machen. Achtung auf den **internen Widerspruch** zwischen Finding 2 (Auth-Guard = exakt 2026.6.4) und Finding 8 (README/hacs.json = 2026.3.0): vor dem Pin-Fix muss geklärt werden, welche Version die getestete Untergrenze ist.