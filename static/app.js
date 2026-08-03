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
  
  showContextTip();
    // 顶部状态栏
    const player = data.player || {};
    setText('stat-day', `第${Math.floor(data.tick / 24) + 1}天`);
    setText('stat-weather', getWeatherDisplay(data.weather));
    setText('stat-gold', player.gold || 0);
    setText('stat-energy', Math.round(player.energy || 100));
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
      square: '🏛️', workshop: '🔨', wilderness: '🌲', school: '🏫', mine: '⛏️'
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
        <div class="loc-marker">${locIcons[id] || '📍'} ${locNames[id] || loc.name}</div>
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
      happy: '😊', neutral: '😐', anxious: '😰', angry: '😠', sad: '😢'
    };

    agents.forEach(a => {
      const item = document.createElement('div');
      item.className = 'agent-item';
      item.innerHTML = `
        <div class="agent-avatar" style="background:${getAgentColor(a.id)}">${getAgentEmoji(a.id)}</div>
        <div>
          <div class="agent-name">${a.name}</div>
          <div class="agent-meta">${a.role_cn || a.role} · ${a.location_cn || a.location}</div>
        </div>
        <div class="agent-meta">
          <span class="mood-indicator mood-${a.mood}">${moodEmojis[a.mood] || '😐'}</span>
          <div>💰${a.gold} ⚡${Math.round(a.energy)}</div>
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

    // 从currentState获取完整知识数据
    if (!currentState || !currentState.knowledge) return;

    const claims = currentState.knowledge.claims || [];
    container.innerHTML = '';

    claims.slice(-20).reverse().forEach(c => {
      const confidence = Math.round(c.confidence * 100);
      const item = document.createElement('div');
      item.className = 'knowledge-item';
      item.innerHTML = `
        <div class="claim-text">📖 ${c.claim}</div>
        <div class="claim-meta">
          <span>👤 ${c.created_by}</span>
          <span>📍 ${c.location}</span>
          <span>置信度:${confidence}%<span class="confidence-bar"><span class="confidence-fill" style="width:${confidence}%"></span></span></span>
          ${c.solidified ? '<span style="color:var(--gold)">✓ 已固化</span>' : ''}
        </div>
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
  function addLogEntry(text, icon = '📝') {
    const log = document.getElementById('log-content');
    if (!log) return;
    const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `<span class="log-time">${time}</span><span class="log-icon">${icon}</span><span class="log-text">${text}</span>`;
    log.insertBefore(entry, log.firstChild);
    while (log.children.length > 30) log.removeChild(log.lastChild);
  }

  // 添加摘要条目
  function addSummaryEntry(summary) {
    const log = document.getElementById('log-content');
    if (!log) return;
    const entry = document.createElement('div');
    entry.className = 'log-entry summary';
    const day = summary.day || '?';
    const text = summary.overall_summary || summary.narrative || '新的一天';
    entry.innerHTML = `<span class="log-time">第${day}天</span><span class="log-icon">📋</span><span class="log-text">${text}</span>`;
    log.insertBefore(entry, log.firstChild);
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
    const agentNames = agentsHere.map(a => a.name).join('、') || '无人';
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
      `<button class="tutorial-btn ${a.primary ? 'primary' : 'modal-close'}" onclick="">${a.text}</button>`
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
      { icon: '🏘️', title: '欢迎来到 K-town 边境小镇！', desc: '这是一个由AI居民自主生活的小镇。你作为新来的旅行者，可以观察、参与甚至影响小镇的发展。' },
      { icon: '👥', title: '居民们有自己的生活', desc: '12位居民各有职业、性格和目标。他们会工作、社交、传播知识，过着自主的生活。' },
      { icon: '🗺️', title: '探索小镇', desc: '点击地图上的地点可以查看详情。使用右侧的操作按钮移动、工作和社交。' },
      { icon: '📖', title: '知识系统', desc: '居民们会创造、传播和质疑知识。你也可以添加自己的知识，影响小镇的认知。' },
      { icon: '🎯', title: '开始你的旅程', desc: '完成新手任务，与居民建立关系，探索小镇的秘密。祝你在K-town度过愉快的时光！' }
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
      showToast('欢迎来到K-town！先和广场的梅奶奶打个招呼吧', 'success');
    });
  }

  // 操作函数
  function movePlayer(location) {
    sendAction('move', { target: location });
    visitedLocations.add(location);
    addLogEntry(`移动到了${getLocationCn(location)}`, '🚶');
  }

  function doWork(action) {
    sendAction(action, {});
    addLogEntry(`执行了${getActionName(action)}`, '⚒️');
  }

  function doRest() {
    sendAction('rest', {});
    addLogEntry('休息恢复体力', '💤');
  }

  function talkToAgent() {
    sendAction('talk', { target: 'nearest' });
    addLogEntry('和附近的居民聊天', '💬');
  }

  function addKnowledge() {
    const subject = prompt('知识主题：');
    if (!subject) return;
    const claim = prompt('知识内容：');
    if (!claim) return;
    sendAction('claim', { subject, claim });
    addLogEntry(`添加了知识：${subject}`, '📖');
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
        if (target === 'knowledge') loadKnowledge();
        if (target === 'quests') loadQuests();
      });
    });
  }

  // 加载知识列表
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
          <div class="claim-text">📖 ${c.claim}</div>
          <div class="claim-meta">
            <span>👤 ${c.created_by}</span>
            <span>📍 ${c.location}</span>
            <span>置信度:${confidence}%</span>
            ${c.solidified ? '<span style="color:var(--gold)">✓ 已固化</span>' : ''}
          </div>
        `;
        container.appendChild(item);
      });
    }).catch(() => {});
  }

  // 加载任务列表
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
          <div class="quest-title">${q.status === 'completed' ? '✅' : '🎯'} ${q.title}</div>
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
    const map = { clear: '☀️ 晴朗', cloudy: '☁️ 多云', rainy: '🌧️ 下雨', snowy: '❄️ 下雪', windy: '💨 大风' };
    return map[weather] || '☀️ 晴朗';
  }

  function getTimeOfDay(tick) {
    const hour = tick % 24;
    if (hour >= 6 && hour < 9) return '🌅 早晨';
    if (hour >= 9 && hour < 14) return '☀️ 白天';
    if (hour >= 14 && hour < 18) return '🌇 傍晚';
    return '🌙 夜晚';
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
      agent_elder: '👵', agent_blacksmith: '🔨', agent_carpenter: '🪵',
      agent_forager: '🌿', agent_scout: '🧭', agent_merchant: '💰',
      agent_teacher: '📖', agent_farmer: '🌾', agent_storyteller: '📜',
      agent_healer: '💊', agent_miner: '⛏️', agent_player: '👤'
    };
    return map[id] || '👤';
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
      weather_change: '🌤️', resource_found: '💎', social_encounter: '👋',
      item_crafted: '🔨', rumor_spread: '🗣️', trade: '💱', festival: '🎉',
      disaster: '⚠️', player_action: '🎮'
    };
    return map[type] || '📝';
  }

  // 定期轮询（WebSocket备用）
  setInterval(() => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      fetch('/api/state').then(r => r.json()).then(data => {
        currentState = data;
        updateUI(data);
      }).catch(() => {});
    }
  }, 5000);

})();
