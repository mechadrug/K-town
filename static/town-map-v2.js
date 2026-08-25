// K-town v2.0 — SVG 地图渲染器 v2.1
// 手绘水彩风格小镇地图 + 动画系统
window.TownMapV2 = (function() {
  "use strict";
  
  var SVG_NS = "http://www.w3.org/2000/svg";
  var svg = null;
  var agentTokens = {};
  var stableSeed = 17;
  var lastWeather = null;
  var lastRoofStage = null;
  var lastWeatherLocation = null;
  var currentRoof = null;
  var currentRoofStage = null;

  // 分层界面：一次只显示一个地点（舞台居中放大 + 等级标注）
  var currentLoc = "square";
  var LOCATION_STAGE = {x: 600, y: 400};
  var locStageGroup = null;

  // 地点配置（像素画风，更大画布 1200x720）
  var LOCATIONS = {
    square: {
      x: 600, y: 280, name: "广场", icon: "🏛", variant: "tower",
      width: 180, height: 140, color: "#D7CCC8", roofColor: "#8D6E63",
      desc: "小镇中心的公共集会场所，每天早上有集市"
    },
    workshop: {
      x: 220, y: 210, name: "工坊", icon: "🔨", variant: "workshop",
      width: 150, height: 120, color: "#FFCCBC", roofColor: "#BF360C",
      desc: "制作工具和加工材料的场所，炉火日夜不熄"
    },
    wilderness: {
      x: 970, y: 500, name: "荒野", icon: "🌲", variant: "wilderness",
      width: 210, height: 160, color: "#A5D6A7", roofColor: "#2E7D32",
      desc: "采集资源和探索未知的区域，蕴藏着秘密"
    },
    school: {
      x: 250, y: 540, name: "学校", icon: "📚", variant: "school",
      width: 140, height: 110, color: "#C5CAE9", roofColor: "#283593",
      desc: "教学育人和治病救人的场所，知识的灯塔"
    },
    mine: {
      x: 970, y: 190, name: "矿洞", icon: "⛏", variant: "mine",
      width: 150, height: 120, color: "#B0BEC5", roofColor: "#37474F",
      desc: "采集矿石的地下洞穴，深处据说有稀有矿物"
    }
  };


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
      fill: "none", stroke: "#4A90D9", "stroke-width": 16, opacity: 0.25, 
    }));
    riverG.appendChild(el("path", {
      d: "M0,452 C150,432 250,462 400,442 C550,422 700,452 850,432 C920,422 1000,442 1000,442",
      fill: "none", stroke: "#6BB3F0", "stroke-width": 6, opacity: 0.35
    }));
    svg.appendChild(riverG);
  }

  // ===== 道路绘制（art-direction §3.1：连接 5 地点的手绘土路）=====
  function drawRoads() {
    var g = el("g", {id: "roads"});
    // 地点坐标（与 LOCATIONS 一致）
    var pts = {
      square: {x: 600, y: 280},
      workshop: {x: 220, y: 210},
      wilderness: {x: 970, y: 500},
      school: {x: 250, y: 540},
      mine: {x: 970, y: 190},
    };
    var links = [
      ["square", "workshop"], ["square", "wilderness"],
      ["square", "school"], ["square", "mine"],
      ["workshop", "school"], ["mine", "wilderness"],
    ];
    links.forEach(function(pair) {
      var a = pts[pair[0]], b = pts[pair[1]];
      // 手绘曲线：用二次贝塞尔 + 中点偏移制造自然弯曲
      // Geometry must not change when a WebSocket state packet arrives.
      var linkSeed = pair[0].length * 13 + pair[1].length * 7 + stableSeed;
      var mx = (a.x + b.x) / 2 + ((linkSeed % 40) - 20);
      var my = (a.y + b.y) / 2 + (((linkSeed * 3) % 40) - 20);
      var d = "M" + a.x + "," + (a.y + 60) + " Q" + mx + "," + my + " " + b.x + "," + (b.y + 60);
      // 底层宽边（土路轮廓）
      g.appendChild(el("path", {d: d, fill: "none", stroke: "#D7CCC8", "stroke-width": 20, "stroke-linecap": "round", opacity: 0.7}));
      // 中间沙色（走出来的路）
      g.appendChild(el("path", {d: d, fill: "none", stroke: "#EFEBE9", "stroke-width": 10, "stroke-linecap": "round", opacity: 0.85}));
      // 中央虚线（脚印花纹）
      g.appendChild(el("path", {d: d, fill: "none", stroke: "#BCAAA4", "stroke-width": 3, "stroke-linecap": "round", "stroke-dasharray": "14 18", opacity: 0.6}));
    });
    svg.appendChild(g);
  }

  // ===== 场景动画元素 =====

  // ===== 像素点缀（岩石/草丛/花）=====
  function drawScenery() {
    var g = el("g", {id: "scenery"});
    var S = 10;
    var deco = [
      {x: 430, y: 200, w: 3, c: "#9E9E9E"}, {x: 780, y: 580, w: 4, c: "#BDBDBD"},
      {x: 640, y: 540, w: 3, c: "#A1887F"}, {x: 350, y: 440, w: 3, c: "#9E9E9E"},
      {x: 520, y: 440, w: 2, c: "#81C784"}, {x: 700, y: 390, w: 2, c: "#66BB6A"},
      {x: 300, y: 360, w: 2, c: "#A5D6A7"}, {x: 560, y: 170, w: 2, c: "#81C784"},
      {x: 470, y: 520, w: 1, c: "#F48FB1"}, {x: 730, y: 470, w: 1, c: "#FFD54F"},
      {x: 620, y: 630, w: 1, c: "#CE93D8"}, {x: 380, y: 280, w: 1, c: "#FFD54F"}
    ];
    deco.forEach(function(d) { pxRect(g, d.x, d.y, d.w * S, d.w * S, d.c); });
    svg.appendChild(g);
  }

  // ===== 像素画建筑（crisp 方块像素风）=====
  function pxRect(g, x, y, w, h, fill, stroke, cls) {
      var attrs = {
      x: Math.round(x), y: Math.round(y),
      width: Math.round(w), height: Math.round(h),
      fill: fill, stroke: stroke || "none", "stroke-width": 1,
      "shape-rendering": "crispEdges"
      };
      if (cls) {
        attrs["class"] = cls;
        // 保存原始填充，便于夜间/日间切换
        attrs["data-orig-fill"] = fill;
      }
      g.appendChild(el("rect", attrs));
    }

  function drawPixelBuilding(g, loc, S) {
    S = S || 10; // 像素格（舞台分层界面用 16 放大）
    var w = loc.width, h = loc.height;
    var cx = loc.x, bx = cx - w / 2, by = loc.y - h / 2;
    var wallC = loc.color, roofC = loc.roofColor, trim = "rgba(0,0,0,0.2)";
    var variant = loc.variant || "house";

    if (variant === "mine") {
      // 矿洞：岩壁 + 拱形洞口 + 木支撑
      pxRect(g, bx, by + S * 2, w, h - S * 2, "#546E7A", trim);
      var aw = S * 4, ah = S * 6;
      pxRect(g, cx - aw / 2, by + S * 4, aw, ah, "#263238");
      pxRect(g, cx - aw / 2 + S, by + S * 3, aw - S * 2, S * 2, "#263238");
      pxRect(g, cx - aw / 2 + S * 1.5, by + S * 2, aw - S * 3, S, "#263238");
      pxRect(g, cx - aw / 2 - S / 2, by + S * 3, S, ah - S, "#5D4037");
      pxRect(g, cx + aw / 2 - S / 2, by + S * 3, S, ah - S, "#5D4037");
      pxRect(g, bx + S, by + S * 3, S, S, "#B0BEC5");
      pxRect(g, bx + w - S * 2, by + S * 4, S, S, "#FFD54F");
      pxRect(g, bx + S * 2, by + h - S * 3, S, S, "#90A4AE");
      return;
    }

    if (variant === "wilderness") {
      // 荒野：像素树 + 灌木
      var spots = [{x: cx - w / 4, y: by + h / 2}, {x: cx + w / 5, y: by + h / 3}];
      spots.forEach(function(tp) {
        pxRect(g, tp.x - S / 2, tp.y - S * 2, S, S * 2, "#5D4037");
        pxRect(g, tp.x - S * 1.5, tp.y - S * 4, S * 3, S * 2, "#2E7D32");
        pxRect(g, tp.x - S, tp.y - S * 5, S * 2, S * 2, "#388E3C");
        pxRect(g, tp.x - S * 0.5, tp.y - S * 6, S, S * 2, "#4CAF50");
      });
      pxRect(g, bx + S, by + h - S * 2, S * 2, S, "#66BB6A");
      pxRect(g, bx + w - S * 3, by + h - S * 3, S * 2, S * 2, "#81C784");
      return;
    }

    // 通用像素建筑（墙 + 金字塔屋顶 + 像素窗 + 门）
    pxRect(g, bx, by, w, h, wallC, trim);
    var roofRows = Math.max(2, Math.floor(w / (S * 2)));
    for (var i = 0; i < roofRows; i++) {
      var rowW = S * 2 * (i + 1);
      pxRect(g, cx - rowW / 2, by - (roofRows - i) * S, rowW, S, roofC, trim);
    }
    pxRect(g, bx, by - S, w, S, "rgba(255,255,255,0.12)");

    var winCols = Math.max(1, Math.floor(w / (S * 4)));
    for (var c = 0; c < winCols; c++) {
      for (var rr = 0; rr < 2; rr++) {
        var wx = bx + S * 2 + c * ((w - S * 4) / Math.max(1, winCols - 1));
        var wy = by + S * 2 + rr * S * 3;
        if (wy + S > by + h - S * 2) continue;
        pxRect(g, wx, wy, S, S, "rgba(255,255,255,0.35)", trim, 'pixel-window');
        pxRect(g, wx + S, wy, S, S, "rgba(255,255,255,0.25)", trim, 'pixel-window');
        pxRect(g, wx, wy + S, S, S, "rgba(255,255,255,0.25)", trim, 'pixel-window');
        pxRect(g, wx + S, wy + S, S, S, "rgba(255,255,255,0.2)", trim, 'pixel-window');
      }
    }
    pxRect(g, cx - S, by + h - S * 2, S * 2, S * 2, trim);

    if (variant === "tower") {
      // 广场钟楼
      var tw = S * 2;
      pxRect(g, cx - tw / 2, by - roofRows * S - S * 3, tw, S * 3, wallC, trim);
      pxRect(g, cx - tw, by - roofRows * S - S * 4, tw * 2, S, roofC, trim);
      pxRect(g, cx - S, by - roofRows * S - S * 5, tw, S, roofC, trim);
    } else if (variant === "workshop") {
      // 工坊烟囱
      pxRect(g, bx + w - S * 2, by - S * 5, S, S * 4, "#6D4C41", trim);
      pxRect(g, bx + w - S * 2.5, by - S * 5, S * 2, S, "#4E342E");
    } else if (variant === "school") {
      // 学校小钟
      pxRect(g, cx - S / 2, by - roofRows * S - S * 2, S, S * 2, wallC, trim);
      pxRect(g, cx - S, by - roofRows * S - S * 3, S * 2, S, "#FFD54F");
    }

    if (variant === "workshop") {
      drawWorkshopRoofState(g, loc, S);
    }
  }

  // 屋顶阶段必须在晴天也可读：漏雨、临时遮雨、正式修好不只靠数字或雨滴区分。
  function drawWorkshopRoofState(g, loc, S) {
    var stage = loc.roofStage == null ? 0 : loc.roofStage;
    var w = loc.width, h = loc.height, cx = loc.x;
    var bx = cx - w / 2, by = loc.y - h / 2;
    var roofRows = Math.max(2, Math.floor(w / (S * 2)));
    var roofTop = by - roofRows * S;
    var trim = "rgba(0,0,0,0.22)";
    if (stage === 0) {
      g.appendChild(el("path", {
        d: "M" + (bx + S) + "," + (by - S) + " L" + cx + "," + roofTop + " L" + (bx + w - S) + "," + (by - S),
        fill: "none", stroke: "#4E342E", "stroke-width": Math.max(3, S / 3), opacity: 0.8,
        "class": "roof-damage"
      }));
      pxRect(g, bx + S * 2, by - S * 2, S * 2, S, "#5D4037", trim, "roof-damage-patch");
    } else if (stage === 1) {
      g.appendChild(el("path", {
        d: "M" + (bx + S) + "," + (by - S) + " L" + cx + "," + roofTop + " L" + (cx + S * 2) + "," + roofTop + " L" + (bx + w * 0.55) + "," + (by - S),
        fill: "#90A4AE", stroke: "#546E7A", "stroke-width": 2, opacity: 0.82,
        "class": "roof-tarp"
      }));
      g.appendChild(el("line", {x1: bx + S * 2, y1: by - S * 2, x2: bx + w * 0.55, y2: by - S, stroke: "#455A64", "stroke-width": 2, opacity: 0.8, "class": "roof-tarp-rope"}));
    } else {
      g.appendChild(el("path", {
        d: "M" + (bx + S) + "," + (by - S) + " L" + cx + "," + roofTop + " L" + (bx + w - S) + "," + (by - S),
        fill: "none", stroke: "#D7CCC8", "stroke-width": Math.max(2, S / 4), opacity: 0.9,
        "class": "roof-repaired-edge"
      }));
      pxRect(g, bx + S * 2, by - S * 2, S, S, "#FFD54F", trim, "roof-repair-nail");
      pxRect(g, bx + w - S * 3, by - S * 2, S, S, "#FFD54F", trim, "roof-repair-nail");
    }
  }

  // ===== 地点绘制 =====

  // ===== Agent 绘制（持久 token + 平滑动画）=====
  function agentPos(agent) {
    // 分层界面：在场居民簇拥在舞台大建筑周围
    var loc = LOCATIONS[agent.location];
    if (!loc) return {x: LOCATION_STAGE.x, y: LOCATION_STAGE.y};
    var hash = 0;
    for (var i = 0; i < agent.id.length; i++) {
      hash = ((hash << 5) - hash) + agent.id.charCodeAt(i);
      hash = hash & hash;
    }
    var offsetX = ((hash % 100) / 100 - 0.5) * (loc.width * 1.7 * 0.6);
    var offsetY = (((hash >> 8) % 100) / 100 - 0.5) * (loc.height * 1.7 * 0.3);
    return {x: LOCATION_STAGE.x + offsetX, y: LOCATION_STAGE.y + offsetY + 30};
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

    // 心情光环（脉动，radial 柔和）
    g.appendChild(el("circle", {cx: 0, cy: 0, r: 16, fill: moodColor, opacity: 0.18, "class": "agent-aura"}));

    // 像素小人（art-direction §3.2：8×8 级像素小人替代圆点）
    var P = 2.2; // 像素块大小
    var bodyGroup = el("g", {"class": "agent-body"});
    // 头（肤色）
    bodyGroup.appendChild(el("rect", {x: -P * 2, y: -P * 7, width: P * 4, height: P * 4, rx: P, fill: "#FFCCBC", stroke: "white", "stroke-width": 1, "class": "pixel-head"}));
    // 身体（职业色）
    bodyGroup.appendChild(el("rect", {x: -P * 2.5, y: -P * 3, width: P * 5, height: P * 6, rx: P, fill: color, stroke: "white", "stroke-width": 1, "class": "pixel-body"}));
    // 腿（2px）
    bodyGroup.appendChild(el("rect", {x: -P * 1.5, y: P * 3, width: P, height: P * 2.5, fill: "#5D4037", "class": "pixel-leg-l"}));
    bodyGroup.appendChild(el("rect", {x: P * 0.5, y: P * 3, width: P, height: P * 2.5, fill: "#5D4037", "class": "pixel-leg-r"}));
    g.appendChild(bodyGroup);

    // 心情表情（头上悬浮 emoji）
    var faceText = el("text", {x: 0, y: -P * 9, "text-anchor": "middle", "font-size": "12", "class": "agent-face"});
    faceText.textContent = MOOD_EMOJI[agent.mood] || "😐";
    g.appendChild(faceText);

    // 工作状态指示器
    if (agent.current_task) {
      g.appendChild(el("circle", {cx: 14, cy: -14, r: 4, fill: "#FFB74D", stroke: "white", "stroke-width": 1.5, "class": "task-indicator"}));
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
    var body = g.querySelector(".pixel-body");
    var face = g.querySelector(".agent-face");
    var moodColor = MOOD_COLORS[agent.mood] || "#FFB74D";
    if (aura) aura.setAttribute("fill", moodColor);
    if (body) body.setAttribute("fill", AGENT_COLORS[agent.id] || "#888");
    if (face) face.textContent = MOOD_EMOJI[agent.mood] || "😐";
    var ind = g.querySelector(".task-indicator");
    if (agent.current_task && !ind) {
      g.appendChild(el("circle", {cx: 14, cy: -14, r: 4, fill: "#FFB74D", stroke: "white", "stroke-width": 1.5, "class": "task-indicator"}));
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
  function setWeather(weather, roof) {
    var roofStage = roof && roof.stage != null ? roof.stage : null;
    if (weather === lastWeather && roofStage === lastRoofStage && currentLoc === lastWeatherLocation) return;
    lastWeather = weather;
    lastRoofStage = roofStage;
    lastWeatherLocation = currentLoc;
    var existing = document.getElementById("weather-overlay");
    if (existing) existing.remove();
    var existingDrips = document.getElementById("roof-drips");
    if (existingDrips) existingDrips.remove();
    if (!weather || weather === "clear") return;

    var g = el("g", {id: "weather-overlay"});
    
    if (weather === "rainy") {
      for (var i = 0; i < 80; i++) {
        var rx = Math.random() * 1000;
        var ry = Math.random() * 550;
        var rain = el("line", {
          x1: rx, y1: ry, x2: rx - 3, y2: ry + 18,
          stroke: "#64B5F6", "stroke-width": 1.5, opacity: 0.35,
          "class": "raindrop"
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
          "class": "snowflake"
        });
        snow.style.animationDuration = (2 + Math.random() * 3) + "s";
        snow.style.animationDelay = (Math.random() * 2) + "s";
        g.appendChild(snow);
      }
    } else if (weather === "cloudy") {
      for (var i = 0; i < 6; i++) {
        var cx = 80 + i * 180;
        var cy = 30 + Math.random() * 30;
        var cloud = el("g", {"class": "cloud-drift"});
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
          "class": "wind-line"
        });
        wind.style.animationDuration = (1.5 + Math.random()) + "s";
        wind.style.animationDelay = (Math.random() * 0.8) + "s";
        g.appendChild(wind);
      }
    }
    if (weather === "rainy" && roof && roof.stage < 2 && currentLoc === "workshop") {
      var drip = el("g", {id: "roof-drips", "class": "roof-drips"});
      for (var d = 0; d < (roof.stage === 1 ? 2 : 4); d++) {
        drip.appendChild(el("line", {x1: LOCATION_STAGE.x - 38 + d * 25, y1: LOCATION_STAGE.y - 45, x2: LOCATION_STAGE.x - 38 + d * 25, y2: LOCATION_STAGE.y + 10, stroke: "#64B5F6", "stroke-width": 2, "class": "roof-drip"}));
      }
      g.appendChild(drip);
    }
    
    svg.appendChild(g);
  }

  // ===== 时间设置 =====
  function setHour(hour) {
    
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

    // 切换像素窗光（夜间为暖黄色）
    try {
      var windows = svg.querySelectorAll('.pixel-window');
      var isNight = (hour >= 17 || hour < 5);
      windows.forEach(function(w) {
        var orig = w.getAttribute('data-orig-fill') || w.getAttribute('fill') || 'white';
        if (isNight) {
          w.setAttribute('fill', '#FFD54F');
          w.setAttribute('opacity', '0.95');
        } else {
          w.setAttribute('fill', orig);
        }
      });
  } catch (e) { /* ignore in older browsers */ }
  }

  // ===== 分层界面：渲染当前地点舞台 =====
  function setLocation(locId) {
    var loc = LOCATIONS[locId] || LOCATIONS.square;
    if (locStageGroup && locStageGroup.parentNode) svg.removeChild(locStageGroup);
    currentLoc = locId in LOCATIONS ? locId : "square";
    locStageGroup = el("g", {id: "loc-stage"});

    // 大号像素建筑（居中于舞台，1.7 倍）
    var sc = {
      x: LOCATION_STAGE.x, y: LOCATION_STAGE.y,
      width: loc.width * 1.7, height: loc.height * 1.7,
      color: loc.color, roofColor: loc.roofColor, variant: loc.variant,
      roofStage: currentRoof && currentRoof.stage
    };
    drawPixelBuilding(locStageGroup, sc, 16);

    // 地点专属动态点缀
    if (loc.variant === "workshop") {
      for (var i = 0; i < 3; i++) {
        var sm = el("circle", {
          cx: LOCATION_STAGE.x + sc.width / 2 - 26, cy: LOCATION_STAGE.y - sc.height / 2 - 55 - i * 20,
          r: 5 + i * 3, fill: "rgba(180,180,180,0.3)", "class": "smoke-puff"
        });
        sm.style.animationDelay = (i * 0.8) + "s";
        locStageGroup.appendChild(sm);
      }
    } else if (loc.variant === "mine") {
      for (var i = 0; i < 5; i++) {
        var sp = el("circle", {
          cx: LOCATION_STAGE.x - 30 + i * 15, cy: LOCATION_STAGE.y + 20 + (i % 3) * 10,
          r: 2 + (i % 2), fill: "#FFD54F", "class": "sparkle"
        });
        sp.style.animationDelay = (i * 0.6) + "s";
        locStageGroup.appendChild(sp);
      }
    }

    svg.appendChild(locStageGroup);
    agentTokens = {}; // 让在场居民按新地点重排
  }

  // ===== 公开 API =====
  return {
    init: function(svgElement) {
      svg = svgElement;
      svg.innerHTML = "";
      drawBackground();
      drawRoads();
      drawScenery();
      setLocation("square");
      agentTokens = {};
    },
    update: function(agents, weather, hour, roof) {
      if (!svg) return;
      var nextRoofStage = roof && roof.stage != null ? roof.stage : null;
      currentRoof = roof || null;
      if (nextRoofStage !== currentRoofStage && currentLoc === "workshop") {
        currentRoofStage = nextRoofStage;
        setLocation(currentLoc);
      } else {
        currentRoofStage = nextRoofStage;
      }
      // 分层界面：只显示当前地点的在场居民
      var here = (agents || []).filter(function(a) { return a.location === currentLoc; });
      updateAgentPositions(here);
      if (weather) setWeather(weather, roof);
      if (hour !== undefined) setHour(hour);
    },
    setLocation: function(locId) { if (svg) setLocation(locId); },
  };
})();
