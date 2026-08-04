// K-town v2.0 — 音效系统 (Web Audio API)
window.KTownSound = (function() {
  "use strict";
  var ctx = null;

  function getCtx() {
    if (!ctx) {
      try {
        ctx = new (window.AudioContext || window.webkitAudioContext)();
      } catch(e) { return null; }
    }
    return ctx;
  }

  function playTone(freq, duration, type, vol, ramp) {
    var c = getCtx();
    if (!c) return;
    try {
      var osc = c.createOscillator();
      var gain = c.createGain();
      osc.type = type || "sine";
      osc.frequency.setValueAtTime(freq, c.currentTime);
      gain.gain.setValueAtTime(vol || 0.08, c.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, c.currentTime + (duration || 0.2));
      osc.connect(gain);
      gain.connect(c.destination);
      osc.start(c.currentTime);
      osc.stop(c.currentTime + (duration || 0.2));
    } catch(e) {}
  }

  function playChord(freqs, duration, type, vol) {
    freqs.forEach(function(f, i) {
      setTimeout(function() { playTone(f, duration, type, vol); }, i * 50);
    });
  }

  return {
    // 连接
    connect: function() { playTone(523, 0.15, "sine", 0.06); setTimeout(function() { playTone(659, 0.2, "sine", 0.06); }, 150); },
    
    // 玩家行动
    move: function() { playTone(440, 0.12, "sine", 0.06); setTimeout(function() { playTone(520, 0.1, "sine", 0.05); }, 80); },
    work: function() { playTone(330, 0.15, "triangle", 0.08); setTimeout(function() { playTone(330, 0.1, "triangle", 0.06); }, 150); },
    talk: function() { playTone(520, 0.08, "sine", 0.05); playTone(580, 0.08, "sine", 0.05); },
    rest: function() { playTone(220, 0.4, "sine", 0.04); },
    addKnowledge: function() { playTone(660, 0.12, "square", 0.05); playTone(880, 0.12, "square", 0.03); },
    
    // 事件
    event: function() { playTone(440, 0.15, "triangle", 0.06); },
    eventGood: function() { playChord([523, 659, 784], 0.25, "sine", 0.06); },
    eventBad: function() { playTone(330, 0.3, "sawtooth", 0.06); playTone(220, 0.4, "sawtooth", 0.04); },
    dayStart: function() { playChord([440, 554, 659], 0.3, "sine", 0.07); },
    festival: function() { playChord([523, 659, 784, 1047], 0.3, "square", 0.04); },
    rumor: function() { playTone(440, 0.08, "triangle", 0.04); playTone(550, 0.08, "triangle", 0.04); },
    
    // UI
    click: function() { playTone(800, 0.04, "sine", 0.03); },
    success: function() { playTone(523, 0.1, "sine", 0.06); playTone(784, 0.15, "sine", 0.05); },
    error: function() { playTone(200, 0.2, "sawtooth", 0.06); },
    
    // 天气
    rain: function() { if (ctx) { ctx.close(); ctx = null; } },
    
    // 重置
    reset: function() { if (ctx) { ctx.close(); ctx = null; } }
  };
})();
