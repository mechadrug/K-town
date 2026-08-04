// K-town 图标系统 —— 全站 emoji 单一来源
// 目的：杜绝 HTML 中的 `?` 占位符与 JS 中散落的重复定义。
// 用法：window.KTownIcons.<分类>.<键>，例如 KTownIcons.weather.rainy
(function () {
  'use strict';
  window.KTownIcons = {
    time: { morning: '🌅', day: '☀️', dusk: '🌇', night: '🌙' },
    weather: { clear: '☀️', cloudy: '⛅', rainy: '🌧️', snowy: '❄️', windy: '🌪️' },
    mood: { happy: '😊', neutral: '😐', sad: '😔', angry: '😠', anxious: '😟' },
    location: { square: '🏛️', workshop: '🔨', wilderness: '🌲', school: '🏫', mine: '⛏️' },
    action: {
      move: '🚶', work: '🛠️', talk: '💬', rest: '🛏️', investigate: '🔍',
      trade: '💰', observe: '👀', sleep: '🌙', addKnowledge: '📝', reset: '🔄'
    },
    resource: {
      gold: '🪙', energy: '⚡', ap: '🎯', food: '🍞', materials: '🪵',
      tools: '🔧', medicine: '💊', ore: '⛏️'
    },
    event: {
      weather_change: '🌤️', resource_found: '💎', social_encounter: '🤝',
      item_crafted: '🔨', rumor_spread: '🗣️', trade: '💰', festival: '🎉',
      disaster: '⚠️', player_action: '🎮', price_change: '📊',
      knowledge_conflict: '⚡', agent_goal_complete: '🏆', day_summary: '📰'
    },
    agent: {
      agent_elder: '👴', agent_blacksmith: '🔨', agent_carpenter: '🪵',
      agent_forager: '🌿', agent_scout: '🦅', agent_merchant: '💰',
      agent_teacher: '📖', agent_farmer: '🌾', agent_storyteller: '📜',
      agent_healer: '💊', agent_miner: '⛏️', agent_player: '🧳'
    },
    ui: {
      close: '✕', news: '📰', quest: '🎯', knowledge: '📚', location: '📍',
      soundOn: '🔊', soundOff: '🔇', player: '🧳', resident: '👤', info: 'ℹ️'
    }
  };
})();
