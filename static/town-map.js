// K-town SVG Town Map Module
window.TownMap = (function() {
  "use strict";
  var SVG_NS = "http://www.w3.org/2000/svg";
  var svg = null;
  var agentTokens = {};

  var LOCATIONS = {
    square:     { x: 400, y: 70,  name: "\u5e7f\u573a" },
    workshop:   { x: 150, y: 120, name: "\u5de5\u574a" },
    school:     { x: 180, y: 360, name: "\u5b66\u6821" },
    mine:       { x: 650, y: 130, name: "\u77ff\u6d1e" },
    wilderness: { x: 620, y: 370, name: "\u8352\u91ce" }
  };

  var PATHS = {
    "square-workshop":   "M400,70 C300,80 250,100 150,120",
    "square-school":     "M400,70 C300,150 220,250 180,360",
    "square-mine":       "M400,70 C550,60 600,80 650,130",
    "square-wilderness": "M400,70 C550,150 580,250 620,370",
    "workshop-school":   "M150,120 C140,200 150,280 180,360",
    "workshop-wilderness":"M150,120 C250,250 400,350 620,370",
    "school-wilderness": "M180,360 C350,380 500,375 620,370",
    "mine-wilderness":   "M650,130 C670,220 660,300 620,370",
    "mine-workshop":     "M650,130 C450,100 300,110 150,120"
  };

  var AGENT_EMOJI = {
    agent_elder: "\uD83D\uDC75", agent_blacksmith: "\uD83D\uDD28", agent_carpenter: "\uD83E\uDEB5",
    agent_forager: "\uD83C\uDF3F", agent_scout: "\uD83E\uDD1D", agent_merchant: "\uD83D\uDCB0",
    agent_teacher: "\uD83D\uDCD6", agent_farmer: "\uD83C\uDF3E", agent_storyteller: "\uD83D\uDCDC",
    agent_healer: "\uD83D\uDC8A", agent_miner: "\u26CF\uFE0F", agent_player: "\uD83D\uDC64"
  };

  var MOOD_COLORS = {
    happy: "#3fb950", neutral: "#d29922", sad: "#58a6ff",
    angry: "#f85149", anxious: "#f0883e"
  };

  function el(tag, attrs) {
    var e = document.createElementNS(SVG_NS, tag);
    if (attrs) for (var k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  function drawBackground() {
    // Sky gradient
    var defs = el("defs");
    var skyGrad = el("linearGradient", {id:"skyGrad", x1:"0", y1:"0", x2:"0", y2:"1"});
    skyGrad.appendChild(el("stop", {offset:"0%", "stop-color":"#87CEEB"}));
    skyGrad.appendChild(el("stop", {offset:"100%", "stop-color":"#E0F7FA"}));
    defs.appendChild(skyGrad);
    svg.appendChild(defs);

    // Sky rect
    svg.appendChild(el("rect", {x:0, y:0, width:800, height:500, fill:"url(#skyGrad)", id:"sky"}));

    // Mountains
    var mtns = el("g", {id:"mountains"});
    mtns.appendChild(el("polygon", {points:"0,200 100,80 200,200", fill:"#7B8FA1", opacity:0.4}));
    mtns.appendChild(el("polygon", {points:"150,200 280,60 400,200", fill:"#8FA5B2", opacity:0.4}));
    mtns.appendChild(el("polygon", {points:"500,200 620,50 750,200", fill:"#7B8FA1", opacity:0.4}));
    mtns.appendChild(el("polygon", {points:"650,200 750,100 850,200", fill:"#8FA5B2", opacity:0.5}));
    svg.appendChild(mtns);

    // Ground
    svg.appendChild(el("ellipse", {cx:400, cy:500, rx:500, ry:180, fill:"#4A7C59", id:"ground"}));
    svg.appendChild(el("ellipse", {cx:400, cy:500, rx:450, ry:160, fill:"#5B9A6F", opacity:0.6}));
  }

  function drawPaths() {
    var g = el("g", {id:"paths"});
    for (var key in PATHS) {
      g.appendChild(el("path", {
        d: PATHS[key], fill:"none", stroke:"#8B7355", "stroke-width": 8,
        "stroke-linecap": "round", opacity: 0.6, className: "map-path"
      }));
      g.appendChild(el("path", {
        d: PATHS[key], fill:"none", stroke:"#C4A882", "stroke-width": 4,
        "stroke-linecap": "round", "stroke-dasharray": "2,6", opacity: 0.8
      }));
    }
    svg.appendChild(g);
  }

  function drawRiver() {
    var g = el("g", {id:"river"});
    g.appendChild(el("path", {
      d:"M0,300 C100,310 200,280 350,320 C500,360 600,340 800,370",
      fill:"none", stroke:"#4A90D9", "stroke-width": 12, opacity: 0.4, className: "river-water"
    }));
    g.appendChild(el("path", {
      d:"M0,302 C100,312 200,282 350,322 C500,362 600,342 800,372",
      fill:"none", stroke:"#6BB3F0", "stroke-width": 6, opacity: 0.5, className: "river-flow"
    }));
    svg.appendChild(g);
  }

  function drawClouds() {
    var g = el("g", {id:"clouds"});
    var cloudData = [
      {x:100, y:30, s:1}, {x:300, y:50, s:0.8}, {x:550, y:25, s:1.2},
      {x:700, y:60, s:0.9}, {x:200, y:70, s:0.6}
    ];
    cloudData.forEach(function(c, i) {
      var cg = el("g", {className: "cloud", style:"animation-delay:" + (i * 3) + "s"});
      cg.appendChild(el("ellipse", {cx:c.x, cy:c.y, rx:40*c.s, ry:18*c.s, fill:"white", opacity:0.7}));
      cg.appendChild(el("ellipse", {cx:c.x+25*c.s, cy:c.y-8, rx:30*c.s, ry:15*c.s, fill:"white", opacity:0.6}));
      cg.appendChild(el("ellipse", {cx:c.x-20*c.s, cy:c.y+3, rx:25*c.s, ry:12*c.s, fill:"white", opacity:0.5}));
      g.appendChild(cg);
    });
    svg.appendChild(g);
  }

  function drawTrees() {
    var g = el("g", {id:"trees"});
    var treePositions = [
      {x:80,y:200,s:1},{x:90,y:210,s:0.7},{x:320,y:150,s:0.9},{x:500,y:180,s:0.8},
      {x:720,y:250,s:1},{x:100,y:420,s:0.9},{x:350,y:440,s:0.7},{x:500,y:450,s:0.8},
      {x:130,y:300,s:0.6},{x:680,y:420,s:0.9},{x:420,y:250,s:0.5},{x:250,y:180,s:0.7},
      {x:550,y:320,s:0.6},{x:750,y:350,s:0.8},{x:50,y:350,s:0.7}
    ];
    treePositions.forEach(function(t, i) {
      var tg = el("g", {className: i % 3 === 0 ? "tree-sway" : "", style:"animation-delay:" + (i * 0.5) + "s"});
      tg.appendChild(el("rect", {x:t.x-3*t.s, y:t.y, width:6*t.s, height:20*t.s, fill:"#5D4037", rx:2}));
      tg.appendChild(el("polygon", {points:t.x+","+(t.y-30*t.s)+" "+(t.x-15*t.s)+","+(t.y)+" "+(t.x+15*t.s)+","+(t.y), fill:"#2E7D32"}));
      tg.appendChild(el("polygon", {points:t.x+","+(t.y-40*t.s)+" "+(t.x-12*t.s)+","+(t.y-15*t.s)+" "+(t.x+12*t.s)+","+(t.y-15*t.s), fill:"#388E3C"}));
      tg.appendChild(el("polygon", {points:t.x+","+(t.y-48*t.s)+" "+(t.x-8*t.s)+","+(t.y-28*t.s)+" "+(t.x+8*t.s)+","+(t.y-28*t.s), fill:"#43A047"}));
      g.appendChild(tg);
    });
    svg.appendChild(g);
  }

  function drawLocation(id) {
    var loc = LOCATIONS[id];
    if (!loc) return;
    var g = el("g", {id:"location-" + id, className: "loc-group"});
    g.appendChild(el("circle", {
      cx: loc.x, cy: loc.y, r: 38, fill:"rgba(255,255,255,0.15)",
      stroke:"rgba(255,255,255,0.3)", "stroke-width": 2, className: "loc-glow"
    }));

    if (id === "square") drawSquare(g, loc.x, loc.y);
    else if (id === "workshop") drawWorkshop(g, loc.x, loc.y);
    else if (id === "school") drawSchool(g, loc.x, loc.y);
    else if (id === "mine") drawMine(g, loc.x, loc.y);
    else if (id === "wilderness") drawWilderness(g, loc.x, loc.y);

    g.appendChild(el("text", {
      x: loc.x, y: loc.y + 45, "text-anchor": "middle",
      fill: "#333", "font-size": 13, "font-weight": "bold"
    }));
    g.lastChild.textContent = loc.name;

    svg.appendChild(g);
  }

  function drawSquare(g, x, y) {
    g.appendChild(el("rect", {x:x-30, y:y-20, width:60, height:40, fill:"#D7CCC8", rx:4}));
    g.appendChild(el("circle", {cx:x, cy:y, r:10, fill:"#64B5F6", opacity:0.7}));
    g.appendChild(el("circle", {cx:x, cy:y-2, r:6, fill:"#90CAF9", opacity:0.8}));
    g.appendChild(el("rect", {x:x+15, y:y-25, width:3, height:25, fill:"#5D4037"}));
    g.appendChild(el("polygon", {points:[x+18,y-25,x+35,y-20,x+18,y-15], fill:"#E53935"}));
    g.appendChild(el("rect", {x:x-25, y:y+5, width:12, height:6, fill="#8D6E63"}));
    g.appendChild(el("rect", {x:x+13, y:y+5, width:12, height:6, fill:"#8D6E61"}));
  }

  function drawWorkshop(g, x, y) {
    g.appendChild(el("rect", {x:x-28, y:y-18, width:56, height:36, fill:"#8D6E63", rx:2}));
    g.appendChild(el("polygon", {points:[x-32,y-18,x+32,y-18,x,y-35], fill:"#5D4037"}));
    g.appendChild(el("rect", {x:x+12, y:y-32, width:8, height:16, fill:"#4E342E"}));
    g.appendChild(el("circle", {cx:x+16, cy:y-36, r:5, fill:"#90A4AE", opacity:0.5, className: "smoke"}));
    g.appendChild(el("circle", {cx:x+16, cy:y-40, r:4, fill:"#90A4AE", opacity:0.3, className: "smoke", style:"animation-delay:0.5s"}));
    g.appendChild(el("circle", {cx:x-15, cy:y, r:5, fill:"#78909C"}));
    g.appendChild(el("rect", {x:x+10, y:y-5, width:15, height:10, fill="#455A64", rx:1}));
  }

  function drawSchool(g, x, y) {
    g.appendChild(el("rect", {x:x-25, y:y-15, width:50, height:30, fill:"#FFF9C4", rx:2}));
    g.appendChild(el("polygon", {points:[x-28,y-15,x+28,y-15,x,y-30], fill:"#F57F17"}));
    g.appendChild(el("rect", {x:x-5, y:y-40, width:10, height:15, fill:"#795548"}));
    g.appendChild(el("circle", {cx:x, cy:y-43, r:4, fill:"#FDD835"}));
    g.appendChild(el("rect", {x:x-18, y:y-5, width:10, height:10, fill:"#42A5F5", rx:1}));
    g.appendChild(el("rect", {x:x+8, y:y-5, width:10, height:10, fill:"#42A5F5", rx:1}));
    g.appendChild(el("rect", {x:x-5, y:y+5, width:10, height:12, fill="#5D4037"}));
  }

  function drawMine(g, x, y) {
    g.appendChild(el("polygon", {points:[x-30,y+25,x+30,y+25,x,y-25], fill="#5D4037"}));
    g.appendChild(el("polygon", {points:[x-30,y+25,x+30,y+25,x,y-25], fill="#4E342E"}));
    g.appendChild(el("ellipse", {cx:x, cy:y+5, rx:18, ry:12, fill:"#3E2723"}));
    g.appendChild(el("ellipse", {cx:x, cy:y+3, rx:14, ry:9, fill:"#1B0000", opacity:0.8}));
    g.appendChild(el("line", {x1:x-20, y1:y+18, x2:x+20, y2:y+18, stroke:"#795548", "stroke-width": 2}));
    g.appendChild(el("line", {x1:x-20, y1:y+22, x2:x+20, y2:y+22, stroke:"#795548", "stroke-width": 2}));
    g.appendChild(el("circle", {cx:x-10, cy:y+20, r:3, fill:"#4E342E"}));
    g.appendChild(el("circle", {cx:x+10, cy:y+20, r:3, fill:"#4E342E"}));
    g.appendChild(el("circle", {cx:x, cy:y, r:3, fill:"#FFEB3B", opacity:0.6}));
  }

  function drawWilderness(g, x, y) {
    // Campfire
    g.appendChild(el("polygon", {points:[x-5,y+10,x+5,y+10,x,y-5], fill="#5D4037"}));
    g.appendChild(el("path", {d:"M" + x + "," + (y-15) + " C" + (x-8) + "," + (y-5) + " " + (x+8) + "," + (y-8) + " " + x + "," + (y-15), fill:"#FF6F00", opacity:0.7}));
    // Tent
    g.appendChild(el("polygon", {points:[x-20,y+15,x+20,y+15,x,y-10], fill:"#A1887F"}));
    g.appendChild(el("polygon", {points:[x-20,y+15,x,y-10,x,y+15], fill:"#8D6E63"}));
    // Extra trees
    g.appendChild(el("polygon", {points:[x+15,y+5,x+25,y+20,x+5,y+20], fill:"#1B5E20"}));
    g.appendChild(el("polygon", {points:[x-20,y+0,x-10,y+20,x-30,y+20], fill:"#2E7D32"}));
    // Mushrooms
    g.appendChild(el("ellipse", {cx:x+22, cy:y+18, rx:4, ry:3, fill:"#E53935"}));
    g.appendChild(el("rect", {x:x+21, y:y+18, width:3, height:4, fill:"#FFFDE7"}));
  }

  function createAgentToken(agent) {
    var loc = LOCATIONS[agent.location];
    if (!loc) return null;
    var g = el("g", {id:"agent-" + agent.id, className: "agent-token"});
    var moodColor = MOOD_COLORS[agent.mood] || "#888";
    var emoji = AGENT_EMOJI[agent.id] || "\uD83D\uDC64";

    g.appendChild(el("circle", {
      cx: loc.x, cy: loc.y, r: 14, fill: "white", stroke: moodColor, "stroke-width": 3
    }));
    var txt = el("text", {
      x: loc.x, y: loc.y + 4, "text-anchor": "middle", "font-size": 12
    });
    txt.textContent = emoji;
    g.appendChild(txt);
    g.appendChild(el("title")).textContent = agent.name;

    svg.appendChild(g);
    agentTokens[agent.id] = g;
    return g;
  }

  function updateAgentPositions(agents) {
    agents.forEach(function(agent) {
      var existing = agentTokens[agent.id];
      if (!existing) {
        createAgentToken(agent);
        return;
      }
      var loc = LOCATIONS[agent.location];
      if (!loc) return;
      var circle = existing.querySelector("circle");
      if (circle) {
        circle.setAttribute("cx", loc.x);
        circle.setAttribute("cy", loc.y);
        circle.setAttribute("stroke", MOOD_COLORS[agent.mood] || "#888");
      }
      var text = existing.querySelector("text");
      if (text) {
        text.setAttribute("x", loc.x);
        text.setAttribute("y", loc.y + 4);
      }
    });
  }

  function animateMove(agentId, fromLoc, toLoc) {
    var token = agentTokens[agentId];
    if (!token) return;
    var from = LOCATIONS[fromLoc];
    var to = LOCATIONS[toLoc];
    if (!from || !to) return;

    var pathKey = fromLoc + "-" + toLoc;
    var pathSel = PATHS[pathKey] || PATHS[toLoc + "-" + fromLoc];
    if (!pathSel) {
      var circle = token.querySelector("circle");
      if (circle) { circle.setAttribute("cx", to.x); circle.setAttribute("cy", to.y); }
      var text = token.querySelector("text");
      if (text) { text.setAttribute("x", to.x); text.setAttribute("y", to.y + 4); }
      return;
    }

    var pathEl = document.createElementNS(SVG_NS, "path");
    pathEl.setAttribute("d", pathSel);
    var length = pathEl.getTotalLength ? pathEl.getTotalLength() : 500;
    var circle = token.querySelector("circle");
    var text = token.querySelector("text");
    if (!circle || !text) return;

    var animTime = 1500;
    var start = null;
    function step(ts) {
      if (!start) start = ts;
      var t = Math.min(1, (ts - start) / animTime);
      var pt = pathEl.getPointAtLength(t * length);
      circle.setAttribute("cx", pt.x);
      circle.setAttribute("cy", pt.y);
      text.setAttribute("x", pt.x);
      text.setAttribute("y", pt.y + 4);
      if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  function setWeather(weather) {
    var existing = document.getElementById("weather-overlay");
    if (existing) existing.remove();
    if (!weather || weather === "clear") return;

    var g = el("g", {id:"weather-overlay"});
    if (weather === "rainy") {
      for (var i = 0; i < 40; i++) {
        var rx = Math.random() * 800;
        var ry = Math.random() * 300;
        g.appendChild(el("line", {
          x1: rx, y1: ry, x2: rx-3, y2: ry+15,
          stroke: "#64B5F6", "stroke-width": 2, opacity: 0.4, className: "raindrop"
        }));
      }
    } else if (weather === "snowy") {
      for (var i = 0; i < 30; i++) {
        var sx = Math.random() * 800;
        var sy = Math.random() * 300;
        g.appendChild(el("circle", {cx: sx, cy: sy, r: 2+Math.random()*2, fill: "white", opacity: 0.7, className: "snowflake"}));
      }
    } else if (weather === "cloudy") {
      for (var i = 0; i < 3; i++) {
        var cx = 150 + i * 250;
        g.appendChild(el("ellipse", {cx: cx, cy: 20+i*10, rx: 60+i*10, ry: 25+i*5, fill: "#B0BEC5", opacity: 0.5}));
      }
    } else if (weather === "windy") {
      for (var i = 0; i < 8; i++) {
        var wy = 50 + i * 50;
        g.appendChild(el("path", {
          d: "M" + (50+Math.random()*100) + "," + wy + " C" + (200+Math.random()*100) + "," + (wy-10) + " " + (400+Math.random()*100) + "," + (wy+10) + " " + (700+Math.random()*50) + "," + wy,
          fill: "none", stroke: "rgba(255,255,255,0.3)", "stroke-width": 2, className: "wind-line"
        }));
      }
    }
    svg.appendChild(g);
  }

  function setHour(hour) {
    var sky = document.getElementById("sky");
    if (!sky) return;
    var colors = {
      night: ["#0D1B2A", "#1B2838"],
      dawn: ["#FF6F61", "#FFB74D"],
      day: ["#87CEEB", "#E0F7FA"],
      dusk: ["#FF8A65", "#FFB74D"]
    };
    var c;
    if (hour >= 21 || hour < 5) c = colors.night;
    else if (hour >= 5 && hour < 8) c = colors.dawn;
    else if (hour >= 8 && hour < 17) c = colors.day;
    else c = colors.dusk;

    var grad = svg.querySelector("#skyGrad stop:first-child");
    var grad2 = svg.querySelector("#skyGrad stop:last-child");
    if (grad) grad.setAttribute("stop-color", c[0]);
    if (grad2) grad2.setAttribute("stop-color", c[1]);

    // Sun/Moon
    var celestial = document.getElementById("celestial");
    if (!celestial) {
      celestial = el("circle", {id:"celestial", r:20});
      svg.insertBefore(celestial, svg.firstChild);
    }
    var sunX = 50 + (hour / 24) * 700;
    var sunY = 60 + Math.sin((hour / 24) * Math.PI) * -40;
    if (hour >= 18 || hour < 6) {
      celestial.setAttribute("fill", "#E0E0E0");
      celestial.setAttribute("cx", 650 - ((hour > 18 ? hour - 18 : hour + 6) / 12) * 600);
      celestial.setAttribute("cy", 40);
    } else {
      celestial.setAttribute("fill", "#FDD835");
      celestial.setAttribute("cx", sunX);
      celestial.setAttribute("cy", sunY);
    }
  }

  // Public API
  return {
    init: function(svgElement) {
      svg = svgElement;
      svg.setAttribute("viewBox", "0 0 800 500");
      svg.innerHTML = "";
      drawBackground();
      drawPaths();
      drawRiver();
      drawClouds();
      drawTrees();
      ["square","workshop","school","mine","wilderness"].forEach(function(id) {
        drawLocation(id);
      });
      agentTokens = {};
    },
    update: function(agents, weather, hour) {
      if (!svg) return;
      updateAgentPositions(agents);
      if (weather) setWeather(weather);
      if (hour !== undefined) setHour(hour);
    },
    animateMove: animateMove,
    setWeather: function(w) { if (svg) setWeather(w); },
    setHour: function(h) { if (svg) setHour(h); }
  };
})();
