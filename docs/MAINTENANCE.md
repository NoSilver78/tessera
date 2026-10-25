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

1. **Code-Guard auf die validierten HA-Feature-Linien.** Der Auth-Schreibpfad prüft im Code gegen die
   Menge validierter HA-**Feature-Linien** `YEAR.MONTH` (derzeit **`2026.7`**, **`2026.8`**,
   **`2026.9`** und **`2026.10`**, `SUPPORTED_HA_AUTH_FEATURES`; neueste validiert `2026.10.4`). Jedes
   Patch innerhalb einer validierten Linie passiert; auf einem **nicht validierten Monats-Release** wird der
   Enforce-/Schreibpfad **fail-closed blockiert** (`compute_enforce_plan` liefert einen
   `blocked`-Plan) — **kein** nativer Write; wirksam bleibt der read-only `monitor`-Zustand. HA liefert
   Auth-Store-Breaking-Changes nur in der Monats-Linie aus; die Patch-Toleranz ist daher bewusst und
   kein blindes Weiterschreiben über Monatsgrenzen. Mehrere Linien gleichzeitig zu führen ist Absicht:
   wer eine HA-Version zurückhängt, verliert `enforce` nicht.

   **Frühwarnung in CI:** `tests/test_ha_auth_contract.py` prüft gegen das *installierte* HA (nicht
   gegen Test-Doubles) und wird **rot**, sobald CI auf einer Linie läuft, die noch niemand validiert
   hat — plus Struktur-Checks auf genau den privaten Subset (`AuthStore._groups`/`_data_to_save`,
   `models.Group`, `PolicyPermissions`), den die Adapter anfassen.
2. **HACS-Mindestversion (optional, derzeit NICHT gesetzt).** `hacs.json` wird bereits ausgeliefert,
   enthält aber **keinen** `homeassistant`-Pin: die `hacs/action`-Validierung lehnte den Wert als
   künftiges Minimum ab. Der **aktive** Schutz ist daher allein der Code-Guard aus #1; ein
   `hacs.json`-`homeassistant`-Pin (HACS blockt dann Installation/Update auf älteren Instanzen) kann
   beim Public-Flip als zweite Hürde nachgezogen werden, sobald HACS die Zielversion kennt.
3. **Fail-safe-to-monitor überall.** Jeder Fehler im Enforce-/Recovery-Pfad fällt auf den
   nicht-eingreifenden `monitor`-Modus zurück (kein Deny-all, kein stiller Halbzustand).

   > **Nuance (Dev-E2E 2026-07-01, `spike/reports/tessera-dev-e2e-report-2026-07-01.md`):** War
   > `enforce` einmal erfolgreich angewandt und wird eine *spätere* Re-Evaluation von der
   > D9-Vorprüfung geblockt (z. B. weil eine neue auth-berührende Component auftaucht), fällt der
   > Runtime auf `monitor` und legt ein Repairs-Issue an — **lässt aber die zuletzt angewandten
   > (restriktiveren) `tessera:`-Gruppen stehen**, bis ein Admin die Ursache auflöst (Ack bzw. Fix)
   > und einen sauberen `enforce`→`off`-Zyklus fährt. Das ist **kein** Halbzustand (der native
   > Zustand ist der letzte konsistente, *strengere* Apply — kein teilweiser Write) und **kein**
   > Sicherheits-Downgrade. Nur eine bewusste UX-Konsequenz: angezeigter `monitor`-Modus und noch
   > vorhandene native Gruppen können auseinanderlaufen, bis der Admin `enforce` erneut setzt.

## Prozess pro HA-Release

Für **jedes** neue Home-Assistant-Release:

1. **Quellen diffen (bevor irgendetwas angehoben wird).** Die neue Linie ist erst dann validiert, wenn
   der von den Adaptern angefasste Subset unverändert ist. Konkret gegen den zuletzt validierten Tag:

   ```
   homeassistant/auth/auth_store.py     # _groups, _store, async_get_groups, _data_to_save
   homeassistant/auth/models.py         # models.Group (id/name/policy/system_generated)
   homeassistant/auth/permissions/      # PolicyPermissions + entities-Policy-Shape
   ```

   Ein reiner Versions-Bump ohne diesen Diff ist **kein** Validieren, sondern Raten.
