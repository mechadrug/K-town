"use strict";

/* View-only campaign renderer.
 *
 * The story director lives on the server. This adapter renders only the
 * stable payload contract, so chapter content can grow without adding more
 * story branches to app-v2.js.
 */
(function () {
  var statusText = {
    current: "正在经历",
    unlocked: "已经走过",
    upcoming: "即将到来"
  };

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function render(campaign, container) {
    if (!container) return;
    if (!campaign || !campaign.title) {
      container.innerHTML = '<div class="placeholder-text">篇章信息暂时没有更新</div>';
      return;
    }

    var next = campaign.next_chapter;
    var chapters = (campaign.chapters || []).map(function (chapter) {
      var status = statusText[chapter.status] || chapter.status || "";
      return '<span class="campaign-chapter campaign-' + esc(chapter.status) + '">' +
        '第' + esc(chapter.week) + '周 · ' + esc(chapter.title) + ' · ' + esc(status) +
        '</span>';
    }).join('');

    container.innerHTML =
      '<div class="campaign-kicker">当前篇章 · 第' + esc(campaign.week) + '周</div>' +
      '<div class="campaign-title-row"><h2>' + esc(campaign.title) + '</h2>' +
      '<span class="campaign-day">本章第' + esc(campaign.day_in_chapter) + '天</span></div>' +
      '<p class="campaign-subtitle">' + esc(campaign.subtitle) + '</p>' +
      '<div class="campaign-detail"><strong>眼下的压力</strong><span>' + esc(campaign.pressure) + '</span></div>' +
      '<div class="campaign-detail"><strong>这一周想留下什么</strong><span>' + esc(campaign.objective) + '</span></div>' +
      '<div class="campaign-score-row"><span>照顾 ' + esc(campaign.scores && campaign.scores.care) + '</span>' +
      '<span>安全 ' + esc(campaign.scores && campaign.scores.safety) + '</span>' +
      '<span>信任 ' + esc(campaign.scores && campaign.scores.trust) + '</span>' +
      '<span>欢迎 ' + esc(campaign.scores && campaign.scores.welcome) + '</span></div>' +
      '<div class="campaign-chapters">' + chapters + '</div>' +
      (next ? '<div class="campaign-next">再过 ' + esc(campaign.days_until_next) + ' 天：第' + esc(next.week) + '周 · ' + esc(next.title) + '</div>' :
        '<div class="campaign-next">最后一章正在等待你的选择。</div>') +
      (campaign.final_outcome ? '<div class="campaign-outcome"><strong>' + esc(campaign.final_outcome.headline) + '</strong></div>' : '');
  }

  window.KTownCampaignView = { render: render };
}());
