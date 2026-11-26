# Stille Fallbacks auf HA-Interna: Analyse, Empfehlung, Alternativen

Claude · 2026-11-26 · Auslöser: hoher Punkt 2 aus
[Gate Review PR #73](gate-review-pr73-auto-recompile-claude-2026-11-26.md) —
„wie verhindern wir diesen Fehler in Zukunft?"
Jede Option ist **gebaut und gemessen**, nicht nur überlegt; Belege stehen jeweils dabei.
Validierter Gesamtstand als Patch: [`silent-ha-fallbacks-patch-claude-2026-11-26.diff`](silent-ha-fallbacks-patch-claude-2026-11-26.diff)

## 1. Die Fehlerklasse — und sie ist größer als der eine Fund

Der Fund war `getattr(user, "invalidate_cache", None)`: verschwindet die Methode, wird daraus ein
lautloses No-op. Beim Suchen nach Geschwistern zeigte sich, dass das **Muster** das Problem ist, nicht
die Stelle. Inventar über `custom_components/tessera/`:

| Stelle | Fallback | Richtung bei Wegfall |
|---|---|---|
| `_user_helpers._is_unmanaged_user` | `getattr(user, "is_owner", False)`, `getattr(user, "system_generated", False)` | **unsicher** — Owner gilt als verwaltbar |
| `auth_adapter._is_managed_user` | dieselben zwei | **unsicher** — Owner landet in der verwalteten Menge |
| `auth_adapter._assert_managed_user` | dieselben zwei | **unsicher** — der Guard, der Owner-Writes verhindert, hört auf zu greifen |
| `auth_adapter._assert_owner_or_admin_survives_in` | `getattr(user, "is_active", True)` | sicher — zählt Überlebende unter, blockiert eher |
| `auth_adapter._is_active_owner_or_admin` | `is_active`, `system_generated`, `is_owner` | gemischt |
| `auth_adapter._invalidate_permission_cache` (+3 Inline-Kopien) | `getattr(user, "invalidate_cache", None)` | **unsicher** — verengte Policy gewährt weiter bis zum Neustart |
| `__init__`, `mode_manager`, `auth_adapter._user_id` | `getattr(user, "id", None)` | sicher — wird unmittelbar validiert, fehlender Wert wirft/überspringt |

Die privaten Attribute, die Tessera **direkt** liest (`hass.auth._store`, `store._groups`,
`store._data_to_save`), sind dagegen nicht das Problem: ein Wegfall wirft, und die Contract-Tests
decken sie ab. **Das Projekt hat das richtige Muster also schon — die `getattr`-Fallbacks sind die
Ausnahme, die es aushebelt.** Und ihr Grund ist nicht HA, sondern die eigenen Test-Doubles: ein
`FakeUser`, dem ein Feld fehlte, wurde in Produktionscode mit einem permissiven Default erkauft.

## 2. Die Optionen, jede validiert

### Option B — strikter Attributzugriff statt permissiver Fallbacks ⭐

`user.is_owner` statt `getattr(user, "is_owner", False)`. Ein Wegfall wirft dann `AttributeError`,
und der Enforce-Pfad verwandelt das über `_compile_for_mode_safely` in einen **blockierten Plan plus
Repairs-Hinweis** — fail-closed statt still.

**Validierung** (im Wegwerf-Worktree auf `feat/auto-recompile`):

- Alle 11 permissiven User-Fallbacks strikt gemacht → zuerst **7 rote Tests**, alle in
  `tests/test_mode_manager.py`. Ursache: dessen `FakeUser` kennt `is_active` nicht. **Eine Zeile**
  im Double behebt alle sieben. Zwei weitere Doubles (`test_init`, `test_restore`) brauchten
  `invalidate_cache` — drei Zeilen je Datei.
- Danach: **424 passed, 5 skipped** — identisch zum Stand vorher. `ruff`, `black`,
  `mypy --strict` grün gegen **HA 2026.8.2 und 2026.11.1**.
- Umfang: **+22/−27 in 5 Dateien**, netto **5 Zeilen weniger** Code.
- Nebenbeleg für die Fail-closed-Richtung: als die Doubles das Attribut noch nicht hatten, erschien
  der `AttributeError` in den Testausgaben als `detail: ['AttributeError']` eines **blockierten
  Plans** — der Enforce-Pfad fängt ihn also tatsächlich ab, statt eine falsche Entscheidung zu
  treffen. Das ist gemessen, nicht erhofft.

**Grenze:** wirkt erst zur Laufzeit, und zwar wenn die Stelle erreicht wird.

### Option F — Typ-Contract, von `mypy` pro HA-Linie geprüft ⭐

Eine neue Datei `custom_components/tessera/_ha_contract.py`, deren Inhalt **vollständig unter
`TYPE_CHECKING`** steht: ein `Protocol` mit genau der `User`- und `Group`-Oberfläche, die Tessera
liest, und je eine Funktion, die HAs echten Typ darauf zurückgibt. Fehlt ein Member, scheitert der
Typcheck. Null Laufzeitkosten.

**Validierung:**

- `mypy --strict` grün gegen **2026.8.2 und 2026.11.1**.
- **Mutationsprobe:** ein Member ins Protocol, das HA nicht hat →
  `error: Incompatible return value type (got "User", expected "_UserLike")` +
  `note: "User" is missing following "_UserLike" protocol member: …`. Also exakt benannt.
- Beim Bauen hat der Mechanismus sofort einen **echten** Fehler in meinem ersten Entwurf gefunden:
  `Group.policy` ist HAs `PolicyType` (verschachtelte Mappings), nicht `dict[str, object]`. Besser
  kann man eine Prüfung nicht einführen als damit, dass sie beim ersten Lauf etwas findet.
- Wirkt **ohne neue Infrastruktur**: `mypy` läuft seit v0.9.5 in der Contract-Matrix **pro
  validierter Linie** und nightly gegen die Vorabversion. Ein Wegfall in einer Beta fällt damit
  ungefähr eine Woche vor HAs Release auf.

**Grenze:** prüft die **Form**, nicht das **Verhalten**. `invalidate_cache` könnte existieren und
nichts mehr leeren.

### Option A — Verhaltens-Contract-Test gegen das installierte HA

Genau die Lücke von F schließen: `models.User` bauen, `permissions` lesen, `invalidate_cache()`
rufen, prüfen, dass der Cache-Eintrag aus `__dict__` verschwunden ist.

**Validierung:**

- Vorbedingung geprüft: `models.User(name=…, perm_lookup=None, groups=[], id=…)` lässt sich **ohne
  `hass`-Fixture** bauen; `permissions` landet in `__dict__`; `invalidate_cache()` entfernt es.
  (Auf 2026.11.1 nachgefahren.)
- Test in `tests/test_ha_auth_contract.py`: **5 passed** auf 2026.11.1.
- **Mutationsprobe:** den `invalidate_cache()`-Aufruf entfernen → rot mit der beabsichtigten
  Meldung („…would keep granting until restart").

**Grenze:** deckt genau das ab, was man hineinschreibt — kein Netz gegen die *nächste* Stelle.

### Option D — Scanner, der neue stille Fallbacks verhindert

Ein Test, der die Komponente per AST nach dreiargumentigem `getattr` durchsucht und jeden Fund
verlangt: entweder strikt lesen oder **mit Begründung** in einer Allowlist stehen.

**Validierung:**

- Gebaut, grün: **2 passed**. Die Allowlist enthält am Ende genau drei Einträge, und zwar die
  belegbar harmlosen: `child_devices` (gibt es erst ab HA 2026.9, muss optional sein), `version`
  (Manifeste ohne Version sind erlaubt) und die drei `id`-Lesungen, deren Wert unmittelbar danach
  validiert wird.
- Der Scanner hat beim Bauen den Reststand **selbst korrekt ermittelt**: nach Option B blieben
  exakt diese drei `id`-Stellen übrig, und ein von mir falsch gesetzter Allowlist-Eintrag
  (`_user_helpers.py:group_ids`, dort steht `hasattr`, kein `getattr`) fiel durch den
  Stale-Check auf.
- **Mutationsprobe:** permissiven `is_owner`-Fallback in den Owner-Guard zurückbauen → rot, mit
  `_user_helpers.py:17 getattr(..., 'is_owner', <default>)`.

**Grenze:** syntaktisch. Wer `try/except AttributeError` schreibt oder `hasattr` benutzt, läuft
vorbei. Der Zweck ist nicht Dichtheit, sondern dass das Hinzufügen eine **Entscheidung** wird.

### Option C — Startup-Probe, die die Oberfläche beim Setup prüft

Beim Laden des Entry alle benötigten Symbole prüfen und bei Fehlen `enforce` verweigern.

**Bewertung — nicht gebaut, bewusst:** Option B liefert das Verhalten schon, nur später (beim
ersten Benutzen statt beim Setup), und das ist belegt (siehe B: der `AttributeError` wird zum
blockierten Plan). Eine eigene Probe wäre eine zweite Liste derselben Symbole, die mit F und A
auseinanderlaufen kann. **Kosten/Nutzen negativ**, solange der Enforce-Pfad fail-closed ist.

### Option E — die Abhängigkeit deklarieren oder pinnen

**Verworfen, nicht möglich.** HA deklariert diese Interna nicht; es gibt nichts zu pinnen. Geprüft
im Zuge von ADR 0006: ab 2026.9 deklariert HA nur noch `probatio`, `voluptuous` liegt transitiv bei —
dasselbe Muster. Für `auth.models` gibt es nicht einmal das.

## 3. Empfehlung

**B + F + D, in dieser Reihenfolge — und A für die eine Stelle, an der Verhalten zählt.**

Die drei greifen auf verschiedenen Ebenen, und keine ersetzt eine andere:

| | wirkt | wann | Kosten |
|---|---|---|---|
| **B** strikter Zugriff | Laufzeit, fail-closed | wenn die Stelle läuft | −5 Zeilen netto, 1 Zeile Double |
| **F** Typ-Contract | Typcheck | **pro HA-Linie + nightly**, ~1 Woche vor dem Release | ~50 Zeilen, keine Laufzeit |
| **A** Verhaltenstest | Testlauf gegen echtes HA | pro Linie + nightly | ~20 Zeilen |
| **D** Scanner | Testlauf | bei jedem Commit | ~80 Zeilen, Allowlist mit 3 Einträgen |

Warum in dieser Reihenfolge: **B** nimmt die Gefahr weg (permissiv → fail-closed), **F** zieht die
Entdeckung nach vorn (vor HAs Release statt danach), **D** verhindert den Rückfall, **A** deckt das
eine Verhalten ab, das eine Form-Prüfung nicht sehen kann. Zusammen kosten sie weniger Code als die
Fallbacks, die sie ersetzen — der Gesamtstand hat **427 passed, 5 skipped** und ist auf beiden
geprüften HA-Linien sauber.

Ehrlich dazugesagt: das ist kein Schutz gegen HA-Änderungen, sondern gegen **unbemerkte**
HA-Änderungen. Bricht HA `models.User`, bleibt Arbeit — sie fällt nur vorher auf und in die sichere
Richtung.

### Alternativen, wenn weniger gewollt ist

- **Nur B.** Das Minimum mit dem größten Effekt: aus „still permissiv" wird „laut fail-closed".
  Entdeckung bleibt reaktiv (beim Benutzen), aber die unsichere Richtung ist weg.
- **Nur A+F ohne B.** Wenn die Fallbacks aus Rücksicht auf die Doubles bleiben sollen: CI merkt den
  Wegfall, die Produktionssemantik bleibt aber permissiv, bis jemand reagiert. Schwächer, aber
  billiger im Diff.
- **D später.** Der Scanner ist der am wenigsten dringende Teil — er schützt vor dem *nächsten*
  Fall, nicht vor dem jetzigen.

## 4. Codex-Aufgaben

### Aufgabe 1 — Option B

```text
Aufgabe: Permissive getattr-Fallbacks auf HA-User-Attribute durch strikte Zugriffe ersetzen.

Betroffene Dateien:
- custom_components/tessera/_user_helpers.py
- custom_components/tessera/auth_adapter.py
- tests/test_mode_manager.py, tests/test_init.py, tests/test_restore.py (nur Doubles)

Regeln / was nicht ändern:
- Keine Logik umbauen: nur getattr(user, "x", default) -> user.x.
- getattr(user, "id", None) an den drei Stellen BLEIBT: der Wert wird unmittelbar validiert.
- Keine Protokolle, keine neuen Dateien in dieser Aufgabe.
- Tests nicht abschwächen; Doubles nur um die fehlenden Felder ergänzen.

Erwartete Umsetzung:
- _is_unmanaged_user, _is_managed_user, _assert_managed_user,
  _assert_owner_or_admin_survives_in, _is_active_owner_or_admin und
  _invalidate_permission_cache lesen is_owner / system_generated / is_active /
  invalidate_cache strikt.
- Die drei inline wiederholten invalidate_cache-Fallbacks in auth_adapter.py rufen
  stattdessen _invalidate_permission_cache(user).
- tests/test_mode_manager.py: FakeUser bekommt `is_active: bool = True`.
- tests/test_init.py und tests/test_restore.py: die User-Doubles bekommen eine
  invalidate_cache-No-op-Methode.

Tests:
- Volle Suite grün (erwartet: 424 passed, 5 skipped wie vorher).
- Mutationsprobe: is_active im FakeUser von test_mode_manager wieder entfernen -> 7 Tests
  müssen rot werden. Ergebnis im Abschlussbericht nennen.

Definition of Done: ruff, black, mypy --strict grün; Suite grün; Diff nur in den genannten
Dateien; kein permissiver getattr auf User-Attribute mehr vorhanden.

Abschlussbericht: geänderte Dateien, Diffstat, Testergebnis, Mutationsprobe.
```

### Aufgabe 2 — Option F

```text
Aufgabe: Typ-Contract für die gelesene HA-Auth-Oberfläche einführen.

Betroffene Dateien: custom_components/tessera/_ha_contract.py (neu)

Regeln / was nicht ändern:
- Der komplette Modulinhalt steht unter `if TYPE_CHECKING:` — zur Laufzeit passiert nichts.
- Kein Produktionscode importiert dieses Modul; es existiert für mypy.
- Keine eigenen Typen für HA-Strukturen erfinden: Group.policy ist
  homeassistant.auth.permissions.types.PolicyType (nicht dict[str, object] — das schlägt fehl).

Erwartete Umsetzung:
- Protocol _UserLike mit id: str, is_owner: bool, is_active: bool, system_generated: bool und
  def invalidate_cache(self) -> None.
- Protocol _GroupLike mit id: str, name: str | None, policy: PolicyType,
  system_generated: bool.
- Je eine Funktion, die models.User bzw. models.Group annimmt und das Protocol zurückgibt.
- Modul-Docstring erklärt, warum: ein getattr-Fallback verbarg den Wegfall hinter einem
  permissiven Default; hier scheitert stattdessen der Typcheck, pro validierter HA-Linie
  und nightly gegen die kommende.

Tests:
- mypy --strict gegen mindestens zwei installierte HA-Linien grün (lokal 2026.8.2 und
  2026.11.1 sind nachgewiesen machbar).
- Mutationsprobe: ein Member ins Protocol schreiben, das HA nicht hat -> mypy muss mit
  "is missing following protocol member" rot werden.

Definition of Done: mypy grün auf beiden Linien, Mutationsprobe dokumentiert, keine
Laufzeitänderung (Modul wird nirgends importiert).

Abschlussbericht: neue Datei, mypy-Ausgaben je Linie, Mutationsprobe.
```

### Aufgabe 3 — Option A

```text
Aufgabe: Verhaltens-Contract für den Permissions-Cache.

Betroffene Dateien: tests/test_ha_auth_contract.py

(Entspricht Aufgabe 2 aus dem Gate Review zu PR #73 — dort steht die ausführliche Fassung.
Kurz: models.User ohne hass bauen, permissions lesen, invalidate_cache() rufen, prüfen dass
der Cache-Eintrag aus __dict__ verschwunden ist. Mutationsprobe: Aufruf entfernen -> rot.)
```

### Aufgabe 4 — Option D

```text
Aufgabe: Scanner gegen neue stille Fallbacks auf HA-Attribute.

Betroffene Dateien: tests/test_no_silent_ha_fallbacks.py (neu)

Regeln / was nicht ändern:
- Kein Produktionscode.
- Der Scanner arbeitet per ast über custom_components/tessera/*.py, nicht per Regex.
- Erst nach Aufgabe 1 erledigen, sonst ist die Allowlist voll mit Altlasten.

Erwartete Umsetzung:
- Alle Aufrufe `getattr(x, "name", default)` (drei Argumente) sammeln.
- Jeder Fund muss in einer ALLOWED-Tabelle {datei: {attribut: begründung}} stehen, sonst
  schlägt der Test fehl, mit Datei:Zeile in der Meldung.
- Zweiter Test: Allowlist-Einträge ohne zugehörige Fundstelle sind stale und schlagen fehl.
- Startinhalt der Allowlist: resolver.py/child_devices (erst ab HA 2026.9),
  d9_gate.py/version (Manifest ohne Version erlaubt), __init__.py+auth_adapter.py+
  mode_manager.py/id (Wert wird unmittelbar validiert).

Tests:
- Beide Tests grün.
- Mutationsprobe: einen permissiven getattr-Fallback in _user_helpers.py einbauen ->
  Test rot mit Datei:Zeile.

Definition of Done: grün, Mutationsprobe dokumentiert, Allowlist enthält nur begründete
Einträge.

Abschlussbericht: neue Datei, Testergebnis, Mutationsprobe, Allowlist-Inhalt.
```

## 5. Nicht prüfbare Punkte

- **Ob HA `models.User` je bricht.** Die Analyse sagt nur, dass es *auffallen* würde. Heute ist
  `auth/models.py` zwischen 2026.11.1 und 2026.12.0b0 byte-identisch.
- **Verhalten gegen 2026.12.0b0.** Validiert habe ich gegen 2026.8.2 und 2026.11.1; für die Beta
  liegt nur der Quellen-Diff vor (`models.py` unverändert), kein Lauf.
- **Ob der Scanner in der Praxis stört.** Die Allowlist hat heute drei Einträge; ob sie bei
  realer Weiterentwicklung schlank bleibt, zeigt erst die Nutzung.
