"use strict";

/* One network boundary for views.  No view should need to know whether an
 * endpoint is REST or WebSocket, or how JSON errors are represented. */
(function () {
  function json(response) {
    if (!response.ok) throw new Error("HTTP " + response.status);
    return response.json();
  }

  function get(path) {
    return fetch(path).then(json);
  }

  function post(path, body) {
    return fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {})
    }).then(json);
  }

  function sendPlayerAction(socket, action) {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      throw new Error("socket_unavailable");
    }
    socket.send(JSON.stringify({ type: "player_action", action: action || {} }));
  }

  window.KTownApi = {
    getState: function () {
      return get("/api/state").then(function (data) {
        return window.KTownContract.normalizeState(data);
      });
    },
    getRequests: function () { return get("/api/requests"); },
    getQuests: function () { return get("/api/quests"); },
    getKnowledge: function () { return get("/api/knowledge"); },
    interveneCrisis: function (id, action) {
      return post("/api/crisis/" + encodeURIComponent(id) + "/intervene", { action: action })
        .then(window.KTownContract.normalizeActionResult);
    },
    dialogueOptions: function (agentId) {
      return get("/api/dialogue/options/" + encodeURIComponent(agentId));
    },
    executeDialogue: function (agentId, optionId) {
      return post("/api/dialogue/execute/" + encodeURIComponent(agentId), { option_id: optionId })
        .then(window.KTownContract.normalizeActionResult);
    },
    sendPlayerAction: sendPlayerAction
  };
}());
