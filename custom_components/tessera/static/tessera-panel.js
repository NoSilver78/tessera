/**
 * Tessera matrix panel — a custom element (<tessera-matrix-panel>) for the
 * admin-only Tessera sidebar page. Home Assistant assigns the `hass` property.
 *
 * The matrix splits each role into two provenance columns:
 *   - Floor: the grant inherited from the area's floor (display-only here).
 *   - Area:  the direct Area x Role grant, editable — clicking a cell cycles
 *            none -> read -> read+control -> none via `tessera/matrix/set_grant`.
 * When both sources grant the same area, the row is flagged "doppelt" (a
 * redundant double: removing one source won't change effective access).
 *
 * Each area row expands (chevron) to list the entities Tessera resolves for it;
 * those entities inherit the area right, so they carry no per-entity columns.
 *
 * WebSocket:
 *   - `tessera/matrix/get`       load areas, roles, per-source grants, floors,
 *                                entities-by-area, monitor preview
 *   - `tessera/matrix/set_grant` persist one Area cell, return the refreshed matrix
 */
class TesseraMatrixPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = undefined;
    this._data = undefined;
    this._error = "";
    this._pending = "";
    this._loading = false;
    this._expanded = new Set();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._data && !this._loading) {
      this._load();
    }
    this._render();
  }

  async _load() {
    if (!this._hass) {
      return;
    }
    this._loading = true;
    this._error = "";
    this._render();
    try {
      this._data = await this._hass.connection.sendMessagePromise({
        type: "tessera/matrix/get",
      });
    } catch (err) {
      this._error = this._messageFromError(err);
    } finally {
      this._loading = false;
      this._render();
    }
  }

  /** Advance one Area x Role cell to its next grant state and persist it. */
  async _toggle(areaId, roleId) {
    if (!this._hass || this._pending) {
      return;
    }
    const current = this._grantFor(areaId, roleId);
    // Cycle the Area cell: none -> read -> read+control -> none.
    const next = current.control
      ? { read: false, control: false }
      : current.read
        ? { read: true, control: true }
        : { read: true, control: false };

    this._pending = `${areaId}::${roleId}`;
    this._error = "";
    this._render();
    try {
      this._data = await this._hass.connection.sendMessagePromise({
        type: "tessera/matrix/set_grant",
        area_id: areaId,
        role_id: roleId,
        read: next.read,
        control: next.control,
      });
    } catch (err) {
      this._error = this._messageFromError(err);
    } finally {
      this._pending = "";
      this._render();
    }
  }

  _toggleExpand(areaId) {
    if (this._expanded.has(areaId)) {
      this._expanded.delete(areaId);
    } else {
      this._expanded.add(areaId);
    }
    this._render();
  }

  /** Direct Area grant for a cell, defaulting to no permission. */
  _grantFor(areaId, roleId) {
    return (
      this._data?.grants?.[areaId]?.[roleId] || { read: false, control: false }
    );
  }

  /** Floor-inherited grant for a cell, defaulting to no permission. */
  _floorGrantFor(areaId, roleId) {
    return (
      this._data?.floor_grants?.[areaId]?.[roleId] || {
        read: false,
        control: false,
      }
    );
  }

  /** A cell is a "double" when both the floor and the area grant it. */
  _isDouble(areaId, roleId) {
    const area = this._grantFor(areaId, roleId);
    const floor = this._floorGrantFor(areaId, roleId);
    return (area.read || area.control) && (floor.read || floor.control);
  }

  _state(grant) {
    return grant.control ? "control" : grant.read ? "read" : "none";
  }

  _entityName(entityId) {
    const state = this._hass?.states?.[entityId];
    return state?.attributes?.friendly_name || entityId;
  }

  _messageFromError(err) {
    if (err && typeof err === "object" && "message" in err) {
      return String(err.message);
    }
    return "Tessera matrix request failed";
  }

  _render() {
    const data = this._data;
    const areas = data?.areas || [];
    const roles = data?.roles || [];
    const preview = data?.preview;

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          padding: 24px;
          color: var(--primary-text-color);
          background: var(--primary-background-color);
          box-sizing: border-box;
        }
        .card {
          background: var(--card-background-color);
          border-radius: var(--ha-card-border-radius);
          box-shadow: var(--ha-card-box-shadow);
          border: var(--ha-card-border-width, 1px) solid var(--divider-color);
          overflow: hidden;
        }
        header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
          padding: 20px 24px;
          border-bottom: 1px solid var(--divider-color);
        }
        h1 { margin: 0; font-size: 24px; font-weight: 500; }
        .actions { display: flex; gap: 12px; align-items: center; }
        button {
          border: 1px solid var(--divider-color);
          border-radius: 999px;
          background: var(--secondary-background-color);
          color: var(--primary-text-color);
          cursor: pointer;
          font: inherit;
          padding: 8px 14px;
        }
        button:hover { border-color: var(--primary-color); }
        button:disabled { cursor: progress; color: var(--disabled-text-color); }
        .error {
          margin: 16px 24px 0;
          padding: 12px 16px;
          border-radius: 8px;
          color: var(--error-color);
          background: var(--secondary-background-color);
        }
        .legend {
          display: flex;
          flex-wrap: wrap;
          gap: 16px;
          padding: 12px 24px 0;
          font-size: 12px;
          color: var(--secondary-text-color);
        }
        .legend span { display: inline-flex; align-items: center; gap: 6px; }
        .swatch { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
        .swatch.read { background: var(--warning-color); }
        .swatch.control { background: var(--success-color); }
        .swatch.dbl { outline: 2px solid var(--error-color); outline-offset: 1px; }
        .preview {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
          gap: 12px;
          padding: 20px 24px;
          border-bottom: 1px solid var(--divider-color);
        }
        .metric { background: var(--secondary-background-color); border-radius: 10px; padding: 12px; }
        .metric span {
          display: block; color: var(--secondary-text-color);
          font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em;
        }
        .metric strong { display: block; margin-top: 4px; font-size: 22px; font-weight: 500; }
        .matrix-wrap { overflow: auto; }
        table { width: 100%; border-collapse: collapse; min-width: 640px; }
        th, td {
          border-bottom: 1px solid var(--divider-color);
          padding: 10px 12px;
          text-align: center;
        }
        th {
          background: var(--secondary-background-color);
          color: var(--secondary-text-color);
          font-weight: 500;
          position: sticky; top: 0; z-index: 1;
        }
        th.sub { font-weight: 400; font-size: 12px; text-transform: none; }
        th:first-child, td:first-child {
          position: sticky; left: 0; text-align: left;
          background: var(--card-background-color); z-index: 2;
        }
        th.role-h { z-index: 1; }
        .bl { border-left: 1px solid var(--divider-color); }
        .cell {
          min-width: 84px;
          border-radius: 10px;
          font: inherit;
          padding: 6px 10px;
        }
        .cell.none { color: var(--secondary-text-color); background: var(--secondary-background-color); }
        .cell.read { color: var(--primary-text-color); background: var(--warning-color); }
        .cell.control { color: var(--text-primary-color); background: var(--success-color); }
        .cell.floor { display: inline-block; border: none; cursor: default; opacity: 0.92; }
        .cell.dbl { outline: 2px solid var(--error-color); outline-offset: 1px; }
        .chev {
          border: none; background: none; padding: 0 6px 0 0;
          color: var(--secondary-text-color); cursor: pointer; font-size: 13px;
        }
        .chev:hover { color: var(--primary-color); border: none; }
        .doppelt {
          margin-left: 8px; font-size: 11px; padding: 1px 8px; border-radius: 6px;
          color: var(--primary-text-color); background: var(--warning-color);
        }
        tr.entrow td {
          background: var(--secondary-background-color);
          text-align: left; padding: 8px 12px 10px 34px;
        }
        .ehint {
          font-size: 11px; color: var(--secondary-text-color);
          text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 8px;
        }
        .eboxes { display: flex; flex-wrap: wrap; gap: 6px; }
        .ebox {
          background: var(--card-background-color);
          border: 1px solid var(--divider-color);
          border-radius: 6px; padding: 3px 8px;
          font-family: var(--code-font-family, monospace); font-size: 11px;
          color: var(--secondary-text-color);
        }
        .empty { padding: 32px 24px; color: var(--secondary-text-color); }
      </style>
      <div class="card">
        <header>
          <h1>Tessera Matrix</h1>
          <div class="actions">
            ${this._loading ? "<span>Loading...</span>" : ""}
            <button type="button" id="refresh" ${this._disabledAttr(this._loading || this._pending)}>
              Refresh
            </button>
          </div>
        </header>
        ${this._error ? `<div class="error">${this._escape(this._error)}</div>` : ""}
        ${roles.length ? this._legendTemplate() : ""}
        ${this._previewTemplate(preview)}
        ${this._matrixTemplate(areas, roles)}
      </div>
    `;

    this.shadowRoot.getElementById("refresh")?.addEventListener("click", () => {
      this._load();
    });
    this.shadowRoot.querySelectorAll("[data-area][data-role]").forEach((button) => {
      button.addEventListener("click", () => {
        if (button.dataset.area && button.dataset.role) {
          this._toggle(button.dataset.area, button.dataset.role);
        }
      });
    });
    this.shadowRoot.querySelectorAll("[data-expand]").forEach((button) => {
      button.addEventListener("click", () => {
        if (button.dataset.expand) {
          this._toggleExpand(button.dataset.expand);
        }
      });
    });
  }

  _legendTemplate() {
    return `
      <section class="legend" aria-label="Legend">
        <span><span class="swatch read"></span>read</span>
        <span><span class="swatch control"></span>control (implies read)</span>
        <span><span class="swatch dbl"></span>doppelt (floor + area)</span>
        <span>Floor = display · Area = click to edit</span>
      </section>
    `;
  }

  _previewTemplate(preview) {
    if (!preview) {
      return '<div class="empty">No preview available yet.</div>';
    }
    return `
      <section class="preview" aria-label="Monitor preview">
        ${this._metric("Roles", preview.roles_total)}
        ${this._metric("Entities", preview.entities_total)}
        ${this._metric("Read Grants", preview.read_total)}
        ${this._metric("Control Grants", preview.control_total)}
      </section>
    `;
  }

  _metric(label, value) {
    return `
      <div class="metric">
        <span>${this._escape(label)}</span>
        <strong>${Number(value || 0)}</strong>
      </div>
    `;
  }

  _matrixTemplate(areas, roles) {
    if (!roles.length) {
      return '<div class="empty">Add Tessera roles in the integration options first.</div>';
    }
    if (!areas.length) {
      return '<div class="empty">No Home Assistant areas found.</div>';
    }
    const roleHead = roles
      .map(
        (role) =>
          `<th class="role-h bl" colspan="2" scope="colgroup">${this._escape(role.name)}</th>`,
      )
      .join("");
    const subHead = roles
      .map(() => '<th class="sub bl" scope="col">Floor</th><th class="sub" scope="col">Area</th>')
      .join("");
    return `
      <div class="matrix-wrap">
        <table>
          <thead>
            <tr>
              <th rowspan="2" scope="col">Bereich</th>
              ${roleHead}
            </tr>
            <tr>${subHead}</tr>
          </thead>
          <tbody>
            ${areas.map((area) => this._areaRow(area, roles)).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  _areaRow(area, roles) {
    const floor = this._data?.area_floor?.[area.id];
    const label = floor ? `${area.name} · ${floor.name}` : area.name;
    const expanded = this._expanded.has(area.id);
    const rowDouble = roles.some((role) => this._isDouble(area.id, role.id));
    const cells = roles
      .map((role) => this._floorCell(area, role) + this._areaCell(area, role))
      .join("");
    const nameCell = `
      <td>
        <button type="button" class="chev" data-expand="${this._escape(area.id)}"
          aria-label="Toggle entities" aria-expanded="${expanded ? "true" : "false"}">
          ${expanded ? "▾" : "▸"}
        </button>${this._escape(label)}${rowDouble ? '<span class="doppelt">doppelt</span>' : ""}
      </td>`;
    const rows = [`<tr>${nameCell}${cells}</tr>`];
    if (expanded) {
      rows.push(this._entityRow(area, roles.length));
    }
    return rows.join("");
  }

  _floorCell(area, role) {
    const state = this._state(this._floorGrantFor(area.id, role.id));
    const dbl = this._isDouble(area.id, role.id) ? " dbl" : "";
    return `<td class="bl"><span class="cell floor ${state}${dbl}">${state}</span></td>`;
  }

  _areaCell(area, role) {
    const state = this._state(this._grantFor(area.id, role.id));
    const dbl = this._isDouble(area.id, role.id) ? " dbl" : "";
    const pending = this._pending === `${area.id}::${role.id}`;
    return `
      <td>
        <button
          type="button"
          class="cell ${state}${dbl}"
          data-area="${this._escape(area.id)}"
          data-role="${this._escape(role.id)}"
          ${this._disabledAttr(pending)}
          title="Toggle area grant ${this._escape(area.name)} / ${this._escape(role.name)}"
        >
          ${pending ? "Saving..." : state}
        </button>
      </td>
    `;
  }

  _entityRow(area, roleCount) {
    const ids = this._data?.entities_by_area?.[area.id] || [];
    const colspan = 1 + roleCount * 2;
    const boxes = ids.length
      ? ids
          .map((id) => `<span class="ebox">${this._escape(this._entityName(id))}</span>`)
          .join("")
      : '<span class="ebox">— keine Entities —</span>';
    return `
      <tr class="entrow">
        <td colspan="${colspan}">
          <div class="ehint">${ids.length} Entities · erben das Area-Recht</div>
          <div class="eboxes">${boxes}</div>
        </td>
      </tr>
    `;
  }

  _escape(value) {
    return String(value).replace(/[&<>"']/g, (char) => {
      const entities = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      };
      return entities[char];
    });
  }

  _disabledAttr(disabled) {
    return disabled ? "disabled" : "";
  }
}

customElements.define("tessera-matrix-panel", TesseraMatrixPanel);
