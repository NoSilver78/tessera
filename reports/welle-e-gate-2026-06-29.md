# Welle-E-Gate (PR #12, D11/D13/D15) — 2026-06-29
Adversariales Panel (6 Skeptiker, mit Degenerations-Erkennung). **problemCount=1.**

## Entscheidung: FAIL (D11-Over-Claim) — Re-Spin nötig
D15 (enforce-kritisch) + D13 + Isolation sind sauber gemessen. **Ein** Claim ist über-claimt: **D11** behauptet eine *gemessene* Reihenfolge, nutzt aber hardcodierte Literale. Per Gate-Regel (`holds=false` auf lasttragendem Claim) → FAIL. Gesamturteil ohnehin **PARTIAL / kein Enforce-Go** (D7/A4 offen).

## Je Claim
- **D15-ENFORCE** — ✅ PASS. `full_superset = sorted({*original_groups, group_id})` → **Union, kein Subset** (D5-Lektion: REPLACE → volles Superset → kein Drop-Lockout); `async_update_user` real, Read-back verifiziert; Permission-Probe `forbidden_read/control=True` über echte `check_entity` nach `invalidate_cache`, **non-tautologisch** (`tessera-test-user` = non-admin → policy-getrieben, kein Bypass); off/monitor `native_write_observed=False`.
- **D15-RESTORE** — ✅ PASS. `before==after_restore=True`, `before==after_enforce=False` (echte Drift, kein No-op); Orphan-Gruppe `tessera:lifecycle` entfernt; kein Lockout (Owner/Admin-Token-Probe HTTP 200); load-bearing (Negativkontrolle kippt auf PARTIAL).
- **D11** — 🔴 **FAIL (over-claim, high).** `native_write_call_count`/`native_write_refused_before_call` = **Literale** (`__init__.py:1511-1512`), Gate prüft tautologisch gegen Konstanten (`:1587-1588`, `d0_preflight_spike.py:910-911`). Kein Spy um `async_update_user`. Richtung real (Write-Branch unerreichbar via `return :1502`) → high, nicht critical.
- **D13** — ✅ PASS (low). `updated=True` (groups 6→7, realer Write), `restored=True` (exakter Fingerprint-Revert), kein Lockout. In-Process-Sim ehrlich gelabelt.
- **Kein Streu-Grün** — ✅ (mit D11-Einschränkung).
- **Keine Regression** — ✅ Diff nur `spike/`; D5(PASS)/D7(PARTIAL) erhalten; Produkt enforce-frei.

## Auflagen (Re-Spin)
1. **D11 instrumentieren statt behaupten:** echten Call-Counter/Spy/Monkeypatch um `hass.auth.async_update_user`; `native_write_call_count`/`native_write_refused_before_call` aus der **Messung** ableiten; tautologisches Gate (`__init__.py:1587-1588`, `d0_preflight_spike.py:910-911`) auf den gemessenen Zähler umstellen. `native_write_blocked` ehrlich (Branch-not-reached ≠ „blocked") oder umbenennen.
2. Bis D11 gemessen: Report-Summary von „refuses enforce **before** native auth write" auf die belegbare Aussage zurücknehmen (Versions-Mismatch-Branch erreicht Write-Block nicht; Fingerprint unverändert).
3. **D5-Auflagen mitnehmen** (aus `d5-gate-2026-06-29.md`, im Rebase nicht gefoldet): `auth_store_corrupted` umbenennen · Seeds @754/@761 entliteralisieren · `test_d5_verdicts.py` in CI.

## Re-Gate
Nur **D11** muss neu — D15/D13/Restore/Isolation sind bereits verifiziert. Nach Fix: CI grün + PR-Update → Re-Gate (D11-fokussiert).

---

## Re-Gate (Re-Spin `ff3091d` → gemerged `b30d8c1`) — PASS
**D11 ehrlich instrumentiert** (Eigen-Prüfung, kein Panel nötig bei fokussiertem Single-Claim):
- Monkeypatch-**Spy** um `hass.auth.async_update_user` (`:1567-1588`) zählt echte Calls (`call_count=len(calls)`).
- `native_write_call_count`/`refused_before_call` aus der **Messung** (`:1624-1636`), Feld `native_write_measurement_source="spy:hass.auth.async_update_user"`.
- d0_preflight-Gate (`:909-913`) liest jetzt die **gemessenen** Felder, nicht Konstanten.
- Evidence: **0 native Writes** im Version-Mismatch-Pfad → D11 PASS gemessen belegt.
D15/D13/D5/D7-Verdikte erhalten, Diff nur `spike/`+`tests/`, Produkt unberührt. Gemerged `b30d8c1`.
**Offen (Cleanup-Pass):** D5-Auflagen (`auth_store_corrupted`-Rename, Seeds @754/@761) — Hardening, nicht-blockierend.
