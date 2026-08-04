// K-town v2.0 — SVG 地图渲染器 v2.1
// 手绘水彩风格小镇地图 + 动画系统
window.TownMapV2 = (function() {
  "use strict";
  
  var SVG_NS = "http://www.w3.org/2000/svg";
  var svg = null;
  var agentTokens = {};
  var animFrameIds = [];
  var currentWeather = "clear";
  var currentHour = 12;
  var sceneElements = {};

  // 地点配置
  var LOCATIONS = {
    square: {
      x: 500, y: 200, name: "广场", icon: "🏛",
      width: 160, height: 120, color: "#D7CCC8", roofColor: "#8D6E63",
      desc: "小镇中心的公共集会场所，每天早上有集市"
    },
    workshop: {
      x: 180, y: 160, name: "工坊", icon: "🔨",
      width: 130, height: 100, color: "#FFCCBC", roofColor: "#BF360C",
      desc: "制作工具和加工材料的场所，炉火日夜不熄"
    },
    wilderness: {
      x: 800, y: 420, name: "荒野", icon: "🌲",
      width: 180, height: 140, color: "#A5D6A7", roofColor: "#2E7D32",
      desc: "采集资源和探索未知的区域，蕴藏着秘密"
    },
    school: {
      x: 200, y: 440, name: "学校", icon: "📚",
      width: 120, height: 100, color: "#C5CAE9", roofColor: "#283593",
      desc: "教学育人和治病救人的场所，知识的灯塔"
    },
    mine: {
      x: 800, y: 150, name: "矿洞", icon: "⛏",
      width: 130, height: 110, color: "#B0BEC5", roofColor: "#37474F",
      desc: "采集矿石的地下洞穴，深处据说有稀有矿物"
    }
  };

  // 道路连接
  var PATHS = [
    { from: "square", to: "workshop", type: "main" },
    { from: "square", to: "wilderness", type: "main" },
    { from: "square", to: "school", type: "main" },
    { from: "square", to: "mine", type: "main" },
    { from: "workshop", to: "school", type: "dirt" },
    { from: "wilderness", to: "school", type: "dirt" },
    { from: "wilderness", to: "mine", type: "dirt" },
    { from: "workshop", to: "mine", type: "dirt" }
  ];

  // Agent 个人色
  var AGENT_COLORS = {
    agent_elder: "#8D6E63", agent_blacksmith: "#FF7043", agent_carpenter: "#7E57C2",
    agent_forager: "#66BB6A", agent_scout: "#42A5F5", agent_merchant: "#FFA726",
    agent_teacher: "#5C6BC0", agent_farmer: "#9CCC65", agent_storyteller: "#EC407A",
    agent_healer: "#26C6DA", agent_miner: "#78909C", agent_player: "#FF6B35"
  };

  var MOOD_COLORS = {
    happy: "#7CB342", neutral: "#FFB74D", sad: "#64B5F6",
    angry: "#E57373", anxious: "#FF8A65"
  };

  var MOOD_EMOJI = {
    happy: "😊", neutral: "😐", sad: "😢", angry: "😠", anxious: "😰"
  };

  // ===== 工具函数 =====
  function el(tag, attrs) {
    var e = document.createElementNS(SVG_NS, tag);
    if (attrs) for (var k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  // ===== 背景绘制 =====
  function drawBackground() {
    var defs = el("defs");
    
    // 天空渐变
    var skyGrad = el("linearGradient", {id: "skyGradient", x1: "0", y1: "0", x2: "0", y2: "1"});
    skyGrad.appendChild(el("stop", {offset: "0%", "stop-color": "#87CEEB", id: "skyStop1"}));
    skyGrad.appendChild(el("stop", {offset: "100%", "stop-color": "#E0F7FA", id: "skyStop2"}));
    defs.appendChild(skyGrad);

    // 地面渐变
    var groundGrad = el("linearGradient", {id: "groundGradient", x1: "0", y1: "0", x2: "0", y2: "1"});
    groundGrad.appendChild(el("stop", {offset: "0%", "stop-color": "#5B9A6F"}));
    groundGrad.appendChild(el("stop", {offset: "100%", "stop-color": "#81C784"}));
    defs.appendChild(groundGrad);

    // 发光滤镜
    var glowFilter = el("filter", {id: "glow", x: "-50%", y: "-50%", width: "200%", height: "200%"});
    var feGaussian = el("feGaussianBlur", {stdDeviation: "6", result: "blur"});
    var feMerge = el("feMerge");
    feMerge.appendChild(el("feMergeNode", {in: "blur"}));
    feMerge.appendChild(el("feMergeNode", {in: "SourceGraphic"}));
    glowFilter.appendChild(feGaussian);
    glowFilter.appendChild(feMerge);
    defs.appendChild(glowFilter);

    // 柔和阴影滤镜
    var shadowFilter = el("filter", {id: "softShadow", x: "-20%", y: "-20%", width: "140%", height: "140%"});
    var feDrop = el("feDropShadow", {dx: "2", dy: "4", stdDeviation: "3", "flood-color": "rgba(0,0,0,0.15)"});
    shadowFilter.appendChild(feDrop);
    defs.appendChild(shadowFilter);

    svg.appendChild(defs);

    // 天空背景
    svg.appendChild(el("rect", {x: 0, y: 0, width: 1000, height: 600, fill: "url(#skyGradient)", id: "sky"}));

    // 昼夜色调遮罩层
    var tint = el("rect", {x: 0, y: 0, width: 1000, height: 600, fill: "transparent", id: "daynight-tint", pointerEvents: "none"});
    svg.appendChild(tint);
    sceneElements.daynightTint = tint;

    // 远山层次
    var hills = el("g", {id: "hills"});
    hills.appendChild(el("path", {
      d: "M0,350 Q150,250 300,320 Q450,220 600,300 Q750,200 900,280 Q950,250 1000,300 L1000,600 L0,600 Z",
      fill: "#78909C", opacity: "0.25"
    }));
    hills.appendChild(el("path", {
      d: "M0,380 Q200,300 400,360 Q600,280 800,350 Q900,310 1000,360 L1000,600 L0,600 Z",
      fill: "#90A4AE", opacity: "0.3"
    }));
    svg.appendChild(hills);

    // 地面
    svg.appendChild(el("ellipse", {cx: 500, cy: 650, rx: 700, ry: 250, fill: "url(#groundGradient)", id: "ground"}));

    // 河流
    var riverG = el("g", {id: "river"});
    riverG.appendChild(el("path", {
      d: "M0,450 C150,430 250,460 400,440 C550,420 700,450 850,430 C920,420 1000,440 1000,440",
      fill: "none", stroke: "#4A90D9", "stroke-width": 16, opacity: 0.25, className: "river-water"
    }));
    riverG.appendChild(el("path", {
      d: "M0,452 C150,432 250,462 400,442 C550,422 700,452 850,432 C920,422 1000,442 1000,442",
      fill: "none", stroke: "#6BB3F0", "stroke-width": 6, opacity: 0.35
    }));
    svg.appendChild(riverG);
    sceneElements.river = riverG;
  }

  // ===== 道路绘制 =====
  function drawPaths() {
    var g = el("g", {id: "paths"});
    PATHS.forEach(function(p) {
      var from = LOCATIONS[p.from];
      var to = LOCATIONS[p.to];
      if (!from || !to) return;
      
      var midX = (from.x + to.x) / 2;
      var midY = (from.y + to.y) / 2 - 20;
      var pathD = "M" + from.x + "," + (from.y + 30) + " Q" + midX + "," + midY + " " + to.x + "," + (to.y + 30);
      
      // 道路阴影
      g.appendChild(el("path", {
        d: pathD, fill: "none", stroke: "rgba(0,0,0,0.08)",
        "stroke-width": p.type === "main" ? 16 : 10, "stroke-linecap": "round"
      }));
      
      // 道路主体
      g.appendChild(el("path", {
        d: pathD, fill: "none", 
        stroke: p.type === "main" ? "#C4A882" : "#A1887F",
        "stroke-width": p.type === "main" ? 10 : 6,
        "stroke-linecap": "round", opacity: 0.6
      }));
      
      if (p.type === "main") {
        g.appendChild(el("path", {
          d: pathD, fill: "none", stroke: "#E8D5B8",
          "stroke-width": 1.5, "stroke-dasharray": "6,8",
          "stroke-linecap": "round", opacity: 0.4
        }));
      }
    });
    svg.appendChild(g);
  }

  // ===== 场景动画元素 =====
  function drawSceneAnimations() {
    var sceneG = el("g", {id: "scene-animations"});
    
    // 工坊烟囱的烟
    var smokeG = el("g", {id: "workshop-smoke"});
    var workshop = LOCATIONS.workshop;
    for (var i = 0; i < 3; i++) {
      var smoke = el("circle", {
        cx: workshop.x + 30 + i * 5, cy: workshop.y - 70 - i * 15,
        r: 6 + i * 3, fill: "rgba(180,180,180,0.3)", className: "smoke-puff"
      });
      smoke.style.animationDelay = (i * 0.8) + "s";
      smokeG.appendChild(smoke);
    }
    sceneG.appendChild(smokeG);
    sceneElements.smoke = smokeG;

    // 荒野的树
    var treesG = el("g", {id: "wilderness-trees"});
    var wilderness = LOCATIONS.wilderness;
    var treePositions = [
      {x: wilderness.x - 50, y: wilderness.y + 20},
      {x: wilderness.x + 40, y: wilderness.y - 10},
      {x: wilderness.x - 20, y: wilderness.y + 40},
      {x: wilderness.x + 60, y: wilderness.y + 30}
    ];
    treePositions.forEach(function(tp, i) {
      var tree = el("g", {className: "tree-sway", style: "animation-delay:" + (i * 0.5) + "s"});
      // 树干
      tree.appendChild(el("rect", {
        x: tp.x - 3, y: tp.y - 15, width: 6, height: 20, fill: "#5D4037"
      }));
      // 树冠
      tree.appendChild(el("circle", {
        cx: tp.x, cy: tp.y - 25, r: 15, fill: "#388E3C", opacity: 0.8
      }));
      tree.appendChild(el("circle", {
        cx: tp.x - 8, cy: tp.y - 18, r: 10, fill: "#4CAF50", opacity: 0.7
      }));
      tree.appendChild(el("circle", {
        cx: tp.x + 8, cy: tp.y - 20, r: 11, fill: "#2E7D32", opacity: 0.75
      }));
      treesG.appendChild(tree);
    });
    sceneG.appendChild(treesG);
    sceneElements.trees = treesG;

    // 矿洞的矿石闪光
    var mineG = el("g", {id: "mine-sparkle"});
    var mine = LOCATIONS.mine;
    for (var i = 0; i < 4; i++) {
      var sparkle = el("circle", {
        cx: mine.x - 30 + Math.random() * 60,
        cy: mine.y + 10 + Math.random() * 30,
        r: 2 + Math.random() * 2,
        fill: "#B0BEC5", className: "sparkle",
        style: "animation-delay:" + (i * 1.2) + "s"
      });
      mineG.appendChild(sparkle);
    }
    sceneG.appendChild(mineG);
    sceneElements.sparkles = mineG;

    svg.appendChild(sceneG);
  }

  // ===== 地点绘制 =====
  function drawLocation(id) {
    var loc = LOCATIONS[id];
    if (!loc) return;

    var g = el("g", {className: "location-marker", "data-id": id});
    g.style.cursor = "pointer";

    // 光晕
    var glow = el("ellipse", {
      cx: loc.x, cy: loc.y + 30, rx: loc.width / 2 + 15, ry: 18,
      fill: "rgba(0,0,0,0.06)", className: "loc-glow"
    });
    g.appendChild(glow);

    // 建筑阴影
    g.appendChild(el("ellipse", {
      cx: loc.x + 5, cy: loc.y + loc.height / 2 + 10,
      rx: loc.width / 2, ry: 6, fill: "rgba(0,0,0,0.08)"
    }));

    // 建筑主体
    var building = el("rect", {
      x: loc.x - loc.width / 2, y: loc.y - loc.height / 2,
      width: loc.width, height: loc.height, rx: 10, ry: 10,
      fill: loc.color, stroke: "rgba(0,0,0,0.12)", "stroke-width": 1.5,
      className: "loc-building", filter: "url(#softShadow)"
    });
    g.appendChild(building);

    // 屋顶
    var roofH = loc.height * 0.45;
    var roof = el("polygon", {
      points: (loc.x - loc.width / 2 - 12) + "," + (loc.y - loc.height / 2) + " " +
              loc.x + "," + (loc.y - loc.height / 2 - roofH) + " " +
              (loc.x + loc.width / 2 + 12) + "," + (loc.y - loc.height / 2),
      fill: loc.roofColor, opacity: 0.85,
      stroke: "rgba(0,0,0,0.1)", "stroke-width": 1
    });
    g.appendChild(roof);

    // 屋顶边缘高光
    g.appendChild(el("line", {
      x1: loc.x - loc.width / 2 - 10, y1: loc.y - loc.height / 2,
      x2: loc.x, y2: loc.y - loc.height / 2 - roofH,
      stroke: "rgba(255,255,255,0.2)", "stroke-width": 2
    }));

    // 建筑内部装饰（小窗户）
    var windowRows = Math.floor(loc.height / 30);
    var windowCols = Math.floor(loc.width / 35);
    for (var r = 0; r < windowRows; r++) {
      for (var c = 0; c < windowCols; c++) {
        var wx = loc.x - loc.width / 2 + 15 + c * 32;
        var wy = loc.y - loc.height / 2 + 12 + r * 28;
        if (wx < loc.x + loc.width / 2 - 10 && wy < loc.y + loc.height / 2 - 10) {
          g.appendChild(el("rect", {
            x: wx, y: wy, width: 12, height: 10, rx: 2,
            fill: "rgba(255,255,255,0.25)", stroke: "rgba(0,0,0,0.08)", "stroke-width": 0.5
          }));
          // 窗户十字
          g.appendChild(el("line", {
            x1: wx + 6, y1: wy, x2: wx + 6, y2: wy + 10,
            stroke: "rgba(0,0,0,0.06)", "stroke-width": 0.5
          }));
          g.appendChild(el("line", {
            x1: wx, y1: wy + 5, x2: wx + 12, y2: wy + 5,
            stroke: "rgba(0,0,0,0.06)", "stroke-width": 0.5
          }));
        }
      }
    }

    // 地点图标
    var iconText = el("text", {
      x: loc.x, y: loc.y + 8, "text-anchor": "middle", "font-size": "30"
    });
    iconText.textContent = loc.icon;
    g.appendChild(iconText);

    // 名称标签背景
    var nameBg = el("rect", {
      x: loc.x - 35, y: loc.y + loc.height / 2 + 14,
      width: 70, height: 22, rx: 11, ry: 11,
      fill: "var(--panel-bg)", stroke: "var(--panel-border)",
      "stroke-width": 1, opacity: 0.92, filter: "url(#softShadow)"
    });
    g.appendChild(nameBg);

    // 名称文字
    var nameText = el("text", {
      x: loc.x, y: loc.y + loc.height / 2 + 29,
      "text-anchor": "middle", "font-size": "12",
      "font-weight": "600", fill: "var(--text-primary)"
    });
    nameText.textContent = loc.name;
    g.appendChild(nameText);

    // 点击事件
    g.addEventListener("click", function() {
      if (window.AppV2 && window.AppV2.onLocationClick) {
        window.AppV2.onLocationClick(id, loc);
      }
    });

    svg.appendChild(g);
  }

  // ===== Agent 绘制（持久 token + 平滑动画）=====
  function agentPos(agent) {
    var loc = LOCATIONS[agent.location];
    if (!loc) return {x: 500, y: 300};
    var hash = 0;
    for (var i = 0; i < agent.id.length; i++) {
      hash = ((hash << 5) - hash) + agent.id.charCodeAt(i);
      hash = hash & hash;
    }
    var offsetX = ((hash % 100) / 100 - 0.5) * (loc.width * 0.6);
    var offsetY = (((hash >> 8) % 100) / 100 - 0.5) * (loc.height * 0.3);
    return {x: loc.x + offsetX, y: loc.y + offsetY + 25};
  }

  function drawAgent(agent) {
    var loc = LOCATIONS[agent.location];
    if (!loc) return;
    var pos = agentPos(agent);
    var color = AGENT_COLORS[agent.id] || "#888";
    var moodColor = MOOD_COLORS[agent.mood] || "#FFB74D";
    var name = agent.name || agent.id;

    // 注意：SVG 用 class 属性，className 不生效（el 已按 setAttribute 处理）
    var g = el("g", {"class": "agent-token", "data-id": agent.id});
    g.style.transform = "translate(" + pos.x + "px, " + pos.y + "px)";

    // 名字标签（宽度自适应完整姓名，不再截断）
    var labelW = Math.max(48, name.length * 8 + 10);
    g.appendChild(el("rect", {
      x: -labelW / 2, y: -30, width: labelW, height: 16, rx: 8,
      fill: "var(--panel-bg)", stroke: color, "stroke-width": 1.5,
      "class": "agent-label-bg", opacity: 0.9
    }));
    var labelText = el("text", {
      x: 0, y: -19, "text-anchor": "middle", "font-size": "8",
      "font-weight": "600", fill: color
    });
    labelText.textContent = name;
    g.appendChild(labelText);

    // 心情光环（脉动）
    g.appendChild(el("circle", {cx: 0, cy: 0, r: 14, fill: moodColor, opacity: 0.15, "class": "agent-aura"}));
    // Agent 身体
    g.appendChild(el("circle", {cx: 0, cy: 0, r: 11, fill: color, stroke: "white", "stroke-width": 2.5, "class": "agent-body"}));
    // 心情表情
    var faceText = el("text", {x: 0, y: 4, "text-anchor": "middle", "font-size": "9", "class": "agent-face"});
    faceText.textContent = MOOD_EMOJI[agent.mood] || "😐";
    g.appendChild(faceText);
    // 工作状态指示器
    if (agent.current_task) {
      g.appendChild(el("circle", {cx: 12, cy: -12, r: 4, fill: "#FFB74D", stroke: "white", "stroke-width": 1.5, "class": "task-indicator"}));
    }

    // 点击事件
    g.addEventListener("click", function(e) {
      e.stopPropagation();
      if (window.AppV2 && window.AppV2.onAgentClick) window.AppV2.onAgentClick(agent);
    });

    svg.appendChild(g);
    agentTokens[agent.id] = {element: g, pos: pos, mood: agent.mood, task: agent.current_task || ""};
  }

  function updateTokenVisual(g, agent) {
    var aura = g.querySelector(".agent-aura");
    var body = g.querySelector(".agent-body");
    var face = g.querySelector(".agent-face");
    var moodColor = MOOD_COLORS[agent.mood] || "#FFB74D";
    if (aura) aura.setAttribute("fill", moodColor);
    if (body) body.setAttribute("fill", AGENT_COLORS[agent.id] || "#888");
    if (face) face.textContent = MOOD_EMOJI[agent.mood] || "😐";
    var ind = g.querySelector(".task-indicator");
    if (agent.current_task && !ind) {
      g.appendChild(el("circle", {cx: 12, cy: -12, r: 4, fill: "#FFB74D", stroke: "white", "stroke-width": 1.5, "class": "task-indicator"}));
    } else if (!agent.current_task && ind) {
      g.removeChild(ind);
    }
  }

  // ===== 更新 Agent 位置（持久 token + 平滑移动 + 动作反馈）=====
  function updateAgentPositions(agents) {
    var newIds = {};
    agents.forEach(function(a) { newIds[a.id] = true; });
    // 清理已离场的 token
    for (var id in agentTokens) {
      if (!newIds[id] && agentTokens[id] && agentTokens[id].element && agentTokens[id].element.parentNode) {
        agentTokens[id].element.parentNode.removeChild(agentTokens[id].element);
        delete agentTokens[id];
      }
    }
    // 更新/新建 token（不再全量重建，移动由 CSS transition 平滑过渡）
    agents.forEach(function(a) {
      var tok = agentTokens[a.id];
      var pos = agentPos(a);
      if (tok && tok.element) {
        if (tok.pos && (tok.pos.x !== pos.x || tok.pos.y !== pos.y)) {
          tok.element.style.transform = "translate(" + pos.x + "px, " + pos.y + "px)";
        }
        tok.pos = pos;
        // 任务变化 → 动作反馈动画（工作/调查等）
        var newTask = a.current_task || "";
        if (newTask !== tok.task) {
          tok.element.classList.remove("agent-acting");
          void tok.element.getBoundingClientRect();
          tok.element.classList.add("agent-acting");
          tok.task = newTask;
        }
        updateTokenVisual(tok.element, a);
      } else {
        drawAgent(a);
      }
    });
  }

  // ===== 天气系统 =====
  function setWeather(weather) {
    currentWeather = weather;
    var existing = document.getElementById("weather-overlay");
    if (existing) existing.remove();
    if (!weather || weather === "clear") return;

    var g = el("g", {id: "weather-overlay"});
    
    if (weather === "rainy") {
      for (var i = 0; i < 80; i++) {
        var rx = Math.random() * 1000;
        var ry = Math.random() * 550;
        var rain = el("line", {
          x1: rx, y1: ry, x2: rx - 3, y2: ry + 18,
          stroke: "#64B5F6", "stroke-width": 1.5, opacity: 0.35,
          className: "raindrop"
        });
        rain.style.animationDuration = (0.3 + Math.random() * 0.4) + "s";
        rain.style.animationDelay = (Math.random() * 0.5) + "s";
        g.appendChild(rain);
      }
    } else if (weather === "snowy") {
      for (var i = 0; i < 50; i++) {
        var sx = Math.random() * 1000;
        var sy = Math.random() * 550;
        var snow = el("circle", {
          cx: sx, cy: sy, r: 2 + Math.random() * 3,
          fill: "white", opacity: 0.5 + Math.random() * 0.3,
          className: "snowflake"
        });
        snow.style.animationDuration = (2 + Math.random() * 3) + "s";
        snow.style.animationDelay = (Math.random() * 2) + "s";
        g.appendChild(snow);
      }
    } else if (weather === "cloudy") {
      for (var i = 0; i < 6; i++) {
        var cx = 80 + i * 180;
        var cy = 30 + Math.random() * 30;
        var cloud = el("g", {className: "cloud-drift"});
        cloud.appendChild(el("ellipse", {cx: cx, cy: cy, rx: 70 + Math.random() * 30, ry: 22 + Math.random() * 10, fill: "#B0BEC5", opacity: 0.35}));
        cloud.appendChild(el("ellipse", {cx: cx + 30, cy: cy - 8, rx: 50, ry: 18, fill: "#CFD8DC", opacity: 0.3}));
        cloud.appendChild(el("ellipse", {cx: cx - 25, cy: cy + 5, rx: 45, ry: 15, fill: "#ECEFF1", opacity: 0.25}));
        g.appendChild(cloud);
      }
    } else if (weather === "windy") {
      for (var i = 0; i < 12; i++) {
        var wy = 40 + i * 45;
        var wind = el("path", {
          d: "M" + (50 + Math.random() * 80) + "," + wy + " Q" + (200 + Math.random() * 100) + "," + (wy - 15) + " " + (400 + Math.random() * 100) + "," + (wy + 10) + " Q" + (550 + Math.random() * 100) + "," + (wy - 5) + " " + (700 + Math.random() * 80) + "," + wy,
          fill: "none", stroke: "rgba(255,255,255,0.2)", "stroke-width": 1.5,
          className: "wind-line"
        });
        wind.style.animationDuration = (1.5 + Math.random()) + "s";
        wind.style.animationDelay = (Math.random() * 0.8) + "s";
        g.appendChild(wind);
      }
    }
    
    svg.appendChild(g);
  }

  // ===== 时间设置 =====
  function setHour(hour) {
    currentHour = hour;
    var stops = svg.querySelectorAll("#skyGradient stop");
    if (stops.length < 2) return;
    
    var colors;
    if (hour >= 17 || hour < 5) {
      colors = ["#1A237E", "#283593"];
    } else if (hour >= 5 && hour < 8) {
      colors = ["#F4A460", "#FFE4B5"];
    } else if (hour >= 8 && hour < 14) {
      colors = ["#87CEEB", "#E0F7FA"];
    } else {
      colors = ["#FF8A65", "#FFB74D"];
    }

    stops[0].setAttribute("stop-color", colors[0]);
    stops[1].setAttribute("stop-color", colors[1]);

    // 夜晚时添加月亮
    var celestial = document.getElementById("celestial-body");
    if (hour >= 15 || hour < 6) {
      if (!celestial) {
        celestial = el("circle", {id: "celestial-body", r: 18, fill: "#E8EAF6", opacity: 0.9});
        svg.insertBefore(celestial, svg.firstChild);
      }
      celestial.setAttribute("cx", 700 - ((hour >= 15 ? hour - 15 : hour + 5) / 12) * 500);
      celestial.setAttribute("cy", 50);
      celestial.style.display = "block";
    } else {
      if (celestial) celestial.style.display = "none";
    }

    // 更新昼夜色调
    var tint = document.getElementById("daynight-tint");
    if (tint) {
      var tintColor = "transparent";
      var tintOpacity = 0;
      if (hour >= 17 || hour < 5) {
        tintColor = "#1A237E";
        tintOpacity = hour >= 17 ? Math.min(0.25, (hour - 17) * 0.06) : Math.min(0.25, (6 - hour) * 0.05);
      } else if (hour >= 5 && hour < 8) {
        tintColor = "#FF8A65";
        tintOpacity = 0.06;
      } else if (hour >= 13 && hour < 17) {
        tintColor = "#FF6B35";
        tintOpacity = ((hour - 13) / 4) * 0.1;
      }
      tint.setAttribute("fill", tintColor);
      tint.setAttribute("opacity", tintOpacity);
    }
  }

  // ===== 公开 API =====
  return {
    init: function(svgElement) {
      svg = svgElement;
      svg.innerHTML = "";
      drawBackground();
      drawPaths();
      drawSceneAnimations();
      Object.keys(LOCATIONS).forEach(function(id) { drawLocation(id); });
      agentTokens = {};
    },
    update: function(agents, weather, hour) {
      if (!svg) return;
      updateAgentPositions(agents);
      if (weather) setWeather(weather);
      if (hour !== undefined) setHour(hour);
    },
    setWeather: function(w) { if (svg) setWeather(w); },
    setHour: function(h) { if (svg) setHour(h); },
    getLocations: function() { return LOCATIONS; }
  };
})();
