/**
 * chorei-neta LINE Bot v6 (2026-09-12)
 * v5からの変更点:
 *   - hidden:true のネタを配信対象から除外（月次事実監査で非表示化されたもの）
 *
 * このコードは GAS Web IDE に貼り付けて保存してください。
 * v5 から v6 への差分は pickRandomNeta() 冒頭の 1行追加のみです。
 */
const PAGE_URL   = "https://shirakei68-lgtm.github.io/chorei-neta/chorei-neta.html";
const DATA_URL   = "https://shirakei68-lgtm.github.io/chorei-neta/neta_data.js";
const LINE_TOKEN = "4fsLxjrikDw4iWPFc7WSEYk2igKbiz8ZYwaGh5zTNSpmIxabijU0RanEcZ/6ZsYjR5LbdN4pv6v8QOlGDVvjIrhRd0txeZMxLkWcKRh7AJMFqosSIXXPbXQiE69kajSjhEkke3t+fYomh56SFIBduAdB04t89/1O/w1cDnyilFU=";

const WEATHER_PREF_BY_MONTH = {
  1:  ["冬・冷え込み"], 2: ["冬・冷え込み"],
  3:  ["春・気温差","花粉"], 4: ["春・気温差","花粉"],
  5:  ["春・気温差","夏・猛暑"],
  6:  ["梅雨・雨天","夏・猛暑"], 7: ["夏・猛暑","梅雨・雨天"],
  8:  ["夏・猛暑","台風・大雨"], 9: ["夏・猛暑","台風・大雨"],
  10: ["秋・涼しい"], 11: ["冬・冷え込み"], 12: ["冬・冷え込み"]
};
const RECENT_HISTORY_KEY = "recent_sent_ids";
const RECENT_HISTORY_SIZE = 10;

function fetchNeta() {
  const resp = UrlFetchApp.fetch(DATA_URL + "?t=" + Date.now(), {muteHttpExceptions: true});
  const text = resp.getContentText();
  const startIdx = text.indexOf("[");
  const endIdx = text.lastIndexOf("]");
  return JSON.parse(text.substring(startIdx, endIdx + 1));
}

function pickRandomNeta(data) {
  // 0) hidden:true を除外（★v6追加★ 月次事実監査で非表示化されたネタを配信しない）
  data = data.filter(n => !n.hidden);
  // 1) 今月に該当するネタで絞り込み
  const now = new Date();
  const month = now.getMonth() + 1;
  let pool = data.filter(n => (n.months || []).includes(month));
  if (pool.length === 0) pool = data;
  // 2) 天気タグ優先絞り込み
  const prefer = WEATHER_PREF_BY_MONTH[month] || [];
  const weatherPool = pool.filter(n =>
    (n.tags && n.tags.weather || []).some(w => prefer.includes(w))
  );
  if (weatherPool.length >= 3) pool = weatherPool;
  // 3) 直近送信済みを除外
  const props = PropertiesService.getScriptProperties();
  const recent = JSON.parse(props.getProperty(RECENT_HISTORY_KEY) || "[]");
  let usable = pool.filter(n => !recent.includes(n.id));
  if (usable.length === 0) usable = pool;
  // 4) ランダム選出
  const chosen = usable[Math.floor(Math.random() * usable.length)];
  // 5) 送信履歴を更新
  recent.unshift(chosen.id);
  props.setProperty(RECENT_HISTORY_KEY, JSON.stringify(recent.slice(0, RECENT_HISTORY_SIZE)));
  return chosen;
}

function dailyPush() {
  try {
    const data = fetchNeta();
    if (!data || data.length === 0) { console.log("[dailyPush] no neta"); return; }
    const neta = pickRandomNeta(data);
    if (!neta) { console.log("[dailyPush] no neta selected"); return; }
    const plainBody = (neta.body || "").replace(/<[^>]+>/g, "").replace(/\s+/g," ").trim();
    const trimmed = plainBody.length > 400 ? plainBody.slice(0,400) + "…" : plainBody;
    const msg = `おはようございます！今日の朝礼ネタです。\n\n📌 ${neta.title}\n【${neta.category}】\n\n${trimmed}\n\n🔗 全文はこちら：\n${PAGE_URL}`;
    UrlFetchApp.fetch("https://api.line.me/v2/bot/message/broadcast", {
      method: "post",
      contentType: "application/json",
      headers: { "Authorization": "Bearer " + LINE_TOKEN },
      payload: JSON.stringify({ messages: [{ type: "text", text: msg }] }),
      muteHttpExceptions: true
    });
    console.log("[dailyPush] sent: " + neta.id + " " + neta.title);
  } catch (e) {
    console.log("[dailyPush] ERROR: " + e.message);
  }
}

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents);
    for (const ev of body.events || []) {
      if (ev.type !== "message" || ev.message.type !== "text") continue;
      const data = fetchNeta();
      const neta = pickRandomNeta(data);
      const plainBody = (neta.body || "").replace(/<[^>]+>/g, "").replace(/\s+/g," ").trim();
      const trimmed = plainBody.length > 400 ? plainBody.slice(0,400) + "…" : plainBody;
      const reply = `📌 ${neta.title}\n【${neta.category}】\n\n${trimmed}\n\n🔗 ${PAGE_URL}`;
      UrlFetchApp.fetch("https://api.line.me/v2/bot/message/reply", {
        method: "post", contentType: "application/json",
        headers: { "Authorization": "Bearer " + LINE_TOKEN },
        payload: JSON.stringify({ replyToken: ev.replyToken, messages: [{ type: "text", text: reply }] }),
        muteHttpExceptions: true
      });
    }
  } catch (e) { console.log("[doPost] ERROR: " + e.message); }
  return ContentService.createTextOutput("OK");
}
