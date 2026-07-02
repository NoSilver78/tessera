/**
 * Tessera matrix panel — a custom element (<tessera-matrix-panel>) for the
 * admin-only Tessera sidebar page. Home Assistant assigns the `hass` property.
 *
 * The matrix is grouped by floor, and each role keeps a two-column provenance
 * split (Floor | Area):
 *   - Floor header row: one per floor. Its Floor cell is the editable floor x
 *     role grant (click cycles none -> read -> read+control -> none via
 *     `tessera/matrix/set_floor_grant`). The floor grant is edited here, once.
 *   - Area rows (indented under the floor): the Floor cell shows the inherited
 *     floor grant (display-only), the Area cell is the editable direct Area x
 *     Role grant (`tessera/matrix/set_grant`). When both the floor and the area
 *     grant a cell, the row is flagged "doppelt" (a redundant double).
 *   - Areas without a floor group under a non-editable "Ohne Etage" header.
 *
 * Each area row expands (chevron) to list the entities Tessera resolves for it;
 * those entities inherit the area right, so they carry no per-entity columns.
 *
 * A header toggle switches between two boards: the Area-Board (above) and a
 * Labels board — labels as rows (colour dot + entity count), one editable cell
 * per role that cycles none -> read -> read+control via
 * `tessera/matrix/set_label_grant`. Each label row expands to the entities it
 * resolves (entity + device + area labels), which inherit the label right.
 *
 * WebSocket:
 *   - `tessera/matrix/get`             load areas, roles, per-source grants,
 *                                      floors, labels, entities, preview
 *   - `tessera/matrix/set_grant`       persist one Area cell, return refreshed matrix
 *   - `tessera/matrix/set_floor_grant` persist one Floor cell, return refreshed matrix
 *   - `tessera/matrix/set_label_grant` persist one Label cell, return refreshed matrix
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
    this._board = "areas";
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
    this._pending = `${areaId}::${roleId}`;
    this._error = "";
    this._render();
    try {
      this._data = await this._hass.connection.sendMessagePromise({
        type: "tessera/matrix/set_grant",
        area_id: areaId,
        role_id: roleId,
        ...this._nextGrant(this._grantFor(areaId, roleId)),
      });
    } catch (err) {
      this._error = this._messageFromError(err);
    } finally {
      this._pending = "";
      this._render();
    }
  }

  /** Advance one Floor x Role cell to its next grant state and persist it. */
  async _toggleFloor(floorId, roleId) {
    if (!this._hass || this._pending) {
      return;
    }
    this._pending = `floor::${floorId}::${roleId}`;
    this._error = "";
    this._render();
    try {
      this._data = await this._hass.connection.sendMessagePromise({
        type: "tessera/matrix/set_floor_grant",
        floor_id: floorId,
        role_id: roleId,
        ...this._nextGrant(this._floorGrantById(floorId, roleId)),
      });
    } catch (err) {
      this._error = this._messageFromError(err);
    } finally {
      this._pending = "";
      this._render();
    }
  }

  /** Cycle a grant: none -> read -> read+control -> none. */
  _nextGrant(current) {
    if (current.control) {
      return { read: false, control: false };
    }
    if (current.read) {
      return { read: true, control: true };
    }
    return { read: true, control: false };
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

  /** Floor-inherited grant for an area cell, defaulting to no permission. */
  _floorGrantFor(areaId, roleId) {
    return (
      this._data?.floor_grants?.[areaId]?.[roleId] || {
        read: false,
        control: false,
      }
    );
  }

  /** The floor grant addressed by floor id (any area on the floor mirrors it). */
  _floorGrantById(floorId, roleId) {
    const areaFloor = this._data?.area_floor || {};
    for (const [areaId, floor] of Object.entries(areaFloor)) {
      if (floor && floor.id === floorId) {
        return this._floorGrantFor(areaId, roleId);
      }
    }
    return { read: false, control: false };
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

  /**
   * Group areas by floor for the matrix body.
   * Returns ordered floors (by level asc, then name) each with their areas, plus
   * the floorless areas. Areas keep the WS order (already sorted by name).
   */
  _floorGroups() {
    const areas = this._data?.areas || [];
    const areaFloor = this._data?.area_floor || {};
    const byFloor = new Map();
    const floorless = [];
    for (const area of areas) {
      const floor = areaFloor[area.id];
      if (!floor) {
        floorless.push(area);
        continue;
      }
      let group = byFloor.get(floor.id);
      if (!group) {
        group = {
          id: floor.id,
          name: floor.name,
          level: floor.level == null ? null : floor.level,
          order: floor.order == null ? 0 : floor.order,
          areas: [],
        };
        byFloor.set(floor.id, group);
      }
      group.areas.push(area);
    }
    // Order by explicit floor level when set; otherwise fall back to the HA
    // floor-registry order (physical-ish), and only then to the name.
    const floors = [...byFloor.values()].sort((a, b) => {
      const la = a.level == null ? Number.POSITIVE_INFINITY : a.level;
      const lb = b.level == null ? Number.POSITIVE_INFINITY : b.level;
      if (la !== lb) {
        return la - lb;
      }
      if (a.order !== b.order) {
        return a.order - b.order;
      }
      return a.name.localeCompare(b.name);
    });
    return { floors, floorless };
  }

  _messageFromError(err) {
    if (err && typeof err === "object" && "message" in err) {
      return String(err.message);
    }
    return "Tessera matrix request failed";
  }

  _render() {
    const data = this._data;
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
        th:first-child:not(.sub), td:first-child {
          position: sticky; left: 0; text-align: left;
          background: var(--card-background-color); z-index: 2;
        }
        th.role-h { z-index: 1; }
        .bl { border-left: 1px solid var(--divider-color); }
        tr.floorrow td {
          background: var(--secondary-background-color);
          border-bottom: 1px solid var(--divider-color);
        }
        tr.floorrow td:first-child {
          background: var(--secondary-background-color);
          font-weight: 500;
        }
        .fname { display: inline-flex; align-items: center; gap: 8px; }
        .fmark {
          width: 4px; height: 16px; border-radius: 2px;
          background: var(--primary-color); display: inline-block;
        }
        .fmeta { color: var(--secondary-text-color); font-weight: 400; font-size: 12px; }
        .cell {
          display: inline-flex; align-items: center; justify-content: center;
          box-sizing: border-box;
          min-width: 88px; min-height: 34px;
          border: 1px solid transparent;
          border-radius: 10px;
          padding: 4px 10px;
          font: inherit;
        }
        .cell.none { color: var(--secondary-text-color); background: var(--secondary-background-color); border-color: var(--divider-color); }
        .cell.read { color: var(--primary-text-color); background: var(--warning-color); }
        .cell.control { color: var(--text-primary-color); background: var(--success-color); }
        .cell.finherit { background: transparent; border-style: dashed; border-color: var(--divider-color); cursor: default; }
        .cell.finherit.read { color: var(--warning-color); background: transparent; }
        .cell.finherit.control { color: var(--success-color); background: transparent; }
        .cell.finherit.none { color: var(--secondary-text-color); background: transparent; }
        .cell.dbl { outline: 2px solid var(--error-color); outline-offset: 1px; }
        td.aname { padding-left: 34px; }
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
          text-align: left; padding: 8px 12px 10px 44px;
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
        .segbar { display: inline-flex; border: 1px solid var(--divider-color); border-radius: 999px; overflow: hidden; }
        .segbar .seg { border: none; border-radius: 0; padding: 8px 16px; background: transparent; }
        .segbar .seg + .seg { border-left: 1px solid var(--divider-color); }
        .segbar .seg.active { background: var(--primary-color); color: var(--text-primary-color); }
        .segbar .seg:hover { border-color: transparent; }
        .ldot {
          width: 10px; height: 10px; border-radius: 50%; display: inline-block;
          margin: 0 6px 0 2px; vertical-align: middle; border: 1px solid var(--divider-color);
        }
        td.lname { text-align: left; padding-left: 12px; }
        td.lname ha-icon { margin-right: 6px; vertical-align: middle; --mdc-icon-size: 18px; }
      </style>
      <div class="card">
        <header>
          <h1>Tessera Matrix</h1>
          <div class="actions">
            <div class="segbar" role="tablist" aria-label="Board">
              <button type="button" id="board-areas" class="seg ${this._board === "areas" ? "active" : ""}"
                role="tab" aria-selected="${this._board === "areas" ? "true" : "false"}">Bereiche</button>
              <button type="button" id="board-labels" class="seg ${this._board === "labels" ? "active" : ""}"
                role="tab" aria-selected="${this._board === "labels" ? "true" : "false"}">Labels</button>
            </div>
            ${this._loading ? "<span>Loading...</span>" : ""}
            <button type="button" id="refresh" ${this._disabledAttr(this._loading || this._pending)}>
              Refresh
            </button>
          </div>
        </header>
        ${this._error ? `<div class="error">${this._escape(this._error)}</div>` : ""}
        ${roles.length ? this._legendTemplate() : ""}
        ${this._previewTemplate(preview)}
        ${this._board === "labels" ? this._labelBoard(roles) : this._matrixTemplate(roles)}
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
    this.shadowRoot.querySelectorAll("[data-floor][data-role]").forEach((button) => {
      button.addEventListener("click", () => {
        if (button.dataset.floor && button.dataset.role) {
          this._toggleFloor(button.dataset.floor, button.dataset.role);
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
    this.shadowRoot.getElementById("board-areas")?.addEventListener("click", () => {
      this._setBoard("areas");
    });
    this.shadowRoot.getElementById("board-labels")?.addEventListener("click", () => {
      this._setBoard("labels");
    });
    this.shadowRoot.querySelectorAll("[data-label][data-role]").forEach((button) => {
      button.addEventListener("click", () => {
        if (button.dataset.label && button.dataset.role) {
          this._toggleLabel(button.dataset.label, button.dataset.role);
        }
      });
    });
  }

  _legendTemplate() {
    const labels = this._board === "labels";
    const dbl = labels
      ? ""
      : '<span><span class="swatch dbl"></span>doppelt (Etage + Bereich)</span>';
    const prov = labels
      ? "Label × Rolle — klicken zum Ändern (none → read → control)"
      : "Floor auf der Etagen-Zeile · Area je Bereich — klicken zum Ändern";
    return `
      <section class="legend" aria-label="Legend">
        <span><span class="swatch read"></span>read</span>
        <span><span class="swatch control"></span>control (implies read)</span>
        ${dbl}
        <span>${prov}</span>
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

  _matrixTemplate(roles) {
    if (!roles.length) {
      return '<div class="empty">Add Tessera roles in the integration options first.</div>';
    }
    const { floors, floorless } = this._floorGroups();
    if (!floors.length && !floorless.length) {
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
    const body = [];
    for (const floor of floors) {
      body.push(this._floorRow(floor, roles));
      for (const area of floor.areas) {
        body.push(this._areaRow(area, roles));
      }
    }
    if (floorless.length) {
      body.push(this._floorlessRow(roles.length));
      for (const area of floorless) {
        body.push(this._areaRow(area, roles));
      }
    }
    return `
      <div class="matrix-wrap">
        <table>
          <thead>
            <tr><th rowspan="2" scope="col">Bereich</th>${roleHead}</tr>
            <tr>${subHead}</tr>
          </thead>
          <tbody>${body.join("")}</tbody>
        </table>
      </div>
    `;
  }

  _floorRow(floor, roles) {
    const count = floor.areas.length;
    const meta = `· Etage · ${count} ${count === 1 ? "Bereich" : "Bereiche"}`;
    const cells = roles
      .map((role) => {
        const state = this._state(this._floorGrantById(floor.id, role.id));
        const pending = this._pending === `floor::${floor.id}::${role.id}`;
        return `
          <td class="bl">
            <button
              type="button"
              class="cell ${state}"
              data-floor="${this._escape(floor.id)}"
              data-role="${this._escape(role.id)}"
              ${this._disabledAttr(pending)}
              title="Etagen-Grant ${this._escape(floor.name)} / ${this._escape(role.name)}"
            >
              ${pending ? "Saving..." : state}
            </button>
          </td>
          <td></td>`;
      })
      .join("");
    return `
      <tr class="floorrow">
        <td>
          <span class="fname"><span class="fmark"></span>${this._escape(floor.name)}
            <span class="fmeta">${meta}</span></span>
        </td>
        ${cells}
      </tr>`;
  }

  _floorlessRow(roleCount) {
    return `
      <tr class="floorrow">
        <td><span class="fname">Ohne Etage</span></td>
        <td class="bl" colspan="${roleCount * 2}"></td>
      </tr>`;
  }

  _areaRow(area, roles) {
    const expanded = this._expanded.has(area.id);
    const rowDouble = roles.some((role) => this._isDouble(area.id, role.id));
    const cells = roles
      .map((role) => {
        const floorState = this._state(this._floorGrantFor(area.id, role.id));
        const areaState = this._state(this._grantFor(area.id, role.id));
        const dbl = this._isDouble(area.id, role.id) ? " dbl" : "";
        const pending = this._pending === `${area.id}::${role.id}`;
        return `
          <td class="bl">
            <span class="cell finherit ${floorState}">${floorState}</span>
          </td>
          <td>
            <button
              type="button"
              class="cell ${areaState}${dbl}"
              data-area="${this._escape(area.id)}"
              data-role="${this._escape(role.id)}"
              ${this._disabledAttr(pending)}
              title="Bereich-Grant ${this._escape(area.name)} / ${this._escape(role.name)}"
            >
              ${pending ? "Saving..." : areaState}
            </button>
          </td>`;
      })
      .join("");
    const nameCell = `
      <td class="aname">
        <button type="button" class="chev" data-expand="${this._escape(area.id)}"
          aria-label="Toggle entities" aria-expanded="${expanded ? "true" : "false"}">
          ${expanded ? "▾" : "▸"}
        </button>${this._escape(area.name)}${rowDouble ? '<span class="doppelt">doppelt</span>' : ""}
      </td>`;
    const rows = [`<tr>${nameCell}${cells}</tr>`];
    if (expanded) {
      rows.push(this._entityRow(area, roles.length));
    }
    return rows.join("");
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

  _setBoard(board) {
    if (this._board === board) {
      return;
    }
    this._board = board;
    this._render();
  }

  /** Advance one Label x Role cell to its next grant state and persist it. */
  async _toggleLabel(labelId, roleId) {
    if (!this._hass || this._pending) {
      return;
    }
    this._pending = `label::${labelId}::${roleId}`;
    this._error = "";
    this._render();
    try {
      this._data = await this._hass.connection.sendMessagePromise({
        type: "tessera/matrix/set_label_grant",
        label_id: labelId,
        role_id: roleId,
        ...this._nextGrant(this._labelGrantFor(labelId, roleId)),
      });
    } catch (err) {
      this._error = this._messageFromError(err);
    } finally {
      this._pending = "";
      this._render();
    }
  }

  /** Direct Label grant for a cell, defaulting to no permission. */
  _labelGrantFor(labelId, roleId) {
    return (
      this._data?.label_grants?.[labelId]?.[roleId] || {
        read: false,
        control: false,
      }
    );
  }

  /** Resolve a HA label colour token to a themed CSS colour for the row dot. */
  _labelDot(color) {
    const token = String(color || "").replace(/[^a-z0-9-]/gi, "");
    return token
      ? `var(--${token}-color, var(--primary-color))`
      : "var(--secondary-text-color)";
  }

  _labelBoard(roles) {
    if (!roles.length) {
      return '<div class="empty">Add Tessera roles in the integration options first.</div>';
    }
    const labels = this._data?.labels || [];
    if (!labels.length) {
      return `
        <div class="empty">
          Keine Home-Assistant-Labels gefunden. Labels in den HA-Einstellungen
          anlegen und Entitäten, Geräten oder Bereichen zuweisen — dann erscheinen
          sie hier.
        </div>`;
    }
    const roleHead = roles
      .map(
        (role) => `<th class="role-h bl" scope="col">${this._escape(role.name)}</th>`,
      )
      .join("");
    const body = labels.map((label) => this._labelRow(label, roles)).join("");
    return `
      <div class="matrix-wrap">
        <table>
          <thead>
            <tr><th scope="col">Label</th>${roleHead}</tr>
          </thead>
          <tbody>${body}</tbody>
        </table>
      </div>
    `;
  }

  _labelRow(label, roles) {
    const key = `label:${label.id}`;
    const expanded = this._expanded.has(key);
    const ids = this._data?.entities_by_label?.[label.id] || [];
    const icon = label.icon
      ? `<ha-icon icon="${this._escape(label.icon)}"></ha-icon>`
      : "";
    const cells = roles
      .map((role) => {
        const state = this._state(this._labelGrantFor(label.id, role.id));
        const pending = this._pending === `label::${label.id}::${role.id}`;
        return `
          <td class="bl">
            <button
              type="button"
              class="cell ${state}"
              data-label="${this._escape(label.id)}"
              data-role="${this._escape(role.id)}"
              ${this._disabledAttr(pending)}
              title="Label-Grant ${this._escape(label.name)} / ${this._escape(role.name)}"
            >
              ${pending ? "Saving..." : state}
            </button>
          </td>`;
      })
      .join("");
    const nameCell = `
      <td class="lname">
        <button type="button" class="chev" data-expand="${this._escape(key)}"
          aria-label="Toggle entities" aria-expanded="${expanded ? "true" : "false"}">
          ${expanded ? "▾" : "▸"}
        </button><span class="ldot" style="background: ${this._labelDot(label.color)}"></span>${icon}${this._escape(label.name)}
        <span class="fmeta">· ${ids.length} ${ids.length === 1 ? "Entität" : "Entitäten"}</span>
      </td>`;
    const rows = [`<tr>${nameCell}${cells}</tr>`];
    if (expanded) {
      rows.push(this._labelEntityRow(label, roles.length));
    }
    return rows.join("");
  }

  _labelEntityRow(label, roleCount) {
    const ids = this._data?.entities_by_label?.[label.id] || [];
    const colspan = 1 + roleCount;
    const boxes = ids.length
      ? ids
          .map((id) => `<span class="ebox">${this._escape(this._entityName(id))}</span>`)
          .join("")
      : '<span class="ebox">— keine Entitäten —</span>';
    return `
      <tr class="entrow">
        <td colspan="${colspan}">
          <div class="ehint">${ids.length} Entitäten · erben das Label-Recht</div>
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
