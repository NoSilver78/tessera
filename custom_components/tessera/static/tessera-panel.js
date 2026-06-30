/**
 * Tessera matrix panel — a custom element (<tessera-matrix-panel>) for the
 * admin-only Tessera sidebar page. Home Assistant assigns the `hass` property;
 * the panel renders the Area x Role grant matrix and persists edits over two
 * WebSocket commands:
 *   - `tessera/matrix/get`       load areas, roles, grants, monitor preview
 *   - `tessera/matrix/set_grant` persist one cell, return the refreshed matrix
 * Each grant cell cycles none -> read -> read+control -> none on click.
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
    // Cycle the cell: none -> read -> read+control -> none.
    const next =
      current.control
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

  /** Return the current grant for a cell, defaulting to no permission. */
  _grantFor(areaId, roleId) {
    return (
      this._data?.grants?.[areaId]?.[roleId] || { read: false, control: false }
    );
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
        h1 {
          margin: 0;
          font-size: 24px;
          font-weight: 500;
        }
        .actions {
          display: flex;
          gap: 12px;
          align-items: center;
        }
        button {
          border: 1px solid var(--divider-color);
          border-radius: 999px;
          background: var(--secondary-background-color);
          color: var(--primary-text-color);
          cursor: pointer;
          font: inherit;
          padding: 8px 14px;
        }
        button:hover {
          border-color: var(--primary-color);
        }
        button:disabled {
          cursor: progress;
          color: var(--disabled-text-color);
        }
        .error {
          margin: 16px 24px 0;
          padding: 12px 16px;
          border-radius: 8px;
          color: var(--error-color);
          background: var(--secondary-background-color);
        }
        .preview {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
          gap: 12px;
          padding: 20px 24px;
          border-bottom: 1px solid var(--divider-color);
        }
        .metric {
          background: var(--secondary-background-color);
          border-radius: 10px;
          padding: 12px;
        }
        .metric span {
          display: block;
          color: var(--secondary-text-color);
          font-size: 12px;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }
        .metric strong {
          display: block;
          margin-top: 4px;
          font-size: 22px;
          font-weight: 500;
        }
        .matrix-wrap {
          overflow: auto;
        }
        table {
          width: 100%;
          border-collapse: collapse;
          min-width: 640px;
        }
        th,
        td {
          border-bottom: 1px solid var(--divider-color);
          padding: 12px;
          text-align: center;
        }
        th {
          background: var(--secondary-background-color);
          color: var(--secondary-text-color);
          font-weight: 500;
          position: sticky;
          top: 0;
          z-index: 1;
        }
        th:first-child,
        td:first-child {
          position: sticky;
          left: 0;
          text-align: left;
          background: var(--card-background-color);
          z-index: 2;
        }
        .cell {
          min-width: 96px;
          border-radius: 10px;
        }
        .cell.none {
          color: var(--secondary-text-color);
          background: var(--secondary-background-color);
        }
        .cell.read {
          color: var(--primary-text-color);
          background: var(--warning-color);
        }
        .cell.control {
          color: var(--text-primary-color);
          background: var(--success-color);
        }
        .empty {
          padding: 32px 24px;
          color: var(--secondary-text-color);
        }
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
    return `
      <div class="matrix-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Area</th>
              ${roles.map((role) => `<th scope="col">${this._escape(role.name)}</th>`).join("")}
            </tr>
          </thead>
          <tbody>
            ${areas.map((area) => this._areaRow(area, roles)).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  _areaRow(area, roles) {
    return `
      <tr>
        <td>${this._escape(area.name)}</td>
        ${roles.map((role) => this._grantCell(area, role)).join("")}
      </tr>
    `;
  }

  _grantCell(area, role) {
    const grant = this._grantFor(area.id, role.id);
    // The cell's CSS class and its visible label are the same token.
    const state = grant.control ? "control" : grant.read ? "read" : "none";
    const pending = this._pending === `${area.id}::${role.id}`;
    return `
      <td>
        <button
          type="button"
          class="cell ${state}"
          data-area="${this._escape(area.id)}"
          data-role="${this._escape(role.id)}"
          ${this._disabledAttr(pending)}
          title="Toggle ${this._escape(area.name)} / ${this._escape(role.name)}"
        >
          ${pending ? "Saving..." : state}
        </button>
      </td>
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
