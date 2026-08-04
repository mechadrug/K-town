// K-town v2.0 — 主应用逻辑 v2.2 (Phase 3 + Phase 4)
(function() {
  'use strict';

  // ===== 状态 =====
  var currentState = null;
  var ws = null;
  var currentDialogueAgent = null;
  var soundEnabled = true;
  var activeTab = 'events';
  var ICONS = window.KTownIcons || {};
  var lastMapLoc = null;
  var knowledgeSubmittedToday = false;
  var lastDay = null;

  // 防抖：防止连点导致 AP 误扣 / 动作堆积（每次动作间隔 ≥300ms）
  var lastActionAt = 0;
  var ACTION_COOLDOWN = 300;
  function canSendAction() {
    var now = Date.now();
    if (now - lastActionAt < ACTION_COOLDOWN) return false;
    lastActionAt = now;
    return true;
  }

  // 知识主题 → 中文（知识视图不再显示英文键）
  var SUBJECT_CN = {
    weather: '天气', resource: '资源', social: '社交', craft: '手艺',
    rumor: '传闻', investigate: '调查', skill: '技能', observation: '观察',
    knowledge: '知识', investigation: '调查'
  };

  // ===== 初始化 =====
  document.addEventListener('DOMContentLoaded', function() {
    TownMapV2.init(document.getElementById('map-canvas'));
    connectWebSocket();
    setupEventListeners();
    // 初始即加载任务与知识数据（不依赖切换 Tab）
    loadQuests();
    loadKnowledge();
    // 首次进入显示新手引导
    var guided = false;
    try { guided = localStorage.getItem('ktown_guided') === '1'; } catch (e) {}
    if (!guided) showGuide();
  });

  // ===== WebSocket =====
  function connectWebSocket() {
    var protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(protocol + '//' + location.host + '/ws');

    ws.onopen = function() {
      console.log('WebSocket connected');
      showToast('🏘 已连接到K-town边境小镇', 'info');
      playSound('connect');
    };

    ws.onmessage = function(e) {
      try {
        var msg = JSON.parse(e.data);
        handleMessage(msg);
      } catch (err) {
        console.error('WS message error:', err);
      }
    };

    ws.onclose = function() {
      console.log('WebSocket disconnected, retrying...');
      setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = function(err) {
      console.error('WS error:', err);
    };
  }

  function handleMessage(msg) {
    switch (msg.type) {
      case 'state':
        currentState = msg.data;
        updateUI(msg.data);
        break;
      case 'day_summary':
        addEvent({
          type: 'day_summary',
          icon: '📰',
          text: '新的一天开始了！',
          category: 'info'
        });
        showToast('📰 新的一天开始了！', 'info');
        playSound('dayStart');
        break;
      case 'event':
        var evt = msg.data;
        var category = getEventCategory(evt.type);
        addEvent({
          type: evt.type || 'info',
          icon: getEventIcon(evt.type),
          text: evt.action || evt.type || '有事情发生了',
          category: category
        });
        if (category === 'positive') playSound('eventGood');
        else if (category === 'negative') playSound('eventBad');
        else playSound('event');
        break;
      case 'player_action_result':
        if (msg.data) {
          var isErr = msg.data.status === 'error';
          showToast(msg.data.result, isErr ? 'error' : 'success');
          if (isErr) playSound('error');
          else playSound('success');
        }
        break;
    }
  }

  // ===== UI 更新 =====
  function updateUI(data) {
    var day = Math.floor(data.tick / 20) + 1;
    var hour = data.tick % 20;
    var player = data.player || {};

    // 新的一天：重置每日领悟（知识按钮恢复）
    if (lastDay !== null && day !== lastDay) {
      knowledgeSubmittedToday = false;
      updateKnowledgeBtn();
    }
    lastDay = day;

    setText('time-text', '第' + day + '天 · ' + getTimeOfDay(hour));
    setText('time-icon', getTimeIcon(hour));
    setText('weather-text', getWeatherName(data.weather));
    setText('weather-icon', getWeatherIcon(data.weather));

    setText('stat-gold', player.gold != null ? player.gold : 0);
    setText('stat-energy', Math.round(player.energy != null ? player.energy : 100));
    setText('stat-ap', player.action_points != null ? player.action_points : 12);
    // AP 上限 12；有十三时夜间行动力时显示 🌙（独立池）
    var nightAp = player.night_ap || 0;
    setText('stat-ap-max', 12 + (nightAp > 0 ? '🌙' + nightAp : ''));

    // 十三时：夜间行动力 > 0 时高亮提示（可夜行探索）
    var apStatEl = document.querySelector('.topbar-stat.ap');
    if (apStatEl) {
      if ((player.night_ap || 0) > 0) apStatEl.classList.add('night-ap');
      else apStatEl.classList.remove('night-ap');
    }

    // 分层界面：玩家位置变化时先切换舞台，再更新居民（避免旧地点人群残留）
    if (player.location && player.location !== lastMapLoc) {
      lastMapLoc = player.location;
      TownMapV2.setLocation(player.location);
      var locLevel = (data.location_levels && data.location_levels[player.location]) || 1;
      setText('map-loc-icon', getLocationIcon(player.location));
      setText('map-loc-name', getLocationCn(player.location));
      setText('map-loc-level', '修缮等级 ' + locLevel);
    }
    TownMapV2.update(data.agents || [], data.weather, hour);
    setTimeTheme(hour);
    var hereCount = (data.agents || []).filter(function(a) { return a.location === player.location; }).length;
    setText('map-loc-count', '在场 ' + hereCount + ' 人');

    // 更新知识列表
    if (data.knowledge && data.knowledge.claims) {
      updateKnowledgeList(data.knowledge.claims);
    }

    // 渲染每日摘要
    if (data.narrative_summary) {
      renderNarrativeSummary(data.narrative_summary);
    }

    // 小镇脉搏（第一屏信息）
    updatePulse(data);
  }

  // ===== 小镇脉搏 =====
  function updatePulse(data) {
    var locsEl = document.getElementById('pulse-locations');
    var moodsEl = document.getElementById('pulse-moods');
    var knEl = document.getElementById('pulse-knowledge');
    var meEl = document.getElementById('pulse-me');

    var counts = {};
    var moods = { happy: 0, neutral: 0, low: 0 };
    (data.agents || []).forEach(function(a) {
      counts[a.location] = (counts[a.location] || 0) + 1;
      if (a.mood === 'happy') moods.happy++;
      else if (a.mood === 'neutral') moods.neutral++;
      else moods.low++;
    });

    if (locsEl) {
      var locs = ['square', 'workshop', 'wilderness', 'school', 'mine'];
      var levels = data.location_levels || {};
      var html = '<div class="pulse-row">';
      locs.forEach(function(l) {
        var lvl = levels[l] || 1;
        html += '<span class="pulse-loc" title="' + getLocationCn(l) + '（修缮至 ' + lvl + ' 级）"><span class="pulse-loc-icon">' + getLocationIcon(l) + '</span>' + lvl + '级·' + (counts[l] || 0) + '</span>';
      });
      html += '</div>';
      locsEl.innerHTML = html;
    }

    if (moodsEl) {
      moodsEl.innerHTML =
        '<span class="mood-dot happy"></span> 开心 ' + moods.happy +
        '<span class="mood-dot neutral"></span> 平静 ' + moods.neutral +
        '<span class="mood-dot low"></span> 低落 ' + moods.low;
    }

    if (knEl) {
      var claims = (data.knowledge_claims || []).slice().sort(function(a, b) {
        return (b.created_at || 0) - (a.created_at || 0);
      }).slice(0, 2);
      if (claims.length > 0) {
        knEl.innerHTML = claims.map(function(c) { return '💬 “' + esc(c.claim) + '”'; }).join('<br>');
      } else {
        knEl.innerHTML = '<span style="color:var(--text-muted)">尚无流传</span>';
      }
    }

    if (meEl) {
      var p = data.player || {};
      meEl.textContent = '🧳 你在 ' + getLocationCn(p.location);
    }
  }

  // ===== 时段主题 =====
  function setTimeTheme(hour) {
    var body = document.body;
    body.classList.remove('theme-morning', 'theme-dusk', 'theme-night');
    if (hour >= 5 && hour < 9) body.classList.add('theme-morning');
    else if (hour >= 13 && hour < 17) body.classList.add('theme-dusk');
    else if (hour >= 17 || hour < 5) body.classList.add('theme-night');
  }

  // ===== Tab 切换 =====
  function switchTab(tabName) {
    activeTab = tabName;
    
    // 更新按钮状态
    var btns = document.querySelectorAll('.tab-btn');
    btns.forEach(function(btn) {
      if (btn.dataset.tab === tabName) btn.classList.add('active');
      else btn.classList.remove('active');
    });

    // 更新面板显示：显式驱动 style.display（内联 display:none 会覆盖 .active class）
    var panels = document.querySelectorAll('.tab-panel');
    panels.forEach(function(panel) {
      var isActive = panel.id === 'tab-' + tabName;
      if (isActive) {
        panel.classList.add('active');
        panel.style.display = 'block';
      } else {
        panel.classList.remove('active');
        panel.style.display = 'none';
      }
    });

    // 加载对应数据
    if (tabName === 'quests') loadQuests();
    if (tabName === 'knowledge') loadKnowledge();

    playSound('click');
  }

  // ===== 事件系统 =====
  function addEvent(evt) {
    var list = document.getElementById('event-list');
    if (!list) return;
    
    var placeholder = list.querySelector('.placeholder-text');
    if (placeholder) placeholder.remove();

    var item = document.createElement('div');
    item.className = 'event-item ' + (evt.category || 'info');
    
    var time = currentState ? ('第' + (Math.floor(currentState.tick / 20) + 1) + '天 ' + getTimeOfDay(currentState.tick % 20)) : '';
    
    item.innerHTML = 
      '<span class="event-icon">' + (evt.icon || '📋') + '</span>' +
      '<div class="event-content">' +
        '<div class="event-text">' + esc(evt.text) + '</div>' +
        (time ? '<div class="event-time">' + time + '</div>' : '') +
      '</div>';

    list.insertBefore(item, list.firstChild);

    while (list.children.length > 8) {
      list.removeChild(list.lastChild);
    }
  }

  // ===== 任务系统 =====
  function loadQuests() {
    fetch('/api/quests').then(function(r) { return r.json(); }).then(function(data) {
      var container = document.getElementById('quest-list');
      if (!container) return;
      container.innerHTML = '';

      var allQuests = [].concat(data.active_quests || [], data.completed_quests || []);
      if (allQuests.length === 0) {
        container.innerHTML = '<div class="placeholder-text">暂无任务</div>';
        return;
      }

      allQuests.forEach(function(q) {
        var item = document.createElement('div');
        item.className = 'quest-item ' + (q.status === 'completed' ? 'completed' : '');
        var pct = Math.min(100, Math.round((q.progress / Math.max(1, q.target)) * 100));
        item.innerHTML = 
          '<div class="quest-title">' + (q.status === 'completed' ? '✅ ' : '🎯 ') + (q.title || '') + '</div>' +
          '<div class="quest-desc">' + (q.description || '') + '</div>' +
          '<div class="quest-progress-bar"><div class="quest-progress-fill" style="width:' + pct + '%"></div></div>' +
          '<div class="quest-meta">' +
            '<span>' + (q.progress || 0) + '/' + (q.target || 1) + '</span>' +
            '<span class="quest-reward">🏆 ' + (q.reward_text || (q.reward_gold ? q.reward_gold + '金币' : '')) + '</span>' +
          '</div>';
        container.appendChild(item);
      });
    }).catch(function() {
      var container = document.getElementById('quest-list');
      if (container) container.innerHTML = '<div class="placeholder-text">加载失败</div>';
    });
  }

  // ===== 知识系统 =====
  function loadKnowledge() {
    fetch('/api/knowledge').then(function(r) { return r.json(); }).then(function(data) {
      updateKnowledgeList(data.claims || []);
    }).catch(function() {});
  }

  function updateKnowledgeList(claims) {
    var container = document.getElementById('knowledge-list');
    if (!container) return;
    container.innerHTML = '';
    claims = claims || [];
    if (claims.length === 0) {
      container.innerHTML = '<div class="placeholder-text">暂无知识记录</div>';
      return;
    }

    // 按主题聚类成"知识流"：同主题下看它如何产生→传播→固化/冲突
    var groups = {};
    claims.forEach(function(c) {
      var key = SUBJECT_CN[c.subject] || c.subject || '其他';
      (groups[key] = groups[key] || []).push(c);
    });

    var keys = Object.keys(groups).sort(function(a, b) { return groups[b].length - groups[a].length; });
    keys.slice(0, 8).forEach(function(key) {
      var list = groups[key].slice().sort(function(a, b) { return (a.created_at || 0) - (b.created_at || 0); });
      var holders = {};
      list.forEach(function(c) { if (c.created_by) holders[c.created_by] = true; });
      var holderCount = Object.keys(holders).length;
      var maxConf = Math.max.apply(null, list.map(function(c) { return c.confidence || 0; }));
      var hasConflict = list.some(function(c) { return (c.contradicted_by || []).length > 0; });
      var isSolidified = list.some(function(c) { return c.solidified; });
      var conf = Math.round(maxConf * 100);

      var item = document.createElement('div');
      item.className = 'knowledge-flow-item';
      var html = '<div class="knowledge-flow-head">📚 ' + key +
        '<span class="knowledge-flow-count">' + list.length + ' 条 · ' + holderCount + ' 人持有</span></div>';
      html += '<div class="knowledge-flow-body">';
      list.slice(0, 3).forEach(function(c) {
        var who = (c.source === 'conversation' || c.source === 'rumor') ? '传到' : '来自';
        html += '<div class="knowledge-flow-line">💬 “' + esc(c.claim) + '”' +
          '<span class="knowledge-flow-meta">' + who + ' ' + getAgentName(c.created_by || '') + ' · ' + Math.round((c.confidence || 0) * 100) + '%</span></div>';
      });
      if (list.length > 3) html += '<div class="knowledge-flow-more">… 另有 ' + (list.length - 3) + ' 条</div>';
      html += '</div>';
      html += '<div class="confidence-bar"><div class="confidence-fill" style="width:' + conf + '%"></div></div>';
      html += '<div class="knowledge-flow-badges">' +
        (isSolidified ? '<span class="kf-badge solid">✓ 已固化</span>' : '') +
        (hasConflict ? '<span class="kf-badge conflict">⚡ 有冲突</span>' : '') +
        (holderCount > 1 ? '<span class="kf-badge spread">↗ 已传播</span>' : '') +
        '</div>';
      item.innerHTML = html;
      container.appendChild(item);
    });
  }

  // ===== Agent 档案 =====
  function onAgentClick(agent) {
    openProfile(agent.id);
  }

  function openProfile(agentId) {
    var agent = null;
    (currentState.agents || []).forEach(function(a) {
      if (a.id === agentId) agent = a;
    });
    if (!agent) return;

    currentDialogueAgent = agent;

    var avatar = document.getElementById('prof-avatar');
    var name = document.getElementById('prof-name');
    var role = document.getElementById('prof-role');
    var mood = document.getElementById('prof-mood');
    var stats = document.getElementById('prof-stats');
    var relations = document.getElementById('prof-relations');

    if (avatar) avatar.textContent = getAgentEmoji(agent.id);
    if (name) name.textContent = agent.name || agent.id;
    if (role) role.textContent = getRoleCn(agent.role) || '居民';
    if (mood) mood.textContent = '心情：' + getMoodText(agent.mood);

    if (stats) {
      stats.innerHTML =
        '<div class="profile-stat-row"><span>🔍 正在</span><span>' + (agent.current_task || '在' + getLocationCn(agent.location) + '四处走走') + '</span></div>' +
        '<div class="profile-stat-row"><span>⚡ 体力</span><div class="mini-bar"><div class="mini-bar-fill energy" style="width:' + (agent.energy || 0) + '%"></div></div><span>' + Math.round(agent.energy || 0) + '</span></div>' +
        '<div class="profile-stat-row"><span>💰 金币</span><span style="color:var(--warm-500);font-weight:600">' + (agent.gold || 0) + '</span></div>' +
        '<div class="profile-stat-row"><span>📍 位置</span><span>' + getLocationCn(agent.location) + '</span></div>';
    }

    if (relations) {
      var ties = agent.social_ties || {};
      var sorted = Object.entries(ties).sort(function(a, b) { return b[1] - a[1]; }).slice(0, 5);
      var relHtml = '<div style="font-size:0.8em;color:var(--text-secondary);margin-bottom:6px;font-weight:600">关系最好的居民：</div>';
      if (sorted.length > 0) {
        relHtml += '<div style="display:flex;flex-direction:column;gap:4px">';
        sorted.forEach(function(t) {
          var otherName = getAgentName(t[0]);
          var val = Math.round(t[1]);
          var color = val > 0 ? 'var(--positive)' : 'var(--negative)';
          relHtml += '<div style="display:flex;justify-content:space-between;font-size:0.78em"><span>' + otherName + '</span><span style="color:' + color + '">' + (val > 0 ? '+' : '') + val + '</span></div>';
        });
        relHtml += '</div>';
      } else {
        relHtml += '<div style="font-size:0.78em;color:var(--text-muted)">暂无关系记录</div>';
      }
      relations.innerHTML = relHtml;
    }

    // 当前目标
    var goalsEl = document.getElementById('prof-goals');
    if (goalsEl) {
      var goals = agent.goals || [];
      goalsEl.style.display = 'block';
      if (goals.length > 0) {
        var goalsHtml = '<div style="font-size:0.8em;color:var(--text-secondary);margin-bottom:6px;font-weight:600">🎯 当前目标</div>';
        goalsHtml += '<div style="display:flex;flex-direction:column;gap:3px">';
        goals.forEach(function(g) {
          var done = g.completed ? '✅' : '○';
          goalsHtml += '<div style="font-size:0.78em;display:flex;align-items:center;gap:4px"><span style="color:var(--warm-500)">' + done + '</span><span>' + (g.description || g) + '</span></div>';
        });
        goalsHtml += '</div>';
        goalsEl.innerHTML = goalsHtml;
      } else {
        goalsEl.innerHTML = '<div style="font-size:0.78em;color:var(--text-muted)">暂无明确目标</div>';
      }
    }

    // 最近日记
    var diaryEl = document.getElementById('prof-diary');
    if (diaryEl) {
      var diary = agent.diary || [];
      diaryEl.style.display = 'block';
      if (diary.length > 0) {
        var diaryHtml = '<div style="font-size:0.8em;color:var(--text-secondary);margin-bottom:6px;font-weight:600">📖 最近日记</div>';
        diaryHtml += '<div style="display:flex;flex-direction:column;gap:4px">';
        diary.slice(-5).forEach(function(entry) {
          diaryHtml += '<div style="font-size:0.78em;padding:4px 6px;background:rgba(0,0,0,0.04);border-radius:4px"><span>' + entry + '</span></div>';
        });
        diaryHtml += '</div>';
        diaryEl.innerHTML = diaryHtml;
      } else {
        diaryEl.innerHTML = '<div style="font-size:0.78em;color:var(--text-muted)">暂无日记记录</div>';
      }
    }

    var overlay = document.getElementById('profile-overlay');
    if (overlay) overlay.style.display = 'flex';
    playSound('click');
  }

  function closeProfile() {
    var overlay = document.getElementById('profile-overlay');
    if (overlay) overlay.style.display = 'none';
    currentDialogueAgent = null;
  }

  // ===== 新手引导 =====
  function showGuide() {
    var overlay = document.getElementById('guide-overlay');
    if (overlay) overlay.style.display = 'flex';
  }

  function closeGuide() {
    var overlay = document.getElementById('guide-overlay');
    if (overlay) overlay.style.display = 'none';
    try { localStorage.setItem('ktown_guided', '1'); } catch (e) {}
  }

  // ===== 对话系统 =====
  function startDialogueFromProfile() {
    if (currentDialogueAgent) {
      openDialogue(currentDialogueAgent);
      closeProfile();
    }
  }

  function openDialogue(agent) {
    currentDialogueAgent = agent;
    var overlay = document.getElementById('dialogue-overlay');
    var avatar = document.getElementById('dlg-avatar');
    var name = document.getElementById('dlg-name');
    var relation = document.getElementById('dlg-relation');
    var messages = document.getElementById('dlg-messages');
    var options = document.getElementById('dlg-options');

    if (!overlay) return;

    if (avatar) avatar.textContent = getAgentEmoji(agent.id);
    if (name) name.textContent = agent.name || agent.id;
    if (relation) relation.textContent = getRelationText(agent);

    if (messages) {
      messages.innerHTML = '<div class="dlg-message dlg-message-agent"><span>你好，旅行者。我是' + (agent.name || '居民') + '。</span></div>';
    }

    if (options) options.innerHTML = '<div class="placeholder-text">加载对话选项...</div>';
    overlay.style.display = 'flex';
    playSound('talk');

    // 从后端获取真实对话选项（按好感度解锁）
    fetch('/api/dialogue/options/' + encodeURIComponent(agent.id))
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var optsEl = document.getElementById('dlg-options');
        if (!optsEl) return;
        // 关系等级 + 心情（对话语境可见）
        var relEl = document.getElementById('dlg-relation');
        if (relEl) {
          var relParts = [data.level || '陌生人'];
          if (data.mood) relParts.push('心情' + getMoodText(data.mood));
          relEl.textContent = relParts.join(' · ');
        }
        var list = data.options || [];
        optsEl.innerHTML = '';
        if (list.length === 0) {
          optsEl.innerHTML = '<div class="placeholder-text">对方似乎不想说话...</div>';
          return;
        }
        list.forEach(function(opt) {
          var btn = document.createElement('button');
          btn.className = 'dialogue-option';
          btn.innerHTML = '<span class="opt-icon">💬</span><span>' + (opt.text || opt.id || '对话') + '</span>';
          btn.title = opt.desc || '';
          btn.onclick = function() { executeDialogue(agent, opt.id, opt.text); };
          optsEl.appendChild(btn);
        });
      })
      .catch(function() {
        var optsEl = document.getElementById('dlg-options');
        if (optsEl) optsEl.innerHTML = '<div class="placeholder-text">对话选项加载失败</div>';
      });
  }

  function executeDialogue(agent, optionId, optionText) {
    var messages = document.getElementById('dlg-messages');
    if (!messages) return;

    var playerMsg = document.createElement('div');
    playerMsg.className = 'dlg-message dlg-message-player';
    playerMsg.innerHTML = '<span>' + (optionText || '你好') + '</span>';
    messages.appendChild(playerMsg);
    messages.scrollTop = messages.scrollHeight;

    // 调用后端真实对话执行接口（消耗AP、真实改变好感度与知识）
    fetch('/api/dialogue/execute/' + encodeURIComponent(agent.id), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ option_id: optionId })
    })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var respEl = document.createElement('div');
        respEl.className = 'dlg-message dlg-message-agent';
        var text = data.message || '……';
        if (data.success === false) showToast(text, 'error');
        respEl.innerHTML = '<span>' + esc(agent.name || '居民') + '：' + esc(text) + '</span>';
        messages.appendChild(respEl);
        messages.scrollTop = messages.scrollHeight;
        if (data.knowledge_gained) showToast('📚 ' + data.knowledge_gained, 'info');
        // 对话消耗 AP：即时更新顶栏显示（避免与实际不符）
        if (data.ap_remaining !== undefined) {
          setText('stat-ap', data.ap_remaining);
        }
      })
      .catch(function() {
        var respEl = document.createElement('div');
        respEl.className = 'dlg-message dlg-message-agent';
        respEl.innerHTML = '<span>' + (agent.name || '居民') + '：……</span>';
        messages.appendChild(respEl);
        messages.scrollTop = messages.scrollHeight;
      });
  }

  function closeDialogue() {
    var overlay = document.getElementById('dialogue-overlay');
    if (overlay) overlay.style.display = 'none';
    currentDialogueAgent = null;
  }

  // ===== Toast 通知 =====
  function showToast(message, type) {
    var container = document.getElementById('toast-container');
    if (!container) return;

    var toast = document.createElement('div');
    toast.className = 'toast ' + (type || 'info');
    
    var iconMap = { success: '✅', error: '❌', info: 'ℹ️' };
    toast.innerHTML = '<span class="toast-icon">' + (iconMap[type] || 'ℹ️') + '</span><span>' + message + '</span>';

    container.appendChild(toast);

    setTimeout(function() {
      toast.classList.add('toast-out');
      setTimeout(function() {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
      }, 300);
    }, 3000);
  }

  // ===== 音效系统 =====
  function playSound(type) {
    if (!soundEnabled || !window.KTownSound) return;
    var soundFn = window.KTownSound[type];
    if (typeof soundFn === 'function') soundFn();
  }

  function toggleSound() {
    soundEnabled = !soundEnabled;
    var btn = document.getElementById('soundBtn');
    if (btn) btn.textContent = soundEnabled ? '🔊' : '🔇';
    if (soundEnabled) playSound('click');
    showToast(soundEnabled ? '音效已开启' : '音效已关闭', 'info');
  }

  // ===== 玩家操作 =====
  function movePlayer(dest) {
    if (!canSendAction()) return;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      showToast('连接已断开，请刷新页面', 'error');
      return;
    }
    ws.send(JSON.stringify({
      type: 'player_action',
      action: { type: 'move', target: dest }
    }));
    playSound('move');
  }

  function doWork(type) {
    if (!canSendAction()) return;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      showToast('连接已断开', 'error');
      return;
    }
    ws.send(JSON.stringify({
      type: 'player_action',
      action: { type: 'work', work_type: type }
    }));
    playSound('work');
  }

  function doRest() {
    if (!canSendAction()) return;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      showToast('连接已断开', 'error');
      return;
    }
    ws.send(JSON.stringify({
      type: 'player_action',
      action: { type: 'rest' }
    }));
    playSound('rest');
  }

  function doInvestigate() {
    if (!canSendAction()) return;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      showToast('连接已断开', 'error');
      return;
    }
    ws.send(JSON.stringify({
      type: 'player_action',
      action: { type: 'investigate' }
    }));
    playSound('investigate');
  }

  function addKnowledge() {
    if (knowledgeSubmittedToday) {
      showToast('今日的思考已经交出去了，明日再悟吧', 'info');
      return;
    }
    if (!canSendAction()) return;
    var claim = prompt('写下你此刻的想法（每日一次，可能触及遗迹的真相）：');
    if (!claim || !claim.trim()) return;

    if (!ws || ws.readyState !== WebSocket.OPEN) {
      showToast('连接已断开', 'error');
      return;
    }
    knowledgeSubmittedToday = true;
    updateKnowledgeBtn();
    ws.send(JSON.stringify({
      type: 'player_action',
      action: { type: 'add_claim', claim: claim.trim() }
    }));
    playSound('addKnowledge');
  }

  function updateKnowledgeBtn() {
    var btn = document.getElementById('addKnowledgeBtn');
    if (!btn) return;
    btn.disabled = knowledgeSubmittedToday;
    btn.classList.toggle('disabled', knowledgeSubmittedToday);
    btn.title = knowledgeSubmittedToday ? '今日已提交，明日再悟' : '每日一次：写下你的想法。若触及遗迹真相，会有领悟';
  }

  function resetSimulation() {
    if (!confirm('确定要重置小镇模拟吗？所有进度将丢失。')) return;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      showToast('连接已断开', 'error');
      return;
    }
    ws.send(JSON.stringify({
      type: 'player_action',
      action: { type: 'reset' }
    }));
  }

  // ===== 键盘快捷键 =====
  function setupEventListeners() {
    document.addEventListener('keydown', function(e) {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      switch(e.key) {
        case '1': movePlayer('square'); break;
        case '2': movePlayer('workshop'); break;
        case '3': movePlayer('wilderness'); break;
        case '4': movePlayer('school'); break;
        case '5': movePlayer('mine'); break;
        case 'w': case 'W': doWork('work'); break;
        case 'i': case 'I': doInvestigate(); break;
        case 'r': case 'R': doRest(); break;
        case 'k': case 'K': addKnowledge(); break;
        case 'Escape': closeDialogue(); closeProfile(); break;
      }
    });

    var dlgOverlay = document.getElementById('dialogue-overlay');
    if (dlgOverlay) {
      dlgOverlay.addEventListener('click', function(e) {
        if (e.target === dlgOverlay) closeDialogue();
      });
    }
    var profOverlay = document.getElementById('profile-overlay');
    if (profOverlay) {
      profOverlay.addEventListener('click', function(e) {
        if (e.target === profOverlay) closeProfile();
      });
    }
  }


  // ===== 每日摘要渲染 =====
  function renderNarrativeSummary(summary) {
    var list = document.getElementById('event-list');
    if (!list) return;

    var item = document.createElement('div');
    item.className = 'event-item info narrative-summary';
    item.style.borderLeftColor = 'var(--warm-500)';
    item.style.background = 'linear-gradient(90deg, rgba(255,167,38,0.06), transparent)';
    item.innerHTML =
      '<span class="event-icon">📰</span>' +
      '<div class="event-content">' +
        '<div class="event-text" style="font-weight:600;color:var(--warm-500)">每日摘要</div>' +
        '<div class="event-text" style="margin-top:4px">' + esc(summary.title) + '</div>' +
        (summary.body ? '<div class="event-text" style="font-size:0.85em;color:var(--text-muted);margin-top:2px">' + esc(summary.body) + '</div>' : '') +
      '</div>';
    list.insertBefore(item, list.firstChild);
  }

  // ===== 工具函数 =====
  function setText(id, text) {
    var el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  // HTML 转义：innerHTML 拼接服务端/LLM 字符串前必须经过（防 XSS 与乱码）
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function getTimeOfDay(hour) {
    if (hour >= 5 && hour < 9) return '早晨';
    if (hour >= 9 && hour < 14) return '白天';
    if (hour >= 14 && hour < 17) return '傍晚';
    return '夜晚';
  }

  function getTimeIcon(hour) {
    if (hour >= 5 && hour < 9) return ICONS.time.morning;
    if (hour >= 9 && hour < 14) return ICONS.time.day;
    if (hour >= 14 && hour < 17) return ICONS.time.dusk;
    return ICONS.time.night;
  }

  function getWeatherName(w) {
    return { clear: '晴朗', cloudy: '多云', rainy: '下雨', snowy: '下雪', windy: '大风' }[w] || '晴朗';
  }

  function getWeatherIcon(w) {
    return ICONS.weather[w] || ICONS.weather.clear;
  }

  function getLocationCn(loc) {
    return { square: '广场', workshop: '工坊', wilderness: '荒野', school: '学校', mine: '矿洞' }[loc] || loc;
  }

  function getLocationIcon(loc) {
    return (ICONS.location || {})[loc] || '📍';
  }

  function getAgentColor(id) {
    return {
      agent_elder: '#8D6E63', agent_blacksmith: '#FF7043', agent_carpenter: '#7E57C2',
      agent_forager: '#66BB6A', agent_scout: '#42A5F5', agent_merchant: '#FFA726',
      agent_teacher: '#5C6BC0', agent_farmer: '#9CCC65', agent_storyteller: '#EC407A',
      agent_healer: '#26C6DA', agent_miner: '#78909C', agent_player: '#FF6B35'
    }[id] || '#888';
  }

  function getAgentEmoji(id) {
    return ICONS.agent[id] || ICONS.ui.resident;
  }

  function getAgentName(id) {
    return {
      agent_elder: '梅奶奶', agent_blacksmith: '铁匠托林', agent_carpenter: '木匠莉娜',
      agent_forager: '采集者费尔南', agent_scout: '侦察兵罗文', agent_merchant: '商人维斯珀',
      agent_teacher: '教师奥尔登', agent_farmer: '农民克莱', agent_storyteller: '讲故事的人艾莉丝',
      agent_healer: '医生希尔达', agent_miner: '矿工戈尔', agent_player: '旅行者'
    }[id] || id;
  }

  function getRoleCn(role) {
    return {
      elder: '长者', blacksmith: '铁匠', carpenter: '木匠',
      forager: '采集者', scout: '侦察兵', merchant: '商人',
      teacher: '教师', farmer: '农民', storyteller: '讲故事的人',
      healer: '医生', miner: '矿工', player: '旅行者'
    }[role] || role;
  }

  function getEventIcon(type) {
    return ICONS.event[type] || '📋';
  }

  function getEventCategory(type) {
    var positive = ['resource_found', 'item_crafted', 'festival', 'agent_goal_complete'];
    var negative = ['disaster', 'knowledge_conflict'];
    var social = ['social_encounter', 'rumor_spread'];
    var player = ['player_action'];
    if (positive.indexOf(type) >= 0) return 'positive';
    if (negative.indexOf(type) >= 0) return 'negative';
    if (social.indexOf(type) >= 0) return 'social';
    if (player.indexOf(type) >= 0) return 'info';
    return 'info';
  }

  function getMoodText(mood) {
    return { happy: '开心', neutral: '平静', sad: '难过', angry: '生气', anxious: '焦虑' }[mood] || '平静';
  }

  function getRelationText(agent) {
    var ties = agent.social_ties || {};
    var val = ties['agent_player'] || 0;
    if (val > 50) return '挚友 · ' + Math.round(val);
    if (val > 30) return '朋友 · ' + Math.round(val);
    if (val > 15) return '熟悉 · ' + Math.round(val);
    if (val > 5) return '认识 · ' + Math.round(val);
    if (val < -10) return '敌对 · ' + Math.round(val);
    return '陌生人';
  }

  // ===== 公开 API =====
  window.AppV2 = {
    onAgentClick: onAgentClick
  };
  
  // 全局接口
  window.movePlayer = movePlayer;
  window.doWork = doWork;
  window.doRest = doRest;
  window.doInvestigate = doInvestigate;
  window.addKnowledge = addKnowledge;
  window.resetSimulation = resetSimulation;
  window.toggleSound = toggleSound;
  window.showGuide = showGuide;
  window.closeGuide = closeGuide;
  window.openProfile = openProfile;
  window.closeProfile = closeProfile;
  window.closeDialogue = closeDialogue;
  window.startDialogueFromProfile = startDialogueFromProfile;
  window.switchTab = switchTab;

  // 5秒轮询（WebSocket 备用）
  setInterval(function() {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      fetch('/api/state').then(function(r) { return r.json(); }).then(function(data) {
        currentState = data;
        updateUI(data);
      }).catch(function() {});
    }
  }, 5000);

})();