2. **Testen** — die Integrations-Tests gegen die neue HA-Version laufen lassen (idealerweise per
   nightly/matrix-CI, die mehrere HA-Versionen abdeckt). Besonderes Augenmerk: Auth-Store-Schreiben,
   Rebind, Restore. `tests/test_ha_auth_contract.py` prüft dabei das installierte HA selbst.
3. **Bei grünem Lauf:** die neue Linie zu `SUPPORTED_HA_AUTH_FEATURES` hinzufügen (die alte Linie
   **bleibt** drin, solange ihr Subset kompatibel ist) und `SUPPORTED_HA_AUTH_VERSION` auf die neueste
   getestete Patch-Version setzen; ggf. ein neues PATCH/MINOR-Release schneiden.
4. **Bei gebrochener interner API:**
   - den Versions-Guard anpassen (neue HA-Version erkennen, Enforce fail-closed blockieren),
   - (optional, sobald gesetzt) die `hacs.json`-Mindestversion anheben,
   - eine neue **MAJOR**-Version veröffentlichen (Bruch der Kompatibilität),
   - den Bruch im Changelog + den Release Notes klar benennen.

## Validierte Linien (Diff-Protokoll)

Jede Zeile ist das Ergebnis von Schritt 1+2 des Prozesses oben — kein Versions-Bump, sondern ein
nachvollziehbarer Diff gegen den zuvor validierten Tag.

| Linie | Diff gegen | Ergebnis | Verifiziert |
|---|---|---|---|
| `2026.7` | — | Basis-Linie | 2026-07-06 (v0.9.1) |
| `2026.8` | 2026.7.1 | `auth_store.py` byte-identisch, `permissions/` unverändert, `models.Group` unverändert | 2026-08-16 (v0.9.2) |
| `2026.9` | 2026.8.1 | `auth_store.py` + `models.py` byte-identisch. `permissions/entities.py` geändert (Area-Sub-Policy löst jetzt die *effektive* Area eines Geräts auf, `dr.async_get_effective_area_id`, für Child-Device-Vererbung) — **für Tessera nicht erreichbar**: der Compiler emittiert ausschließlich `entity_ids`-Leaves (hart geprüft in `_assert_allow_only_policy`) | 2026-10-25 (v0.9.4) |
| `2026.10` | 2026.9.4 | `auth_store.py` byte-identisch; `models.Group` unverändert (`models.py` bekam nur PKCE-Felder am `AuthFlowContext` = Login-Flow, nicht das Gruppenmodell). `permissions/` tauschte `voluptuous` gegen `probatio` (HA ruft `install_as_voluptuous()` beim Import) — Schema-**Bibliothek** bei identischer Policy-Shape; HAs echtes `PolicyPermissions` gewährt weiterhin genau Tesseras allow-only-Policy | 2026-10-25 (v0.9.4) |

Belegt durch `tests/test_ha_auth_contract.py` gegen das jeweils installierte HA — der CI-Matrix-Job
`HA auth contract` fährt jede dieser Linien (`2026.7.1`, `2026.8.1`, `2026.9.4`, `2026.10.4`).

> **Child-Devices (HA 2026.9+):** Ein Child-Device ohne eigene Area erbt die Area des
> Eltern-Geräts. `resolver._device_area_by_id()` löst diese **effektive** Area auf — dieselbe Regel
> wie HAs `device_registry.async_get_effective_area_id` — und Child-Devices zählen auch im
> Label-Pfad, wenn sie das Label **selbst** tragen (HA erbt Labels nie vom Eltern-Gerät). Eine am
> Child gesetzte Area gewinnt immer. Geschlossen, Release offen (CHANGELOG `[Unreleased]`).

> **`DeviceRegistry.devices` als Mapping ist ab HA 2026.9 deprecated** (`report_usage`, entfällt in
> **2027.9**); unterstützt ist nur noch das Iterieren der Einträge. `resolver._iter_device_entries()`
> liest ein echtes Mapping (HA 2026.7/2026.8, Test-Doubles) weiter als Mapping und iteriert alles
> andere — die Linie bestimmt also den Zugriffsweg, ohne HA-Version abzufragen. **Vor HA 2027.9**
> muss der Mapping-Pfad raus; bis dahin ist er die Kompatibilität zu den älteren validierten
> Linien.

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
