# Pilzbuche 8 — Haushalts-RBAC-Modell (Soak-Referenz) + motivierte Roadmap-Features

**Datum:** 2026-07-01 · **Zweck:** das reale Haushaltsmodell für den Tessera-Soak festhalten + zwei durch echte Daten belegt-motivierte Roadmap-Features. **Scope:** Ein-Haushalt (kein Mehrparteien — s. Isolations-Report).

## HA-Struktur (aus der Registry gelesen, read-only)
**4 Etagen (floor_id), 39 Areas:**
- **UG** (`ug`, 9): `ug_bad` `ug_eingang` `ug_elektro` `ug_flur` `ug_hvac`(Heizung/Lüftung) `ug_lager` `ug_waschkueche` `ug_werkstatt` `ug_zimmer`
- **EG** (`eg`, 11): `eg_wohnen` `eg_kuche` `eg_ankleide` `eg_bad` `eg_wc` `eg_buero` `eg_eingangsbereich` `eg_flur_keller` `eg_garderobe` `eg_schlafzimmer` `eg_windfang`
- **OG** (`og`, 14): `og_wohnen` `og_bad` `og_wc` `og_dachraum_treppenhaus` `og_dachraum_wohnen` `og_dachraum_zimmer1` `og_flur_bad` `og_flur_hwr` `og_flur_mitte` `og_hwr` `og_loggia` `og_treppenhaus` `og_zimmer_1` `og_zimmer_2`
- **Außen** (`ab`, 5): `ab_eingang` `ab_terrasse` `ab_dachkante` `ab_kellereingang` `ab_schuppen`

## Rollen (alle **non-admin**; Owner = Michael, außerhalb dieser Rollen)
| Rolle | read | control |
|---|---|---|
| **`ug_nutzer`** | alle 9 UG-Areas | `ug_zimmer` `ug_eingang` `ug_flur` `ug_bad` *(Test-Asymmetrie: waschkueche/werkstatt/lager/elektro/hvac nur read)* |
| **`eg_nutzer`** | alle 11 EG + UG außer `ug_zimmer`/`ug_bad` | alle 11 EG + `ug_eingang` `ug_flur` `ug_elektro` `ug_hvac` `ug_lager` `ug_waschkueche` `ug_werkstatt` |
| **`og_nutzer`** | alle 14 OG | alle 14 OG |

**Kein Zugriff** für `eg_nutzer` auf `ug_zimmer` + `ug_bad` (Privaträume UG-Bewohner) — in allow-only schlicht *nicht gewährt*.
**Wetterstation** (`og_nutzer` sollte sie sehen) → **deferred:** 117 KNX-Entities, Label `aussen_wetter`, **keine Area** → braucht den Label-Selektor (s. u.). Bis dahin: kein Wetter.

## Motivierte Roadmap-Features (durch dieses reale Modell belegt, nicht theoretisch)
1. **Floor-Selektor** *(nächster Task — s. `tessera-t-floor-selector-task-claude-2026-07-01.md`)*. Das Modell ist **etagen-basiert**. Mit Area-only-Grants sind es **~41 Grants**; mit Floor-Grants **~14** (og `1`, eg `1`+7 UG, ug `1`+4). Größter Hebel bei `og_nutzer` (14→1) und dem EG-Teil (11→1). Die „außer"/„control-Teilmenge"-Fälle bleiben area-fein.
2. **Label-Selektor** *(später)*. Die Wetterstation ist label-organisiert (`aussen_wetter`), area-los — nur ein Label-Selektor kann sie granten. Vermutlich weitere KNX-Label-Gruppen.

Beide stehen in `docs/spec-enforce.md` (floor/label/category-Ausbau, v1 = area+entity+domain) — dieses Modell **priorisiert** sie belegt.

## Bau-Reihenfolge
T1 Membership-Writer ✅ (gemergt) → **Floor-Selektor** (macht den Modell-Bau erträglich) → Modell effizient bauen + Personen via `tessera.set_membership` zuweisen → Soak → Label-Selektor (Wetter).
