"use strict";

/* Small runtime contract for the vanilla client.
 *
 * This is intentionally not a build-time type system. It gives every view a
 * predictable shape while the project remains easy to open as static files.
 * A future TypeScript client can implement the same names without changing
 * the FastAPI payload boundary.
 */
(function () {
  function list(value) { return Array.isArray(value) ? value : []; }
  function object(value) { return value && typeof value === "object" ? value : {}; }

  function normalizeState(raw) {
    raw = object(raw);
    var player = object(raw.player);
    return Object.assign({}, raw, {
      tick: Number.isFinite(Number(raw.tick)) ? Number(raw.tick) : 0,
      agents: list(raw.agents),
      requests: list(raw.requests),
      crises: list(raw.crises),
      today_threads: list(raw.today_threads),
      events: list(raw.events),
      knowledge_claims: list(raw.knowledge_claims),
      locations: object(raw.locations),
      location_levels: object(raw.location_levels),
      player: player,
      campaign: object(raw.campaign),
      campaign_markers: object(raw.campaign_markers)
    });
  }

  function normalizeActionResult(raw) {
    raw = object(raw);
    return Object.assign({}, raw, {
      accepted: raw.accepted === true || raw.status === "ok" || raw.success === true,
      status: raw.status || ((raw.accepted === false || raw.success === false) ? "error" : "ok"),
      cost: Number(raw.cost || 0),
      hours: Number(raw.hours || 0),
      changes: list(raw.changes),
      story_beats: list(raw.story_beats),
      next_observation: raw.next_observation || null,
      details: object(raw.details),
      error_code: raw.error_code || null
    });
  }

  window.KTownContract = {
    normalizeState: normalizeState,
    normalizeActionResult: normalizeActionResult,
    list: list,
    object: object
  };
}());
