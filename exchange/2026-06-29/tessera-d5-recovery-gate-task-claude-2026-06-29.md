# Codex-Aufgabe — D5 hartes Recovery-Gate (B2)
Von Claude · 2026-06-29 · Spec: `docs/spec-phase0.md` (B2-Sinn: Z.82 No-Go „Rescue hängt am gesunden Code", Z.50/60 RecoveryController **außerhalb** Tessera-Start, Z.110 „D5 Rescue bei kaputtem Store/Setup-Exception") · Round-2 v2 **B2** · ADR 0004 (Produkt bleibt enforce-frei) · **Branch `welle-b/d5-recovery-gate` (von `main`) → PR**

## Ziel
D5 von **ehrlich-PARTIAL → belastbar** bringen. Heute ist D5 nur eine **Restore-Primitive gegen einen Sidecar-Glitch**, kein Rescue-Beweis: `_prepare_boot_rescue` (`__init__.py:1005`) korrumpiert nur den **Tessera-Sidecar** `/config/.storage/tessera.config` (`:35`), und `_run_boot_rescue_if_requested` (`:633`) setzt die drei Gate-Flags **hartcodiert** auf `False/False/None` (`:694–700`, `:1046–1052`). Das D5-Verdict (`d0_preflight_spike.py:754`) ist `PASS` nur bei `auth_store_corrupted ∧ boot_rescue_corruption_tested ∧ no_admin_lockout` → bleibt korrekt PARTIAL.

**Leitprinzip (wie Welle B/C): ehrlich messen, kein falsches PASS.** Die drei Flags dürfen **nie wieder Konstanten** sein — jede Gate-Zelle auf gemessene Booleans rückführbar (kein Streu-Grün). Alles nur gegen `ha-tessera-dev` (Isolations-Gate vor **jedem** Auth-Write), **kein** `/Volumes/config`, **kein** Live-CM5. Evidence tokenfrei, Failure-Artefakte redaktiert.

## Szenarien

