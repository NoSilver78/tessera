# ADR 0006 — Schema-Bibliothek: Kompatibilität über vier HA-Linien statt Migration auf probatio
Stand 2026-10-25 · Status: **aktiv** · Entscheidung: Michael (2026-10-25)
· **revidiert** die Richtungsentscheidung „Option A" aus
[`exchange/2026-10-12/ha-2026-10-audit-claude-2026-10-12.md`](../exchange/2026-10-12/ha-2026-10-audit-claude-2026-10-12.md) §4
· berührt [ADR 0005](0005-by-group-v1-inert.md) **nicht**

## Kontext

Home Assistant hat `voluptuous` als Validierungs-Bibliothek durch **`probatio`** ersetzt, in zwei
Schritten, die nicht zusammenfallen (gemessen am installierten HA, nicht vermutet):

| Linie | deklarierte Dependency | Laufzeit: `import voluptuous` | HAs Annotationen |
|---|---|---|---|
| 2026.7 / 2026.8 | `voluptuous==0.15.2` | echtes voluptuous | voluptuous |
| **2026.9** | `probatio==0.11.4` | probatio (via Shim) | **noch voluptuous** |
| **2026.10** | `probatio==0.13.0` | probatio (via Shim) | **probatio** |

Der Shim ist HAs eigene Entscheidung: `homeassistant/__init__.py` ruft
`probatio.compat.install_as_voluptuous()` vor allem anderen, mit dem Kommentar *„Custom integrations
and a few dependencies still import voluptuous directly, so alias it to probatio in `sys.modules`
before anything imports it."* Zusätzlich liegt in einer HA-Installation weiterhin ein echtes
`voluptuous` (0.16.0), weil **`annotatedyaml` und `hass-nabucasa`** es noch benötigen — nicht mehr,
weil HA es deklariert.

Das Audit vom **2026-10-12** hat daraus „nur die Guard-Menge erweitern" mit **FAIL** bewertet und
drei Optionen vorgelegt; Michael entschied damals **Option A** (Migration der drei Dateien auf
`probatio.*`), mit der Konsequenz **HA ≥ 2026.9.0** und einer **verschobenen** statt erweiterten
Guard-Menge.

Am **2026-10-25** wurde faktisch das Gegenteil umgesetzt und mit **v0.9.4** veröffentlicht: die
Guard-Menge wurde auf `{2026.7, 2026.8, 2026.9, 2026.10}` **erweitert**, und der Schema-Import blieb
`voluptuous` — gebündelt in `custom_components/tessera/_vol.py`, das die Bibliothek zur Laufzeit
importiert und den Namen für den Typchecker bewusst untypisiert lässt (weil HAs Annotationen je
Linie auseinanderlaufen und kein konkreter Typ auf allen vier Linien passt).

## Entscheidung

**Option A wird revidiert. Die Kompatibilität zu 2026.7/2026.8 bleibt.**

- `SUPPORTED_HA_AUTH_FEATURES` bleibt **erweitert**: `{2026.7, 2026.8, 2026.9, 2026.10}`.
- Es gibt **kein** HA-Minimum von 2026.9 und **keinen** `hacs.json`-`homeassistant`-Pin.
- Die Schema-Bibliothek wird **nicht** auf `probatio.*` umgestellt. Einzige Importstelle bleibt
  `custom_components/tessera/_vol.py` (Laufzeit: `voluptuous`, Typchecker: untypisiert), die drei
  Nutzer (`__init__.py`, `config_flow.py`, `websocket.py`) importieren nur von dort.
- Der Austausch bleibt **vorbereitet**: eine Migration nach Option A ist eine Änderung an *einer*
  Datei (`_vol.py`), nicht an dreien.

## Begründung

1. **`off`/`monitor` sind für *jede* HA-Version dokumentiert.** Ein Minimum von 2026.9 — ob im Code
   oder als HACS-Pin — hätte Nutzern auf älteren Instanzen die Installation genommen, obwohl der
   read-only Pfad dort gefahrlos nützt. Das widerspricht der eigenen Zusage in README und Guide.
2. **Der Enforce-Pfad auf 2026.7/2026.8 ist nachweislich kompatibel.** Das Audit vom 12.10. hat die
   berührte Teilmenge geprüft, die Contract-Tests laufen gegen alle vier Linien grün (inklusive der
   ganzen Kette Grant → Compiler → HAs echtes `PolicyPermissions`). Es gibt keinen funktionalen
   Grund, diese Nutzer abzuschneiden.
3. **probatio ist API-identisch** (clean-room, als Drop-in gedacht). Der Nutzen einer Migration ist
   also kein Verhalten, sondern nur die Sauberkeit der Abhängigkeitskette — und die ist diesen
   Kompatibilitätsverlust jetzt nicht wert.
4. **HA unterstützt den Weg ausdrücklich.** Der Shim existiert laut HAs eigenem Kommentar genau für
   Custom Integrations, die `voluptuous` direkt importieren.
5. **Der Ausstieg ist billig.** Weil alles durch `_vol.py` läuft, ist Option A später ein
   Import-Tausch an einer Stelle — keine Migration mehr.

## Konsequenz

- **Bewusst akzeptiertes Risiko:** Tessera ruht auf zwei Dingen, die **kein Vertrag** sind — dem
  Shim (`install_as_voluptuous()`) und einem transitiv noch vorhandenen `voluptuous`
  (`annotatedyaml`, `hass-nabucasa`). Das Audit vom 12.10. nennt das zu Recht „wackelig"; die
  Revision bestreitet das nicht, sie wählt die Kompatibilität trotzdem.
- **Überwachung statt Hoffnung:** `tests/test_ha_schema_contract.py` prüft gegen das *installierte*
  HA, dass `import voluptuous` genau dann probatio liefert, wenn probatio da ist, und dass Tessera
  mit derselben Bibliothek baut, mit der HA validiert. `mypy --strict` läuft pro validierter Linie,
  der Nightly-Job `HA upcoming line (pre-release)` fährt beides gegen die kommende Linie.
- **Auslöser für eine erneute Vorlage** (dann gilt Option A, als **MAJOR**-Release mit HA-Minimum):
  1. `annotatedyaml` **und** `hass-nabucasa` führen `voluptuous` nicht mehr, **oder**
  2. HA ruft `install_as_voluptuous()` nicht mehr auf bzw. probatio entfernt `compat`, **oder**
  3. der Schema-Contract-Test wird rot.
  Jeder dieser Fälle ist eine sicherheitsnahe Produktänderung → neuer ADR, kein stilles Nachziehen.
- **v0.9.4 bleibt wie veröffentlicht.** Das Release ist im HACS-Default-Store; die Release-Notes
  beschreiben zutreffend, was es tut. Es wird nicht zurückgezogen.
- **Die 1.0.0-Frage bleibt offen** und ist von dieser Revision entkoppelt: ohne Kompatibilitätsbruch
  ist das nächste Release ein PATCH/MINOR. Ein MAJOR entsteht erst, wenn einer der drei Auslöser
  oben eintritt — oder wenn 1.0.0 bewusst als Reifegrad-Marke gesetzt wird (Soak, Dogfood,
  geschlossene Klick-UI-Lücken).
