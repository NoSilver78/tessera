"""Schema-library indirection for Tessera's own voluptuous-style schemas.

Home Assistant is migrating from **voluptuous** to **probatio**, and it does so
in two steps that do *not* fall on the same release:

* **2026.9** ships probatio and installs it *as* voluptuous
  (``install_as_voluptuous()`` in ``homeassistant/__init__.py``), so
  ``import voluptuous`` already yields probatio objects at runtime — while HA's
  own annotations still say ``voluptuous.schema_builder.Schema``.
* **2026.10** flips the annotations to ``probatio.schema.Schema``.

All four validated lines therefore disagree about what the *static* type of a
schema is, and no single import satisfies them: importing voluptuous fails
``mypy --strict`` on 2026.10 (34 arg-type errors in CI, which only passed
locally because the development environment still had a pre-probatio HA),
importing probatio fails the same way on 2026.9 (35 errors, mirrored). Measured
on 2026.8.2, 2026.9.4 and 2026.10.4, not assumed.

The runtime, in contrast, is unambiguous: ``import voluptuous`` is what HA
supports for custom integrations on every line, and it resolves to the probatio
shim wherever probatio is installed. So the import stays, and this one boundary
is deliberately untyped for the checker — the same thing the ``voluptuous``
``ignore_missing_imports`` override did implicitly before HA started annotating
these parameters. Schema *shape* is covered by the config-flow and websocket
tests, which exercise the real validators.

``tests/test_ha_schema_contract.py`` pins the runtime half of this: it asserts
against the installed Home Assistant that ``voluptuous`` resolves to probatio
exactly when probatio is there, and that Tessera ended up with that very
library, so neither half can drift unnoticed.

Why this file exists at all rather than a migration to ``probatio.*``, which
risk that buys and the three triggers that would overturn it:
``decisions/0006-schema-library-compat-over-migration.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Untyped on purpose: HA annotates these parameters as voluptuous on
    # 2026.7-2026.9 and as probatio on 2026.10+, so any concrete type here is
    # wrong on one of the validated lines.
    vol: Any
else:
    # Home Assistant first, deliberately: the shim is installed from
    # homeassistant/__init__.py, and taking the name before that would pin the real
    # voluptuous for the lifetime of the process — Tessera would then build markers
    # with one library while HA validates with the other. Today the import order in
    # this package happens to be right anyway (third-party before local), which is
    # luck, not a guarantee. Tessera only ever runs inside HA, so this costs nothing.
    import homeassistant  # noqa: F401
    import voluptuous as vol

__all__ = ["vol"]