### S1 — No-Admin-Lockout über Tesseras eigenen Schreibpfad (**PASS-Gate**)
Das ist das Risiko, das Tessera *selbst* verursachen kann (REPLACE-`group_ids` über `UserBindingAdapter`, Spec Z.58 „Replace-Lockout, Owner-Guard") und mit der eigenen Restore-Primitive beheben muss.
- **Pre-Restart:** managed Admin-artigen User (`tessera-…`) + einen **Owner/echten Admin als Kontrolle** anlegen. Über `async_update_user(group_ids=…)` (REPLACE) den managed Admin **demoten** (Soll-Gruppen entzogen). Soll-Gruppen-Snapshot + Trigger schreiben. Flags **real** messen, nicht setzen.
- **Boot:** `_run_boot_rescue_if_requested()` läuft in `async_setup` (`:1751`) **vor/unabhängig** vom normalen Tessera-Start, restored die Soll-Gruppen, **rührt Owner/`system_generated`/unmanaged nie an** (Guard `_validate_managed_user` `:718` — assertieren, nicht annehmen).
- **`no_admin_lockout` (gemessen):** echter Token-Round-Trip im D8-Stil (`_make_access_token` `:158` bzw. `_make_llat_access_token` `:587`, danach `async_remove_refresh_token` `:1708`) — ein Owner/Admin kann nach dem Rescue **authentifizieren UND operieren** (control auf erlaubter Entity). Nur dann `True`.
- **Re-Read (Spec B2 „Re-Read beweist System-Zustand"):** managed User trägt nach Rescue **exakt** die Soll-Gruppen (`set == set`), gegen frischen `_auth_snapshot`.

### S1b — Rescue ohne gesunden Tessera-Start (**Teil des PASS-Gates**, load-bearing)
Spec Z.50/60/82: der RecoveryController darf **nicht am gesunden Store/Code hängen**.
- Nachweis, dass der Boot-Rescue **trotz** kaputtem Tessera-Sidecar **und** trotz einer absichtlichen **Setup-Exception** im normalen Tessera-Pfad läuft (Sidecar-Korruption existiert schon; Setup-Exception-Variante ergänzen: normalen Start kontrolliert werfen lassen, Rescue muss vorher/separat greifen). → neues Boolean `rescue_independent_of_healthy_tessera`.

### S2 — echte `/config/.storage/auth`-Korruption (**PARTIAL / observational**, kein PASS-Hebel)
- Auf dem Wegwerf-Container nach **Backup-Kopie** den HA-Auth-Store (`AUTH_STORE_PATH` `:36`) gezielt beschädigen (truncate/garble), Neustart, **beobachten**: bootet HA? greift ein Owner-Recovery? Ehrlich als PARTIAL dokumentieren — Boot-/Store-Recovery ist überwiegend **HA-eigenes** Verhalten (`hass --script auth`-Territorium), nicht Tesseras Gate. **Kein** PASS daraus ableiten. Owner-Schaden ⇒ ausdrücklich außerhalb Tessera-Scope dokumentieren (Tessera fasst Owner nie an).

## Betroffene Dateien
`spike/tools/tessera_spike/harness/custom_components/tessera_spike/__init__.py` — neue Probes `_probe_d5_lockout_rescue` (S1/S1b) + `_probe_d5_authstore_corruption` (S2); Flags `auth_store_corrupted`/`boot_rescue_corruption_tested`/`no_admin_lockout` **aus Messung** statt Konstante (`:694–700`, `:1046–1052`); in `_phase_pre_restart`/`_phase_post_restart` verdrahten · `spike/tools/tessera_spike/d0_preflight_spike.py` — D5-Verdict (`:754`) bekommt echte Eingaben, plus AND-Bedingungen `rescue_independent_of_healthy_tessera` + `reread_state_matches_intended` · `spike/evidence/*` + `spike/reports/*` regenerieren. **NICHT** `custom_components/tessera` (Produkt bleibt enforce-frei, ADR 0004). D4 **separat** lassen (Union/Restore-PASS, nicht mit D5 vermischen — Round-2 v2 §3 B2).

## Regeln / was NICHT ändern
- Owner-/`system_generated`-/unmanaged-Guard bleibt hart; Rescue-Namespace-Guard (`tessera:` only, `_validate_managed_group_id`) bleibt. Die Rescue darf **selbst keinen** Lockout/keine Eskalation erzeugen — explizit testen (Versuch, Owner/`system-users`-Gruppen zu schreiben, muss abgelehnt werden).
- Drei-Flag-AND-Struktur des D5-Verdicts beibehalten — nur mit echten Werten füttern + zwei AND-Bedingungen ergänzen. Keine Aufweichung der PASS-Bedingung.
- Bestehende D1–D4/D6–D9/A2/A3/B3-Pfade nicht regressieren.

## Sicherheits-Guards (dev-only, hart)
- Nur `ha-tessera-dev` (Docker :8124, eigenes Volume); `recreate_container` davor; Isolations-Gate (`FAIL_TARGET_ISOLATION`) vor jedem Auth-Write.
- Vor **jeder** Auth-Store-Manipulation Backup-Kopie von `/config/.storage/auth`; am Ende Restore → reproduzier-/abwischbar. S2 darf höchstens den Container unbootbar machen → per `recreate` erholbar; nie gegen ein Volume mit echten Daten.
- Keine Token-/Passwort-/Auth-Code-/LLAT-Werte in Logs/Evidence/Chat; Failure-Bodies redaktieren. Basis-Evidence (exit_code, gate_results[], Abbruchgrund, Secret-Redaction-Status, kein `Detected blocking call`) wie in allen Wellen.

## DoD
- **D5 = PASS** ⇔ `auth_store_corrupted` (S1-Demotion real injiziert) ∧ `boot_rescue_corruption_tested` ∧ `no_admin_lockout` (echter Admin/Owner Auth+Operate-Round-Trip) ∧ `rescue_independent_of_healthy_tessera` (S1b) ∧ `reread_state_matches_intended` ∧ Owner/system nachweislich nie angefasst. Sonst **PARTIAL** mit benanntem Befund.
- S2 als **dokumentierter PARTIAL/Beobachtungsfall** (kein PASS).
- Jede Gate-Zelle auf gemessene Booleans rückführbar · `d5_truthfulness`-Text an den realen Befund angepasst · Doku-Drift angleichen (Report-„Nächste Pflicht" sagt *Tessera*-Store, `partial_reason` sagt *auth*-Store — beim D5-Landing vereinheitlichen) · CI grün.
- **Übergabe PR-basiert** (AGENTS.md §Übergabe): commit auf `welle-b/d5-recovery-gate` → push → `gh pr create`. **Abschlussbericht** im PR-Body: geänderte Dateien · je Szenario Verdikt + `file:line` + Zahlen · Tests (Happy/Fehler/Grenze/Regression) + Ergebnis · Risiken/Annahmen. → **Re-Gate durch Claude** (Review + CI grün) vor Merge nach `main`.
