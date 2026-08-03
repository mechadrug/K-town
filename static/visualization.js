// K-town 可视化模块
(function() {
  'use strict';

  // 价格趋势图
  function drawPriceChart(canvasId, priceHistory) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !priceHistory) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width = canvas.parentElement.clientWidth - 20;
    const h = canvas.height = 120;
    
    ctx.clearRect(0, 0, w, h);
    
    const resources = Object.keys(priceHistory);
    const colors = {
      food: '#4caf50', materials: '#ff9800', tools: '#2196f3',
      medicine: '#9c27b0', ore: '#607d8b'
    };
    
    // 找出最大价格用于缩放
    let maxPrice = 1;
    resources.forEach(r => {
      const hist = priceHistory[r];
      if (hist) {
        hist.forEach(p => { if (p > maxPrice) maxPrice = p; });
      }
    });
    
    // 绘制网格线
    ctx.strokeStyle = 'rgba(255,255,255,0.1)';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
      const y = h - (i / 4) * h;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }
    
    // 绘制每条价格线
    resources.forEach(r => {
      const hist = priceHistory[r];
      if (!hist || hist.length < 2) return;
      
      ctx.strokeStyle = colors[r] || '#888';
      ctx.lineWidth = 2;
      ctx.beginPath();
      
      hist.forEach((price, i) => {
        const x = (i / (hist.length - 1)) * w;
        const y = h - (price / maxPrice) * h * 0.9;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    });
    
    // 绘制图例
    let legendX = 5;
    resources.forEach(r => {
      ctx.fillStyle = colors[r] || '#888';
      ctx.fillRect(legendX, 5, 8, 8);
      ctx.fillStyle = '#8899aa';
      ctx.font = '10px sans-serif';
      ctx.fillText(r, legendX + 12, 12);
      legendX += 50;
    });
  }

  // 社交网络图（简单节点图）
  function drawSocialNetwork(canvasId, agents) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !agents) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width = canvas.parentElement.clientWidth - 20;
    const h = canvas.height = 150;
    
    ctx.clearRect(0, 0, w, h);
    
    // 计算节点位置（圆形布局）
    const centerX = w / 2;
    const centerY = h / 2;
    const radius = Math.min(w, h) * 0.35;
    
    const positions = {};
    agents.forEach((a, i) => {
      const angle = (i / agents.length) * Math.PI * 2 - Math.PI / 2;
      positions[a.id] = {
        x: centerX + Math.cos(angle) * radius,
        y: centerY + Math.sin(angle) * radius,
        name: a.name
      };
    });
    
    // 绘制关系线
    agents.forEach(a => {
      if (!a.social_ties) return;
      Object.entries(a.social_ties).forEach(([otherId, tie]) => {
        if (tie > 10 && positions[otherId]) {
          const p1 = positions[a.id];
          const p2 = positions[otherId];
          
          // 关系好坏决定颜色
          if (tie > 30) ctx.strokeStyle = 'rgba(76, 175, 80, 0.6)';
          else if (tie > 0) ctx.strokeStyle = 'rgba(255, 215, 0, 0.3)';
          else ctx.strokeStyle = 'rgba(244, 67, 54, 0.3)';
          
          ctx.lineWidth = Math.min(3, Math.abs(tie) / 10);
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.stroke();
        }
      });
    });
    
    // 绘制节点
    agents.forEach(a => {
      const p = positions[a.id];
      if (!p) return;
      
      // 节点颜色基于心情
      const moodColors = {
        happy: '#4caf50', neutral: '#ffd700', anxious: '#ff9800',
        angry: '#f44336', sad: '#2196f3'
      };
      ctx.fillStyle = moodColors[a.mood] || '#888';
      ctx.beginPath();
      ctx.arc(p.x, p.y, 8, 0, Math.PI * 2);
      ctx.fill();
      
      // 名字标签
      ctx.fillStyle = '#e8edf2';
      ctx.font = '9px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(a.name.slice(0, 3), p.x, p.y + 18);
    });
  }

  // 事件时间线
  function renderEventTimeline(containerId, events) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    // 只显示最近10个事件
    const recent = events.slice(-10);
    container.innerHTML = '';
    
    const typeIcons = {
      weather_change: '\u{1F324}', resource_found: '\u{1F48E}', social_encounter: '\u{1F44B}',
      item_crafted: '\u{1F528}', rumor_spread: '\u{1F5E3}', trade: '\u{1F4B1}',
      festival: '\u{1F389}', disaster: '\u{26A0}', player_action: '\u{1F3AE}'
    };
    
    recent.forEach(evt => {
      const div = document.createElement('div');
      div.style.cssText = 'padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.05);font-size:0.8em;display:flex;gap:8px;';
      div.innerHTML = `<span>${typeIcons[evt.type] || '\u{1F4F0}'}</span><span style="color:var(--text-secondary);">${evt.action || evt.type}</span>`;
      container.appendChild(div);
    });
  }

  // 导出函数
  window.KTownViz = { drawPriceChart, drawSocialNetwork, renderEventTimeline };

})();
