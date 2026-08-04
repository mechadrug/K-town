// K-town Sound Effects (Web Audio API)
window.KTownSound = (function() {
  "use strict";
  var ctx = null;

  function getCtx() {
    if (!ctx) {
      ctx = new (window.AudioContext || window.webkitAudioContext)();
    }
    return ctx;
  }

  function playTone(freq, duration, type, vol) {
    try {
      var c = getCtx();
      var osc = c.createOscillator();
      var gain = c.createGain();
      osc.type = type || "sine";
      osc.frequency.setValueAtTime(freq, c.currentTime);
      gain.gain.setValueAtTime(vol || 0.1, c.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, c.currentTime + (duration || 0.2));
      osc.connect(gain);
      gain.connect(c.destination);
      osc.start(c.currentTime);
      osc.stop(c.currentTime + (duration || 0.2));
    } catch(e) {}
  }

  return {
    // Player actions
    move: function() { playTone(440, 0.15, "sine", 0.08); },
    work: function() { playTone(330, 0.2, "triangle", 0.1); },
    talk: function() { playTone(520, 0.1, "sine", 0.06); playTone(580, 0.1, "sine", 0.06); },
    rest: function() { playTone(220, 0.3, "sine", 0.05); },
    addKnowledge: function() { playTone(660, 0.15, "square", 0.06); playTone(880, 0.15, "square", 0.04); },

    // Events
    eventGood: function() { playTone(523, 0.15, "sine", 0.08); playTone(659, 0.15, "sine", 0.08); playTone(784, 0.2, "sine", 0.06); },
    eventBad: function() { playTone(330, 0.3, "sawtooth", 0.08); playTone(220, 0.4, "sawtooth", 0.06); },
    dayStart: function() { playTone(440, 0.2, "sine", 0.1); setTimeout(function() { playTone(550, 0.2, "sine", 0.1); }, 200); setTimeout(function() { playTone(660, 0.3, "sine", 0.08); }, 400); },
    festival: function() { playTone(523, 0.2, "square", 0.06); playTone(659, 0.2, "square", 0.06); playTone(784, 0.2, "square", 0.06); playTone(1047, 0.4, "square", 0.04); },
    rumor: function() { playTone(440, 0.1, "triangle", 0.05); playTone(0, 0.05, "triangle", 0); playTone(550, 0.1, "triangle", 0.05); },

    // UI
    click: function() { playTone(800, 0.05, "sine", 0.04); },
    toast: function() { playTone(600, 0.1, "sine", 0.06); },
    error: function() { playTone(200, 0.2, "sawtooth", 0.08); },

    // Weather
    rain: function() { if (ctx) ctx.close(); ctx = null; }
  };
})();
