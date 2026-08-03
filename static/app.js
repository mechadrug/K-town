// K-town 前端应用
(function() {
  'use strict';

  // 状态
  let currentState = null;
  let ws = null;
  let tutorialStep = 0;
  let visitedLocations = new Set();
  let talkedAgents = new Set();

  // DOM就绪后初始化
  document.addEventListener('DOMContentLoaded', init);

  function init() {
    connectWebSocket();
    setupEventListeners();
    // 检查是否显示新手引导
    if (!localStorage.getItem('ktown_tutorial_done')) {
      showTutorial();
    }
  }

  // WebSocket连接
  function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws`);

    ws.onopen = () => {
      console.log('WebSocket connected');
      showToast('已连接到服务器', 'success');
    };

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        handleMessage(msg);
      } catch (err) {
        console.error('WS message error:', err);
      }
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected, retrying...');
      setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (err) => {
      console.error('WS error:', err);
    };
  }

  // 处理消息
  function handleMessage(msg) {
    switch (msg.type) {
      case 'state':
        currentState = msg.data;
        updateUI(msg.data);
        break;
      case 'day_summary':
        addSummaryEntry(msg.data);
        showToast('新的一天开始了！', 'info');
        break;
      case 'event':
        addLogEntry(msg.data.action || msg.data.type, getEventIcon(msg.data.type));
        break;
      case 'player_action_result':
        if (msg.data && msg.data.result) {
          showToast(msg.data.result, 'success');
        }
        break;
    }
  }

  // 更新UI
  function updateUI(data) {
    // 顶部状态栏
    const player = data.player || {};
    setText('stat-day', `第${Math.floor(data.tick / 24) + 1}天`);
    setText('stat-weather', getWeatherDisplay(data.weather));
    setText('stat-gold', player.gold || 0);
    setText('stat-energy', Math.round(player.energy || 100));
    setText('stat-ap', `${player.action_points || 12}/${player.max_ap || 12}`);
    setText('stat-time', getTimeOfDay(data.tick));
    setText('stat-location', getLocationCn(player.location));

    // 更新时间条颜色
    updateTimeIndicator(data.tick);

    // 渲染地图
    renderMap(data);

    // 渲染居民列表
    renderAgents(data.agents || []);

    // 渲染知识列表
    renderKnowledge(data.knowledge);

    // 渲染任务列表
    renderQuests(data);

    // 更新玩家面板
    updatePlayerPanel(player);
  }

  // 渲染地图
  function renderMap(data) {
    const canvas = document.getElementById('map-canvas');
    if (!canvas) return;

    // 清除旧的agent标记（保留地点）
    canvas.querySelectorAll('.map-location').forEach(el => el.remove());

    const locations = data.locations || {};
    const agents = data.agents || [];

    // 地点位置（百分比）
    const locPositions = {
      square: { x: 50, y: 30 },
      workshop: { x: 20, y: 25 },
      wilderness: { x: 80, y: 70 },
      school: { x: 22, y: 70 },
      mine: { x: 80, y: 25 }
    };

    const locIcons = {
      square: '\u{1F3D8}', workshop: '\u{2692}', wilderness: '\u{1F332}', school: '\u{1F4DA}', mine: '\u{26CF}'
    };

    const locNames = {
      square: '广场', workshop: '工坊', wilderness: '荒野', school: '学校', mine: '矿洞'
    };

    // 计算每个地点的agent
    const locAgents = {};
    agents.forEach(a => {
      locAgents[a.location] = locAgents[a.location] || [];
      locAgents[a.location].push(a);
    });

    // 渲染地点
    Object.entries(locations).forEach(([id, loc]) => {
      const pos = locPositions[id] || { x: 50, y: 50 };
      const locEl = document.createElement('div');
      locEl.className = `map-location loc-${id}`;
      locEl.style.left = pos.x + '%';
      locEl.style.top = pos.y + '%';

      const agentsHere = locAgents[id] || [];
      const agentDots = agentsHere.map(a => {
        const emoji = getAgentEmoji(a.id);
        return `<div class="agent-dot" title="${a.name}">${emoji}</div>`;
      }).join('');

      locEl.innerHTML = `
        <div class="loc-marker">${locIcons[id] || '\u{1F4CD}'} ${locNames[id] || loc.name}</div>
        <div class="loc-agents">${agentDots}</div>
      `;

      locEl.addEventListener('click', () => showLocationDetail(id, loc, agentsHere));
      canvas.appendChild(locEl);
    });
  }

  // 渲染居民列表
  function renderAgents(agents) {
    const container = document.getElementById('agent-list');
    if (!container) return;
    container.innerHTML = '';

    const moodEmojis = {
      happy: '\u{1F60A}', neutral: '\u{1F610}', anxious: '\u{1F61F}', angry: '\u{1F620}', sad: '\u{1F622}'
    };

    agents.forEach(a => {
      const energy = Math.round(a.energy || 0);
      const item = document.createElement('div');
      item.className = 'agent-item';
      item.style.borderLeft = `3px solid ${getAgentColor(a.id)}`;
      item.innerHTML = `
        <div class="agent-avatar" style="background:${getAgentColor(a.id)}">${getAgentEmoji(a.id)}</div>
        <div class="agent-info">
          <div class="agent-name">${a.name}</div>
          <div class="agent-role">${a.role_cn || a.role || '居民'} \u00B7 ${getLocationCn(a.location)}</div>
          <div class="agent-bar"><div class="bar-fill energy" style="width:${energy}%"></div></div>
          <div class="agent-stats">${moodEmojis[a.mood] || '\u{1F610}'} \u{1F4B0}${a.gold || 0} \u{26A1}${energy}</div>
        </div>
      `;
      item.addEventListener('click', () => showAgentDetail(a));
      container.appendChild(item);
    });
  }

  // 渲染知识列表
  function renderKnowledge(knowledge) {
    const container = document.getElementById('knowledge-list');
    if (!container) return;

    const k = knowledge || (currentState && currentState.knowledge) || {};
    const claims = k.claims || [];
    const agentCounts = k.agent_counts || {};

    container.innerHTML = '';

    // 总览信息
    const summary = document.createElement('div');
    summary.className = 'knowledge-summary';
    summary.style.cssText = 'padding:8px 12px;margin-bottom:10px;background:var(--bg-card);border-radius:var(--radius-sm);font-size:0.8em;';
    summary.innerHTML = `
      <div style="color:var(--accent);font-weight:600;margin-bottom:4px;">\u{1F4DA} 共 ${claims.length} 条知识</div>
      <div style="color:var(--text-secondary);">来源分布：${Object.entries(agentCounts).map(([name, count]) => `${name}: ${count}条`).join(' \u00B7 ') || '暂无数据'}</div>
    `;
    container.appendChild(summary);

    // 知识条目
    claims.slice(-20).reverse().forEach(c => {
      const confidence = Math.round((c.confidence || 0) * 100);
      const item = document.createElement('div');
      item.className = 'knowledge-item';
      item.style.borderLeftColor = c.solidified ? 'var(--gold)' : 'var(--accent)';
      item.innerHTML = `
        <div class="claim-text">\u{1F516} ${c.claim}</div>
        <div class="claim-meta">
          <span>\u{1F464} ${c.created_by}</span>
          <span>\u{1F4CD} ${c.location}</span>
          <span>置信度: ${confidence}%<span class="confidence-bar"><span class="confidence-fill" style="width:${confidence}%"></span></span></span>
          ${c.solidified ? '<span style="color:var(--gold)">\u2713 已固化</span>' : ''}
        </div>
      `;
      container.appendChild(item);
    });

    if (claims.length === 0) {
      container.innerHTML += '<p class="placeholder-text">暂无知识记录</p>';
    }
  }

  // 渲染任务列表
  function renderQuests(data) {
    const container = document.getElementById('quest-list');
    if (!container) return;

    const active = data.active_quests || (data.quests && data.quests.active) || [];
    const completed = data.completed_quests || (data.quests && data.quests.completed) || [];

    container.innerHTML = '';

    if (active.length === 0 && completed.length === 0) {
      container.innerHTML = '<p class="placeholder-text">暂无任务</p>';
      return;
    }

    active.forEach(q => {
      const pct = q.progress_pct || Math.round(((q.progress || 0) / Math.max(q.target || 1, 1)) * 100);
      const item = document.createElement('div');
      item.className = 'quest-item';
      item.innerHTML = `
        <div class="quest-title">\u{1F3AF} ${q.title}</div>
        <div class="quest-desc">${q.description || ''}</div>
        <div class="quest-progress"><div class="quest-progress-fill" style="width:${pct}%"></div></div>
        <div class="quest-reward">进度: ${q.progress || 0}/${q.target || 1} | 奖励: ${q.reward_text || (q.reward_gold + '金币')}</div>
      `;
      container.appendChild(item);
    });

    completed.forEach(q => {
      const item = document.createElement('div');
      item.className = 'quest-item completed';
      item.innerHTML = `
        <div class="quest-title">\u2705 ${q.title}</div>
        <div class="quest-desc">${q.description || ''}</div>
        <div class="quest-progress"><div class="quest-progress-fill" style="width:100%"></div></div>
        <div class="quest-reward">奖励: ${q.reward_text || (q.reward_gold + '金币')}</div>
      `;
      container.appendChild(item);
    });
  }

  // 更新玩家面板
  function updatePlayerPanel(player) {
    const energyBar = document.getElementById('player-energy-bar');
    const goldBar = document.getElementById('player-gold-bar');
    if (energyBar) energyBar.style.width = (player.energy || 0) + '%';
    if (goldBar) goldBar.style.width = Math.min(100, (player.gold || 0) / 5) + '%';
  }

  // 添加日志条目
  function addLogEntry(text, icon = '\u{1F4C4}') {
    const log = document.getElementById('log-content');
    if (!log) return;
    const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `<span class="log-time">${time}</span><span class="log-icon">${icon}</span><span class="log-text">${text}</span>`;
    log.insertBefore(entry, log.firstChild);
    while (log.children.length > 30) log.removeChild(log.lastChild);
  }

  // 添加摘要条目（显示在每日摘要区域）
  function addSummaryEntry(summary) {
    const container = document.getElementById('daily-summary');
    if (!container) return;

    // 移除占位符
    const placeholder = container.querySelector('.placeholder-text');
    if (placeholder) placeholder.remove();

    const day = summary.day || Math.floor((currentState ? currentState.tick : 0) / 24) + 1;
    const narrative = summary.overall_summary || summary.narrative || summary.text || '新的一天开始了';
    const events = summary.key_events || summary.events || [];

    const entry = document.createElement('div');
    entry.className = 'summary-entry';
    entry.style.cssText = 'margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid var(--border);animation:fadeIn 0.4s ease;';

    let eventsHtml = '';
    if (events.length > 0) {
      eventsHtml = `
        <div style="margin-top:8px;padding-left:12px;border-left:2px solid var(--accent);">
          ${events.map(e => `<div style="font-size:0.85em;color:var(--text-secondary);margin-bottom:2px;">\u2022 ${e}</div>`).join('')}
        </div>
      `;
    }

    entry.innerHTML = `
      <div style="font-weight:600;color:var(--gold);margin-bottom:6px;font-size:0.95em;">\u{1F4C5} 第 ${day} 天</div>
      <div style="line-height:1.6;color:var(--text-primary);font-size:0.9em;">${narrative}</div>
      ${eventsHtml}
    `;

    container.insertBefore(entry, container.firstChild);
  }

  // 显示Toast消息
  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.3s';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  // 显示地点详情
  function showLocationDetail(id, loc, agentsHere) {
    const locNames = { square: '广场', workshop: '工坊', wilderness: '荒野', school: '学校', mine: '矿洞' };
    const agentNames = agentsHere.map(a => a.name).join('\u3001') || '无人';
    showModal(
      `${locNames[id] || loc.name}`,
      `${loc.description || ''}<br><br>当前在此的居民：${agentNames}`,
      [{ text: '关闭', primary: false }]
    );
  }

  // 显示居民详情
  function showAgentDetail(agent) {
    const moodDesc = {
      happy: '心情愉快', neutral: '心情平静', anxious: '有些焦虑', angry: '非常生气', sad: '心情低落'
    };
    const content = `
      <p><strong>职业：</strong>${agent.role_cn || agent.role}</p>
      <p><strong>位置：</strong>${agent.location_cn || agent.location}</p>
      <p><strong>体力：</strong>${Math.round(agent.energy)}/100</p>
      <p><strong>心情：</strong>${moodDesc[agent.mood] || agent.mood}</p>
      <p><strong>金币：</strong>${agent.gold}</p>
      <p><strong>目标：</strong>${agent.goal || '暂无目标'}</p>
      <p><strong>知识：</strong>${agent.knowledge_count || 0}条</p>
    `;
    showModal(agent.name, content, [{ text: '关闭', primary: false }]);
  }

  // 模态框
  function showModal(title, bodyHtml, actions = []) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay active';
    const actionBtns = actions.map(a =>
      `<button class="tutorial-btn ${a.primary ? 'primary' : 'modal-close'}">${a.text}</button>`
    ).join('');
    overlay.innerHTML = `
      <div class="modal">
        <h3>${title}</h3>
        <div class="modal-body">${bodyHtml}</div>
        <div class="modal-actions">${actionBtns}</div>
      </div>
    `;
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.remove();
    });
    overlay.querySelectorAll('.modal-close').forEach(btn => {
      btn.addEventListener('click', () => overlay.remove());
    });
    document.body.appendChild(overlay);
  }

  // 新手引导
  function showTutorial() {
    const overlay = document.getElementById('tutorial-overlay');
    if (!overlay) return;
    overlay.classList.add('active');

    const steps = [
      { icon: '\u{1F3D8}', title: '欢迎来到 K-town 边境小镇！', desc: '这是一个由AI居民自主生活的小镇。你作为新来的旅行者，可以观察、参与甚至影响小镇的发展。' },
      { icon: '\u{1F465}', title: '居民有自己的生活', desc: '12位居民各有职业、性格和目标。他们会工作、社交、传播知识，过着自主的生活。' },
      { icon: '\u{1F5FA}', title: '探索小镇', desc: '点击地图上的地点可以查看详情。使用右侧的操作按钮移动、工作和社交。' },
      { icon: '\u{1F4D6}', title: '知识系统', desc: '居民会创造、传播和质疑知识。你也可以添加自己的知识，影响小镇的认知。' },
      { icon: '\u{1F3AF}', title: '开始你的旅途', desc: '完成新手任务，与居民建立关系，探索小镇的秘密。祝你在K-town度过愉快的光阴！' }
    ];

    const stepsHtml = steps.map((s, i) => `
      <div class="tutorial-step"><span class="step-num">${i + 1}</span><span>${s.title}</span></div>
    `).join('');

    overlay.innerHTML = `
      <div class="tutorial-card">
        <div class="tutorial-icon">${steps[0].icon}</div>
        <h2>${steps[0].title}</h2>
        <p>${steps[0].desc}</p>
        <div class="tutorial-steps">${stepsHtml}</div>
        <button class="tutorial-btn" id="tutorial-start">开始探索</button>
      </div>
    `;

    document.getElementById('tutorial-start').addEventListener('click', () => {
      overlay.classList.remove('active');
      localStorage.setItem('ktown_tutorial_done', 'true');
      showToast('欢迎来到K-town！先和广场的精灵阿姨打个招呼吧', 'success');
    });
  }

  // 操作函数
  function movePlayer(location) {
    const msg = JSON.stringify({ type: 'player_action', action: { type: 'move', location: location } });
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(msg);
    } else {
      sendAction('move', { target: location });
    }
    visitedLocations.add(location);
    addLogEntry(`移动到了${getLocationCn(location)}`, '\u{1F6B6}');
  }

  function doWork(action) {
    sendAction(action, {});
    addLogEntry(`执行了${getActionName(action)}`, '\u{2692}');
  }

  function doRest() {
    sendAction('rest', {});
    addLogEntry('休息恢复体力', '\u{1F6CF}');
  }

  function talkToAgent() {
    sendAction('talk', { target: 'nearest' });
    addLogEntry('和附近的居民聊天', '\u{1F4AC}');
  }

  function addKnowledge() {
    const subject = prompt('知识主题：');
    if (!subject) return;
    const claim = prompt('知识内容：');
    if (!claim) return;
    sendAction('claim', { subject, claim });
    addLogEntry(`添加了知识：${subject}`, '\u{1F4D6}');
    showToast('知识已添加！', 'success');
  }

  function resetSimulation() {
    if (!confirm('确定要重置模拟吗？所有进度将丢失。')) return;
    fetch('/api/reset', { method: 'POST' })
      .then(r => r.json())
      .then(() => {
        showToast('模拟已重置', 'success');
        localStorage.removeItem('ktown_tutorial_done');
        setTimeout(() => location.reload(), 1000);
      });
  }

  // 发送操作
  function sendAction(type, payload) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'player_action', action: { type, ...payload } }));
    }
    fetch('/api/player/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, ...payload })
    }).then(r => r.json()).then(data => {
      if (data.result) showToast(data.result, 'success');
    }).catch(() => {
      showToast('操作失败，请重试', 'error');
    });
  }

  // 设置事件监听
  function setupEventListeners() {
    // 标签页切换
    document.querySelectorAll('.log-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.log-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const target = tab.dataset.tab;
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        const content = document.getElementById(`tab-${target}`);
        if (content) content.classList.add('active');

        // 加载对应数据
        if (target === 'knowledge' && currentState) renderKnowledge(currentState.knowledge);
        if (target === 'quests' && currentState) renderQuests(currentState);
      });
    });
  }

  // 加载知识列表（API备用）
  function loadKnowledge() {
    fetch('/api/knowledge').then(r => r.json()).then(data => {
      const container = document.getElementById('knowledge-list');
      if (!container || !data.claims) return;
      container.innerHTML = '';
      data.claims.slice(-30).reverse().forEach(c => {
        const confidence = Math.round((c.confidence || 0) * 100);
        const item = document.createElement('div');
        item.className = 'knowledge-item';
        item.style.borderLeftColor = c.solidified ? 'var(--gold)' : 'var(--accent)';
        item.innerHTML = `
          <div class="claim-text">\u{1F516} ${c.claim}</div>
          <div class="claim-meta">
            <span>\u{1F464} ${c.created_by}</span>
            <span>\u{1F4CD} ${c.location}</span>
            <span>置信度: ${confidence}%</span>
            ${c.solidified ? '<span style="color:var(--gold)">\u2713 已固化</span>' : ''}
          </div>
        `;
        container.appendChild(item);
      });
    }).catch(() => {});
  }

  // 加载任务列表（API备用）
  function loadQuests() {
    fetch('/api/quests').then(r => r.json()).then(data => {
      const container = document.getElementById('quest-list');
      if (!container) return;
      container.innerHTML = '';

      const allQuests = [...(data.active_quests || []), ...(data.completed_quests || [])];
      allQuests.forEach(q => {
        const item = document.createElement('div');
        item.className = `quest-item ${q.status === 'completed' ? 'completed' : ''}`;
        item.innerHTML = `
          <div class="quest-title">${q.status === 'completed' ? '\u2705' : '\u{1F3AF}'} ${q.title}</div>
          <div class="quest-desc">${q.description}</div>
          <div class="quest-progress"><div class="quest-progress-fill" style="width:${q.progress_pct}%"></div></div>
          <div class="quest-reward">进度: ${q.progress}/${q.target} | 奖励: ${q.reward_text || q.reward_gold + '金币'}</div>
        `;
        container.appendChild(item);
      });
    }).catch(() => {});
  }

  // 工具函数
  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  function getWeatherDisplay(weather) {
    const map = { clear: '\u2600 晴朗', cloudy: '\u26C5 多云', rainy: '\u{1F327} 下雨', snowy: '\u2744 下雪', windy: '\u{1F32A} 大风' };
    return map[weather] || '\u2600 晴朗';
  }

  function getTimeOfDay(tick) {
    const hour = tick % 24;
    if (hour >= 6 && hour < 9) return '\u{1F305} 早晨';
    if (hour >= 9 && hour < 14) return '\u2600 白天';
    if (hour >= 14 && hour < 18) return '\u{1F306} 傍晚';
    return '\u{1F303} 夜晚';
  }

  function updateTimeIndicator(tick) {
    const hour = tick % 24;
    const indicator = document.getElementById('time-indicator');
    if (indicator) {
      indicator.style.background = hour >= 6 && hour < 18
        ? 'linear-gradient(90deg, #faa623, #f0883e)'
        : 'linear-gradient(90deg, #58a6ff, #bc8cff)';
    }
  }

  function getLocationCn(loc) {
    return { square: '广场', workshop: '工坊', wilderness: '荒野', school: '学校', mine: '矿洞' }[loc] || loc;
  }

  function getAgentEmoji(id) {
    const map = {
      agent_elder: '\u{1F474}', agent_blacksmith: '\u{2692}', agent_carpenter: '\u{1FA93}',
      agent_forager: '\u{1F344}', agent_scout: '\u{1F985}', agent_merchant: '\u{1F4B5}',
      agent_teacher: '\u{1F4D6}', agent_farmer: '\u{1F33E}', agent_storyteller: '\u{1F4DC}',
      agent_healer: '\u{1FA7A}', agent_miner: '\u{26CF}', agent_player: '\u{1F464}'
    };
    return map[id] || '\u{1F464}';
  }

  function getAgentColor(id) {
    const map = {
      agent_elder: '#9c27b0', agent_blacksmith: '#ff9800', agent_carpenter: '#8b4513',
      agent_forager: '#4caf50', agent_scout: '#2ecc71', agent_merchant: '#ffd700',
      agent_teacher: '#2196f3', agent_farmer: '#1abc9c', agent_storyteller: '#e91e63',
      agent_healer: '#00cec9', agent_miner: '#636e72', agent_player: '#ff6b35'
    };
    return map[id] || '#666';
  }

  function getActionName(action) {
    return { gather_food: '采集食物', gather_material: '采集材料', craft_tool: '制作工具', craft_furniture: '制作家具', rest: '休息' }[action] || action;
  }

  function getEventIcon(type) {
    const map = {
      weather_change: '\u{1F324}', resource_found: '\u{1F48E}', social_encounter: '\u{1F44D}',
      item_crafted: '\u{2692}', rumor_spread: '\u{1F5E3}', trade: '\u{1F4B0}', festival: '\u{1F389}',
      disaster: '\u26A0', player_action: '\u{1F3AE}'
    };
    return map[type] || '\u{1F4C4}';
  }

  // 占位函数（避免引用错误）
  function showContextTip() { /* stub */ }
  function updateVisualizations() { /* stub */ }

  // 定时轮询（WebSocket备用）
  setInterval(() => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      fetch('/api/state').then(r => r.json()).then(data => {
        currentState = data;
        updateUI(data);
      }).catch(() => {});
    }
  }, 5000);

})();
