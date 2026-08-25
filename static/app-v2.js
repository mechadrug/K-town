// K-town v2.0 — 主应用逻辑 v2.2 (Phase 3 + Phase 4)
(function() {
  'use strict';

  // ===== 状态 =====
  var currentState = null;
  var ws = null;
  var currentDialogueAgent = null;
  var soundEnabled = true;
  var ICONS = window.KTownIcons || {};
  var lastMapLoc = null;
  var knowledgeSubmittedToday = false;
  var lastDay = null;
  var threadsCollapsed = false;

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
    loadRequests();
    // 首次进入显示新手引导
    var guided = false;
    try { guided = localStorage.getItem('ktown_guided') === '1'; } catch (e) {}
    if (!guided) showGuide();
    // 初始化粒子层（夜间萤火 / 风中落叶）
    try { initParticleLayer(); } catch (e) { console.warn('initParticleLayer failed', e); }
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
        currentState = window.KTownContract.normalizeState(msg.data);
        updateUI(currentState);
        break;
      case 'day_summary':
        renderNarrativeSummary(msg.data || {});
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
          var actionResult = window.KTownContract.normalizeActionResult(msg.data);
          var isErr = !actionResult.accepted;
          showToast(actionResult.result || (isErr ? '行动未完成' : '行动完成'), isErr ? 'error' : 'success');
          if (isErr) playSound('error');
          else {
            playSound('success');
            addEvent({
              type: 'player_action',
              icon: '✨',
              text: actionResult.result || '行动完成',
              category: 'player-related',
              storyBeats: actionResult.story_beats || [],
              nextObservation: actionResult.next_observation || ''
            });
          }
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
    renderCampaign(data.campaign || null);

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
    TownMapV2.update(data.agents || [], data.weather, hour, data.workshop_roof);
    setTimeTheme(hour);
    try { updateParticles(hour, data.weather); } catch (e) { console.warn('updateParticles failed', e); }
    var hereCount = (data.agents || []).filter(function(a) { return a.location === player.location; }).length;
    setText('map-loc-count', '在场 ' + hereCount + ' 人');

    // 更新知识列表
    if (data.knowledge && data.knowledge.claims) {
      updateKnowledgeList(data.knowledge.claims);
    }

    renderTodayThreads(data.today_threads || []);
    renderContextActions(data);
    renderCrisisBanner(data.crises || []);

    // 小镇脉搏（第一屏信息）
    updatePulse(data);

    // 请求列表（随状态推送保持最新：完成/截止变化即时可见）
    renderRequests(data.requests);
  }

  function toggleThreads() {
    threadsCollapsed = !threadsCollapsed;
    var list = document.getElementById('thread-list');
    var button = document.getElementById('thread-toggle');
    if (list) list.hidden = threadsCollapsed;
    if (button) {
      button.textContent = threadsCollapsed ? '展开' : '收起';
      button.setAttribute('aria-expanded', String(!threadsCollapsed));
    }
  }

  function renderTodayThreads(threads) {
    var list = document.getElementById('thread-list');
    if (!list) return;
    list.innerHTML = '';
    (threads || []).forEach(function(thread, index) {
      var card = document.createElement('article');
      card.className = 'thread-card thread-' + (thread.kind || 'info');
      var icon = index === 0 ? '🙋' : (index === 1 ? '🌧️' : '🧭');
      var visibleItems = (thread.items || []).slice(0, 3);
      var items = visibleItems.map(function(item, itemIndex) {
        var button = item.action ? '<button class="thread-link" data-app-action="follow-thread" data-thread-item="' + itemIndex + '">' + esc(item.action.label || '去看看') + ' →</button>' : '';
        return '<div class="thread-item"><div><strong>' + esc(item.title || item.id || '') + '</strong><span>' + esc(item.detail || '') + '</span></div>' + button + '</div>';
      }).join('');
      card.innerHTML = '<div class="thread-card-head"><span class="thread-icon">' + icon + '</span><div><h3>' + esc(thread.title) + '</h3><p>' + esc(thread.detail) + '</p></div></div>' + (items || '<div class="thread-empty">今天还没有新消息。</div>');
      list.appendChild(card);
    });
  }

  // Campaign rendering is an isolated view boundary.  New chapters only need
  // to satisfy the state payload contract; the main app does not know their
  // story text or effect vocabulary.
  function renderCampaign(campaign) {
    if (window.KTownCampaignView && typeof window.KTownCampaignView.render === 'function') {
      window.KTownCampaignView.render(campaign, document.getElementById('campaign-card'));
    }
  }

  function followThread(action) {
    if (!action) return;
    if (typeof action === 'string') {
      try { action = JSON.parse(action); } catch (e) { action = {kind: 'move', target: action}; }
    }
    if (action.kind === 'request') {
      switchTab('requests');
      var request = document.getElementById('request-' + action.request_id);
      if (request && request.scrollIntoView) request.scrollIntoView({behavior: 'smooth', block: 'center'});
    } else if (action.kind === 'crisis') {
      interveneCrisis(action.crisis_id, 'help');
    } else if (action.kind === 'campaign') {
      var campaignCard = document.getElementById('campaign-card');
      if (campaignCard && campaignCard.scrollIntoView) campaignCard.scrollIntoView({behavior: 'smooth', block: 'center'});
    } else if (action.target) {
      movePlayer(action.target);
    }
  }

  function renderContextActions(data) {
    var player = data.player || {};
    var location = player.location || 'square';
    var list = document.getElementById('context-action-list');
    var note = document.getElementById('context-actions-note');
    if (!list) return;
    var here = (data.agents || []).filter(function(agent) { return agent.location === location && agent.id !== 'agent_player'; });
    if (note) note.textContent = here.length ? here.map(function(agent) { return agent.name; }).slice(0, 2).join('、') + (here.length > 2 ? '等人在场' : '在场') : '暂时没有居民在场';
    var actions = [];
    var locationName = getLocationCn(location);
    actions.push({icon: '👀', label: location === 'workshop' ? '查看屋顶和炉台' : '观察' + locationName + '的动静', cost: '0 AP · 不推进', actionType: 'observe'});
    if (location === 'workshop') actions.push({icon: '🔨', label: '在工坊帮忙', cost: '1 AP · 1 小时', actionType: 'work'});
    else if (location === 'wilderness') actions.push({icon: '🌲', label: '在荒野找材料', cost: '1 AP · 1 小时', actionType: 'work'});
    else actions.push({icon: '🧰', label: '处理眼前的活', cost: '1 AP · 1 小时', actionType: 'work'});
    actions.push({icon: '🔍', label: '调查并留下线索', cost: '2 AP · 2 小时', actionType: 'investigate'});
    if (here.length) actions.push({icon: '💬', label: '和在场居民聊聊', cost: '1 AP · 1 小时', actionType: 'talk', agentId: here[0].id});
    list.innerHTML = '';
    actions.slice(0, 4).forEach(function(item) {
      var button = document.createElement('button');
      button.className = 'context-action';
      button.innerHTML = '<span class="context-action-icon">' + item.icon + '</span><span class="context-action-copy"><strong>' + esc(item.label) + '</strong><small>' + esc(item.cost) + '</small></span><span class="context-action-arrow">→</span>';
      button.dataset.appAction = 'context-action';
      button.dataset.actionType = item.actionType;
      if (item.target) button.dataset.target = item.target;
      if (item.agentId) button.dataset.agentId = item.agentId;
      list.appendChild(button);
    });
  }

  function renderCrisisBanner(crises) {
    var banner = document.getElementById('crisis-banner');
    if (!banner) return;
    if (!crises || !crises.length) { banner.style.display = 'none'; return; }
    var crisis = crises[0];
    banner.style.display = 'block';
    banner.innerHTML = '<strong>⚠️ ' + esc(crisis.desc) + '</strong><span>进度 ' + Math.round(crisis.progress) + '/' + crisis.target + ' · 还剩 ' + crisis.days_remaining + ' 天</span><button data-app-action="intervene-crisis" data-crisis-id="' + esc(crisis.id) + '" data-crisis-action="help">今天帮忙（3 AP）</button>';
  }

  function interveneCrisis(id, action) {
    if (!canSendAction()) return;
    window.KTownApi.interveneCrisis(id, action).then(function(result) {
        showToast(result.result || '危机已更新', result.accepted ? 'success' : 'error');
        // 危机干预走 REST，不能等待 WebSocket 的下一条 state；
        // 立即拉取同源状态，保证 AP、横幅进度和今日三条线一起刷新。
        return window.KTownApi.getState().then(function(data) {
          currentState = data;
          updateUI(data);
        });
      }).catch(function() {
        showToast('危机状态同步失败，请刷新页面确认', 'error');
      });
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

  // ===== 粒子层 (fireflies / leaves) =====
  function initParticleLayer() {
    var pc = document.getElementById('particle-canvas');
    if (!pc) {
      pc = document.createElement('div');
      pc.id = 'particle-canvas';
      document.body.insertBefore(pc, document.body.firstChild);
    }
    pc.style.pointerEvents = 'none';
    pc.style.position = 'absolute';
    pc.style.top = '0';
    pc.style.left = '0';
    pc.style.width = '100%';
    pc.style.height = '100%';
    pc.style.overflow = 'hidden';
    pc.style.zIndex = '10';
  }

  function updateParticles(hour, weather) {
    var pc = document.getElementById('particle-canvas');
    if (!pc) return;
    var signature = String(hour) + ':' + String(weather || 'clear') + ':' + document.body.className;
    if (pc.dataset.signature === signature) return;
    pc.dataset.signature = signature;
    pc.innerHTML = '';
    var bodyClass = document.body.classList;
    // 夜晚萤火虫
    if (bodyClass.contains('theme-night')) {
      for (var i = 0; i < 12; i++) {
        var f = document.createElement('div');
        f.className = 'firefly';
        f.style.position = 'absolute';
        f.style.left = (Math.random() * 100) + '%';
        f.style.top = (Math.random() * 100) + '%';
        f.style.width = '6px';
        f.style.height = '6px';
        f.style.borderRadius = '50%';
        f.style.background = 'rgba(255,244,200,0.95)';
        f.style.zIndex = '11';
        pc.appendChild(f);
      }
    } else if (weather === 'windy') {
      // 风中落叶
      for (var j = 0; j < 6; j++) {
        var lp = document.createElement('div');
        lp.className = 'leaf-particle';
        lp.style.position = 'absolute';
        lp.style.left = (Math.random() * 100) + '%';
        lp.style.top = (-10 + Math.random() * 30) + '%';
        lp.style.width = '10px';
        lp.style.height = '10px';
        lp.style.background = 'rgba(180,130,80,0.95)';
        lp.style.zIndex = '11';
        pc.appendChild(lp);
      }
    }
  }

  // ===== Tab 切换 =====
  function switchTab(tabName) {
    
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
    if (tabName === 'requests') loadRequests();

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
        ((evt.storyBeats && evt.storyBeats.length) || evt.nextObservation ?
          '<div class="event-causal-beats">' +
          (evt.storyBeats || []).slice(0, 2).map(function(beat) { return '<div>↳ ' + esc(beat) + '</div>'; }).join('') +
          (evt.nextObservation ? '<div>明天看：' + esc(evt.nextObservation) + '</div>' : '') +
          '</div>' : '') +
      '</div>';

    list.insertBefore(item, list.firstChild);

    while (list.children.length > 8) {
      list.removeChild(list.lastChild);
    }
  }

  // ===== 请求系统（v5 纵切片）=====
  function loadRequests() {
    var requests = (currentState && currentState.requests) || [];
    renderRequests(requests);
    // 状态推送可能早于首次加载：保证 tab 打开时有数据
    if (!currentState) {
      window.KTownApi.getRequests().then(renderRequests).catch(function() {});
    }
  }

  function renderRequests(requests) {
    var container = document.getElementById('request-list');
    if (!container) return;
    container.innerHTML = '';
    if (!requests || requests.length === 0) {
      container.innerHTML = '<div class="placeholder-text">暂时没有居民请求</div>';
      return;
    }
    requests.forEach(function(q) {
      var item = document.createElement('div');
      item.className = 'quest-item ' + (q.status === 'completed' ? 'completed' : '');
      item.id = 'request-' + q.id;
      var meta = '';
      if (q.status === 'completed') {
        meta = '<div class="quest-meta"><span class="quest-reward">✅ 已完成（第' + (q.completed_day || '?') + '天）</span></div>';
      } else {
        var dayNow = currentState ? (Math.floor(currentState.tick / 20) + 1) : 1;
        var left = Math.max(0, q.deadline - dayNow);
        meta = '<div class="quest-meta"><span>截止：第' + q.deadline + '天（还剩' + left + '天）</span></div>';
      }
      var optsHtml = '';
      (q.options || []).forEach(function(o) {
        var disabled = q.status !== 'active' || (q.used_options || []).indexOf(o.id) >= 0;
        optsHtml += '<button class="request-option-btn" ' + (disabled ? 'disabled' : '') +
          ' data-app-action="respond-request" data-request-id="' + esc(q.id) + '" data-option-id="' + esc(o.id) + '" title="' +
          esc(o.requires_cn + ' · 消耗 ' + o.cost_ap + ' 行动力 / ' + o.cost_hours + ' 小时') + '">' +
          esc(o.label) + '<span class="request-cost">' + o.cost_ap + 'AP</span></button>';
      });
      item.innerHTML =
        '<div class="quest-title">' + (q.status === 'completed' ? '✅ ' : '🙋 ') + esc(q.requester_name || '') + ' · ' + esc(q.title) + '</div>' +
        '<div class="quest-desc">' + esc(q.situation) + '</div>' +
        '<div class="request-progress">准备度 ' + (q.progress || 0) + '/' + (q.max_progress || 1) + ' · ' + esc(q.location_name || getLocationCn(q.location)) + '</div>' +
        (q.status === 'active' ? '<div class="request-options">' + optsHtml + '</div>' : '') +
        meta;
      container.appendChild(item);
    });
  }

  function respondRequest(requestId, optionId) {
    if (!canSendAction()) return;
    sendPlayerAction({ type: 'request_respond', request_id: requestId, option: optionId }, '连接已断开，请刷新页面');
  }

  // ===== 任务系统 =====
  function loadQuests() {
    window.KTownApi.getQuests().then(function(data) {
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
          '<div class="quest-title">' + (q.status === 'completed' ? '✅ ' : '🎯 ') + esc(q.title || '') + '</div>' +
          '<div class="quest-desc">' + esc(q.description || '') + '</div>' +
          '<div class="quest-progress-bar"><div class="quest-progress-fill" style="width:' + pct + '%"></div></div>' +
          '<div class="quest-meta">' +
            '<span>' + (q.progress || 0) + '/' + (q.target || 1) + '</span>' +
            '<span class="quest-reward">🏆 ' + esc(q.reward_text || (q.reward_gold ? q.reward_gold + '金币' : '')) + '</span>' +
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
    window.KTownApi.getKnowledge().then(function(data) {
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
    var profile = agent.profile || {};
    if (mood) mood.textContent = '此刻感受：' + (profile.feeling || getMoodText(agent.mood));

    if (stats) {
      stats.innerHTML =
        '<div class="profile-story-row"><span class="profile-story-label">正在做什么</span><strong>' + esc(profile.current_task || agent.current_task || '在附近走走') + '</strong></div>' +
        '<div class="profile-story-row"><span class="profile-story-label">为什么</span><span>' + esc(profile.reason || '还没有新的原因记录。') + '</span></div>' +
        '<div class="profile-story-row"><span class="profile-story-label">行为倾向</span><span>' + esc(profile.tendency || '按自己的节奏推进。') + '</span></div>' +
        '<div class="profile-stat-row"><span>⚡ 体力</span><div class="mini-bar"><div class="mini-bar-fill energy" style="width:' + (agent.energy || 0) + '%"></div></div><span>' + Math.round(agent.energy || 0) + '</span></div>' +
        '<div class="profile-stat-row"><span>💰 金币</span><span style="color:var(--warm-500);font-weight:600">' + (agent.gold || 0) + '</span></div>' +
        '<div class="profile-stat-row"><span>📍 位置</span><span>' + getLocationCn(agent.location) + '</span></div>';
      var emotionDetail = profile.emotion_detail || {};
      stats.innerHTML += '<details class="profile-details"><summary>查看情绪与原因数值</summary><div class="profile-emotions">愉悦 ' + Math.round(emotionDetail.joy || 50) + ' · 焦虑 ' + Math.round(emotionDetail.anxiety || 50) + ' · 愤怒 ' + Math.round(emotionDetail.anger || 50) + ' · 悲伤 ' + Math.round(emotionDetail.sadness || 50) + '</div></details>';
    }

    var responseEl = document.querySelector('.profile-actions');
    if (responseEl) {
      var responseHtml = profile.responses && profile.responses.length ? '<div class="profile-response-label">你能回应</div>' + profile.responses.slice(0, 3).map(function(response) {
        var disabled = response.available_here ? '' : ' disabled';
        return '<button class="profile-response-btn"' + disabled + ' data-app-action="respond-request" data-request-id="' + esc(response.request_id) + '" data-option-id="' + esc(response.option_id) + '"><span>' + esc(response.label) + '</span><small>' + response.cost_ap + ' AP · ' + response.cost_hours + ' 小时' + (response.available_here ? '' : ' · 先移动') + '</small></button>';
      }).join('') : '';
      responseEl.innerHTML = responseHtml + '<button class="action-btn primary profile-dialogue-btn" data-app-action="start-dialogue">💬 对话</button>';
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
           goalsHtml += '<div style="font-size:0.78em;display:flex;align-items:center;gap:4px"><span style="color:var(--warm-500)">' + done + '</span><span>' + esc(g.description || g) + '</span></div>';
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
           diaryHtml += '<div style="font-size:0.78em;padding:4px 6px;background:rgba(0,0,0,0.04);border-radius:4px"><span>' + esc(entry) + '</span></div>';
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
      messages.innerHTML = '<div class="dlg-message dlg-message-agent"><span>你好，旅行者。我是' + esc(agent.name || '居民') + '。</span></div>';
    }

    if (options) options.innerHTML = '<div class="placeholder-text">加载对话选项...</div>';
    overlay.style.display = 'flex';
    playSound('talk');

    // 从后端获取真实对话选项（按好感度解锁）
    window.KTownApi.dialogueOptions(agent.id)
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
          btn.innerHTML = '<span class="opt-icon">💬</span><span>' + esc(opt.text || opt.id || '对话') + '</span>';
          btn.title = opt.desc || '';
          btn.dataset.appAction = 'dialogue-option';
          btn.dataset.agentId = agent.id;
          btn.dataset.optionId = opt.id;
          btn.dataset.optionText = opt.text || opt.id || '对话';
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
    playerMsg.innerHTML = '<span>' + esc(optionText || '你好') + '</span>';
    messages.appendChild(playerMsg);
    messages.scrollTop = messages.scrollHeight;

    // 调用后端真实对话执行接口（消耗AP、真实改变好感度与知识）
    window.KTownApi.executeDialogue(agent.id, optionId)
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
      toast.innerHTML = '<span class="toast-icon">' + (iconMap[type] || 'ℹ️') + '</span><span>' + esc(message) + '</span>';

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

  function sendPlayerAction(action, unavailableMessage) {
    try {
      window.KTownApi.sendPlayerAction(ws, action);
      return true;
    } catch (error) {
      showToast(unavailableMessage || '连接已断开，请刷新页面', 'error');
      return false;
    }
  }

  // ===== 玩家操作 =====
  function movePlayer(dest) {
    if (!canSendAction()) return;
    if (sendPlayerAction({ type: 'move', target: dest })) playSound('move');
  }

  function doWork(type) {
    if (!canSendAction()) return;
    if (sendPlayerAction({ type: 'work', work_type: type }, '连接已断开')) playSound('work');
  }

  function doRest() {
    if (!canSendAction()) return;
    if (sendPlayerAction({ type: 'rest' }, '连接已断开')) playSound('rest');
  }

  function doInvestigate() {
    if (!canSendAction()) return;
    if (sendPlayerAction({ type: 'investigate' }, '连接已断开')) playSound('investigate');
  }

  function doObserve() {
    if (!canSendAction()) return;
    sendPlayerAction({ type: 'observe' }, '连接已断开，请刷新页面');
  }

  function addKnowledge() {
    if (knowledgeSubmittedToday) {
      showToast('今日的思考已经交出去了，明日再悟吧', 'info');
      return;
    }
    if (!canSendAction()) return;
    var claim = prompt('写下你此刻的想法（每日一次，可能触及遗迹的真相）：');
    if (!claim || !claim.trim()) return;

    knowledgeSubmittedToday = true;
    updateKnowledgeBtn();
    if (sendPlayerAction({ type: 'add_claim', claim: claim.trim() }, '连接已断开')) playSound('addKnowledge');
  }

  function updateKnowledgeBtn() {
    var btn = document.getElementById('addKnowledgeBtn');
    if (!btn) return;
    btn.disabled = knowledgeSubmittedToday;
    btn.classList.toggle('disabled', knowledgeSubmittedToday);
    btn.title = knowledgeSubmittedToday ? '今日已提交，明日再悟' : '每日一次：写下你的想法。若触及遗迹真相，会有领悟';
  }

  // ===== 键盘快捷键 =====
  function setupEventListeners() {
    document.addEventListener('click', function(e) {
      var target = e.target.closest ? e.target.closest('[data-app-action]') : null;
      if (!target) return;
      var action = target.getAttribute('data-app-action');
      if (action === 'switch-tab') {
        switchTab(target.getAttribute('data-tab'));
      } else if (action === 'toggle-threads') {
        toggleThreads();
      } else if (action === 'toggle-sound') {
        toggleSound();
      } else if (action === 'show-guide') {
        showGuide();
      } else if (action === 'close-guide') {
        closeGuide();
      } else if (action === 'close-profile') {
        closeProfile();
      } else if (action === 'close-dialogue') {
        closeDialogue();
      } else if (action === 'start-dialogue') {
        startDialogueFromProfile();
      } else if (action === 'respond-request') {
        respondRequest(target.dataset.requestId, target.dataset.optionId);
      } else if (action === 'intervene-crisis') {
        interveneCrisis(target.dataset.crisisId, target.dataset.crisisAction || 'help');
      } else if (action === 'follow-thread') {
        var card = target.closest('.thread-card');
        var index = Number(target.dataset.threadItem);
        var threadIndex = Array.prototype.indexOf.call(document.querySelectorAll('.thread-card'), card);
        var thread = (currentState && currentState.today_threads || [])[threadIndex];
        var item = thread && (thread.items || [])[index];
        followThread(item && item.action);
      } else if (action === 'context-action') {
        var type = target.dataset.actionType;
        if (type === 'observe') doObserve();
        else if (type === 'work') doWork('work');
        else if (type === 'investigate') doInvestigate();
        else if (type === 'talk') openProfile(target.dataset.agentId);
      } else if (action === 'dialogue-option') {
        var agent = currentState && (currentState.agents || []).find(function(item) {
          return item.id === target.dataset.agentId;
        });
        if (agent) executeDialogue(agent, target.dataset.optionId, target.dataset.optionText);
      }
    });

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

    summary = summary || {};
    var overall = summary.overall_summary || summary.title || summary.body || '今天的小镇留下了一些变化。';
    var beats = summary.causal_beats || summary.beats || [];

    var item = document.createElement('div');
    item.className = 'event-item info';
    item.style.borderLeftColor = 'var(--warm-500)';
    item.style.background = 'linear-gradient(90deg, rgba(255,167,38,0.06), transparent)';
    item.innerHTML =
      '<span class="event-icon">📰</span>' +
      '<div class="event-content">' +
        '<div class="event-text" style="font-weight:600;color:var(--warm-500)">每日摘要</div>' +
        '<div class="event-text" style="margin-top:4px">' + esc(overall) + '</div>' +
        (beats.length ? '<div class="event-causal-beats">' + beats.slice(0, 3).map(function(beat) { return '<div>↳ ' + esc(beat) + '</div>'; }).join('') + '</div>' : '') +
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
  window.toggleSound = toggleSound;
  window.showGuide = showGuide;
  window.closeGuide = closeGuide;
  window.openProfile = openProfile;
  window.closeProfile = closeProfile;
  window.closeDialogue = closeDialogue;
  window.startDialogueFromProfile = startDialogueFromProfile;
  window.switchTab = switchTab;
  window.respondRequest = respondRequest;
  window.toggleThreads = toggleThreads;
  window.followThread = followThread;
  window.interveneCrisis = interveneCrisis;

  // 5秒轮询（WebSocket 备用）
  setInterval(function() {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      window.KTownApi.getState().then(function(data) {
        currentState = data;
        updateUI(data);
      }).catch(function() {});
    }
  }, 5000);

})();
