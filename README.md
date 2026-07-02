# Tessera

> Role-based access control (RBAC) for Home Assistant — *Read / Control* × **Role** × **Area**.

[Deutsch](README.de.md) · **English**

Tessera is a standalone permission system for Home Assistant. It closes a gap that has been open for
years: HA only has three fixed system groups, no UI for fine-grained rights, and a hard owner bypass.
Tessera compiles declarative policies (**role × area × action**) into **native** HA
`PolicyPermissions` and writes them — **in `enforce` mode** — into the Home Assistant auth store.
**No monkeypatch, no core fork.**

> ⚠️ **Security-critical integration.** Tessera changes who can see and do what in your Home Assistant
> instance. In `enforce` mode Tessera **actively writes** to the HA auth store. Read the
> **[security model](#security-model-honest)** below before you enable `enforce` — and note the
> **[project status](#project-status)**: enforcement is built, wired, and **proven in a live instance**
> (dev E2E + running operation); broad testing across many setups is still pending.
> **Start with `monitor` anyway**, review the computed verdicts, and only then move deliberately to `enforce`.

## What Tessera does

- **Declarative policies** — roles × areas × actions. Per area × role you grant, in the panel,
  **Read** (view) and/or **Control** (operate); a third level **change** corresponds to HA's global
  `is_admin` (see [security model](#security-model-honest)).
- **Compiler** — translates policies into native HA `PolicyPermissions` (expands areas, floors and
  labels to entity IDs, including the area-less direct entities that HA's `area_ids` alone misses).
- **Linter** — checks policies for conflicts and gaps before applying.
- **Dual-mode membership** — local roles (`by_user`, the baseline, no external dependency) **or**
  additively a mapping from an external IdP (`by_group`, e.g. Authentik/OIDC — optional).
- **Admin panel** "Tessera" in the HA sidebar (administrators only), with a `Bereiche ↔ Labels`
  toggle between two boards: an **Area-Board** (per role the provenance columns **Floor | Area**,
  clickable to set grants, a double-grant marker, expandable to entity level) and a **Labels board**
  — labels as rows with an editable cell per role, expandable to the entities a label resolves to.
- **Three operating modes** with a non-intrusive default — see below.

## Project status

**Published (v0.9.0) · `enforce` dev-proven and active in a live instance · broad multi-setup testing wanted.**

| Building block | Status |
|---|---|
| **Core** (store · compiler · linter · schema · config flow) | ✅ working |
| **Monitor** (read-only preview + matrix panel) | ✅ working |
| **Enforce machinery** (plan · bindings · write+guards · restore/recovery) | ✅ built, adversarially gated |
| **Enforce wiring** (`mode=enforce` goes live) | ✅ wired — `mode=enforce` writes native auth; errors → fail-safe to `monitor` |
| **Area-Board panel** (Floor\|Area provenance · double marker · entity expand · Area+Floor editable) | ✅ working |
| **End-to-end against a dev instance + live operation** | ✅ dev E2E run + live `enforce` verified; **broad multi-setup soak wanted** |
| **HACS enablement** (`hacs.json` · HACS+hassfest CI · brand icon) | ✅ done |
| **HACS** (public · tagged releases) | ✅ v0.2.0–v0.9.0 · default-store submission in review |

The whole story — vision, phases, what comes next, and **where help is most useful** — is in the
**[ROADMAP](ROADMAP.md)** and in **[CONTRIBUTING](CONTRIBUTING.md)**.

## Full guide

Complete **setup & usage** — installation, operating modes, roles/grants/memberships, the Area-Board
panel, `enforce` with preflight, a prominent **"things to watch out for"** section (version guard /
HA updates!), troubleshooting and FAQ — with screenshots:

**📖 [English](docs/GUIDE.md) · [Deutsch](docs/GUIDE.de.md)**

## Installation (HACS — custom repository)

> Tessera is installable as a **HACS custom repository** — there are tagged releases (currently **v0.9.0**).
> Inclusion in the **HACS default store** has been submitted (in review); until then, use "Custom repositories":

1. Open HACS → three-dot menu top right → **Custom repositories**.
2. URL: `https://github.com/NoSilver78/tessera` · category: **Integration** → **ADD**.
3. Select Tessera in the HACS list and download it.
4. **Restart Home Assistant.**
5. **Settings → Devices & Services → Add Integration → Tessera**.

**Tested HA version:** Home Assistant **2026.7.0** (see *[version guard](#version-guard-private-ha-apis)*).
On any other HA version the runtime guard blocks the `enforce` write path and keeps Tessera in the
read-only `monitor` state.

## Security model (honest)

Tessera has three operating modes. **The default is non-intrusive.**

| Mode | Effect |
|---|---|
| `off` | Tessera does nothing. |
| `monitor` | Tessera **computes** permissions and shows deviations (panel + logs), but **does NOT write** to the auth store. Safe for onboarding. |
| `enforce` | Tessera **writes** the compiled permissions into the HA auth store (native group `PolicyPermissions` + rebind of `group_ids`) and really intervenes in access. |

> **Current state:** `enforce` is wired and **writes** native auth state when `mode=enforce` is set —
> after a fail-closed gate sequence (HA version → compile → [D9 gate](docs/GUIDE.md#the-d9-gate) →
> linter → lockout precheck → immutable snapshot/journal → apply). **Every error in this chain safely
> falls back to `monitor`** (no half-applied state); an aborted run is restored from the pre-install
> snapshot at startup. What is still **pending** is broad practical proof (soak + dogfood across many
> setups, see [ROADMAP](ROADMAP.md)). So start with `monitor`, review the computed verdicts, and only
> then move deliberately to `enforce`.

### Allow-only model
Tessera grants permissions **additively (allow-only)**: a policy *grants* access; access not granted
stays denied. Tessera sets **no** deny rules and overrides **no** HA-native admin rights. Owner and
system-generated accounts are never modified.

### Documented leak paths (known limits)
HA permissions do **not** act identically on every surface. Tessera **cannot** close these HA-internal
paths — documented honestly here:

- **`render_template` / template sensors** — templates can read states of entities a user has no UI
  access to; values can leak indirectly.
- **Logbook / History** — history views may reveal events of restricted entities, depending on HA
  version and configuration.
- **Assist / Conversation** — voice/conversation agents can query states or trigger actions that
  partly bypass the permission layer.

> Tessera is **not** full data isolation. If these paths matter to you, add HA-side measures (exclude
> entities from Assist, limit template exposure).

### Version guard (private HA APIs)
Tessera writes partly through **private/undocumented HA auth APIs** for which Home Assistant gives
**no** stability guarantee — they can break between releases. Protection:

- **Active protection (runtime guard):** the auth write path checks in code for the **exact tested**
  HA version (`SUPPORTED_HA_AUTH_VERSION`, currently **2026.7.0** — exact-equality match). On any other
  version the write path is **fail-closed blocked** and `enforce` falls back to the read-only `monitor`
  state — **no** native write. **Every HA core update therefore safely pauses `enforce`** until a
  Tessera version verifies the new HA version (details:
  [guide → things to watch out for](docs/GUIDE.md#things-to-watch-out-for)).
- An additional `hacs.json` pin of the minimum HA version is **deliberately not** set (HACS validation
  rejected the value as a future minimum); the real safeguard is and remains the runtime guard above.
- If an internal API breaks, the tested version is raised and a new version is published.

More on this: **[docs/MAINTENANCE.md](docs/MAINTENANCE.md)**.

## Privacy

Tessera processes account/role/area mappings (HA users, roles, area assignments — personal data under
the GDPR) **entirely locally**. **No cloud, no telemetry.** Persistence is local only (HA auth store +
Tessera's own store).

## Contributing

Tessera is deliberately open to contributors — especially **tests on diverse multi-user setups**,
**HA-version compatibility**, and **feedback on the RBAC model**. Where exactly help is needed is in
**[CONTRIBUTING.md](CONTRIBUTING.md)** (section *Help wanted*).

## Reporting security issues

Please **not** as a public issue. Use GitHub **Private Vulnerability Reporting** (the repo's *Security*
tab) — details in **[SECURITY.md](SECURITY.md)**.

## Development (transparent)

Tessera is built in an unusual, deliberately documented model: **Claude** (architecture, gate, audit),
**Codex** (implementation), and Michael (owner/orchestration). The point is **safety through
multiple-eyes review**: every auth write path passes, before merge, an **adversarial multi-agent gate**
(several independent, skeptical reviewers) plus **mutation proofs** (tests are deliberately broken to
prove they catch the regression). The process is openly viewable: [`CONTRACT.md`](CONTRACT.md),
[`CLAUDE_WORKFLOW.md`](CLAUDE_WORKFLOW.md), the handoffs in [`exchange/`](exchange/), and the gate
reviews in [`reports/`](reports/).

## License

[MIT](LICENSE) © 2026 Michael Scholz
