# Tessera — CM5-Monitor-Soak-Plan

> ⚠️ **Monitor-only, Nullrisiko.** Der Soak läuft **ausschließlich** in `monitor` auf der Live-Instanz **CM5** (`homeassistant-cm5`). Monitor schreibt **nichts** in den nativen HA-Auth-Store (bewiesen: Dev-E2E `spike/reports/tessera-dev-e2e-report-…`) → er kann niemanden aussperren. **Der Enforce-Flip ist ein separater, eigener Schritt** (unten) mit eigenem Go.
>
> Rollen: **[M]** = Michael (Install/UI, HAOS ohne SSH), **[C]** = Claude (Aufbau/Beobachtung, read-only + Monitor-Writes in den Tessera-Store, nie nativ).

## Zweck — was der CM5-Soak liefert (und der Dev-Soak nicht kann)
Der Dev-E2E hat den **Mechanismus** bewiesen (Enforce-Write, Restore, Floor-Expansion, Concurrency-Fix, **Runtime-Durchsetzung** einer echten Session). Was nur die **echte** Instanz liefert:

1. **Scale-Compile-Korrektheit** — der Resolver gegen die **echten ~1400 Entities / 39 Areas / 4 Floors / echte Devices** (Dev: 9 synthetische). Baut das reale 3-Rollen-Modell (`exchange/2026-07-01/tessera-haushaltsmodell-pilzbuche8-…`) zu den richtigen Entity-Mengen auf? Bleibt die Kompilierung performant + korrekt?
2. **D9-Blocker-Enumeration** — CM5 trägt viele HACS-Custom-Components. D9 ist in Monitor **beobachtbar** (Enforce-Plan-Preview), ohne zu blocken. Der Soak liefert die **exakte Liste**, welche Components enforce vetoen würden → das ist *das* Gate für den späteren Enforce-Flip.
3. **Linter an echtem Maßstab** — reale Cross-Rollen-Konflikte (User in mehreren Rollen, überlappende Grants) sichtbar machen (concept §5.2, Cross-Rollen-Deny unmöglich → most-permissive-Merge).
4. **Stabilität/Leak** — lädt sauber, übersteht CM5-Neustarts/HA-Updates, keine Fehler/Speicherwachstum über Tage.

## Voraussetzung — Install *(Michael-Aktion; HAOS, kein SSH, HA-MCP read-only)*
- **[M]** Tessera via **HACS Custom-Repository** installieren (`NoSilver78/tessera`, public) → Integration **„Tessera"** hinzufügen. Default-Mode `monitor`; Panel „Tessera" erscheint.
- **Erwartung [C-verify]:** Integration lädt fehlerfrei · `.storage/auth` **unverändert** (kein `tessera:*`-Group) · Panel da.

## Ablauf
1. **[M]** Install + Integration hinzufügen (s.o.).
2. **[C]** Das **echte** Haushaltsmodell in `monitor` aufbauen: 3 Rollen (`ug/eg/og_nutzer`) via Options-Flow + Floor/Area-Grants via `tessera.set_floor_grant`/Matrix-Panel + Personen via `tessera.set_membership`. **Kein** nativer Write — reine Projektion.
3. **[C]** Gegen die reale Registry prüfen: Monitor-**Preview** (kompiliert die erwarteten Entity-Mengen?), **Linter** (reale Konflikte?), **D9-Verdikt** je Custom-Component ziehen → **D9-Blockerliste** als Evidence festhalten (`spike/evidence/…`).
4. **Laufenlassen ~3–7 Tage.** [C] periodisch (read-only): Fehler-Log, Preview-Konsistenz nach Registry-Änderungen/Neustarts/HA-Updates, Speicher/Ladezeit.

## Exit-Kriterien → GO / NO-GO für Enforce
Grün, wenn über die Dauer **alle** erfüllt:
- **0 Fehler/Tracebacks** (Tessera) im Log; Integration bleibt geladen über Neustarts/Updates.
- **Preview stabil + korrekt** am echten Maßstab (Modell kompiliert zu den intendierten Entity-Mengen; keine Drift nach Registry-Events).
- **Reales Modell lintet sauber** (Cross-Rollen-Konflikte bewusst aufgelöst oder = 0).
- **D9-Blockerliste vollständig + geklärt** — jede vetoende Component bewusst **geackt** (`tessera.acknowledge_component`) oder kuratiert klassifiziert; kein unbekannter Blocker offen.

## Danach — Enforce-Flip (SEPARAT, eigener Go)
**Nicht Teil des Soaks.** Voraussetzung: D9-Blocker geackt + Soak grün. Ablauf-Skizze:
- Rescue-Plan: **Owner bleibt immer unbeschränkt** (Owner-Bypass); Escape-Hatch = `mode=off` (löst Restore, schreibt nativ zurück) oder Deinstall. Eine eingeloggte Owner/Admin-Session offen halten.
- **Kurzes, eng beobachtetes Enforce-Fenster** (nicht sofort „enforce-als-Default"): `mode=enforce` setzen, native `tessera:*`-Gruppen + User-Rebind verifizieren, echte Session-Einschränkung stichprobenartig prüfen (wie Dev-A2), dann bewusst entscheiden, ob enforce bleibt.
- Erst nach stabilem Fenster: enforce als Default.

## Sicherheits-Leitplanken (verbindlich)
- **Nur `monitor`** während des gesamten Soaks. Default-Mode `monitor`.
- **Live-CM5 sonst read-only/tabu** — nur Tessera-Store-Writes (config/policy, nie nativ) + Lesen.
- Auth-/Enforce-**Scharftests nur `ha-tessera-dev`**, nie live.
- Der native Write passiert **erst** beim späteren, separat freigegebenen Enforce-Flip.
