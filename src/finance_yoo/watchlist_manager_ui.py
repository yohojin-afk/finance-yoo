"""Client-side widget embedded in the dashboard page that lets the user add/remove
watchlist tickers directly from the browser, using the GitHub Contents API.

There is no backend for this static GitHub Pages site, so writes are made directly
from the browser to api.github.com using a GitHub personal access token the user
pastes in once; the token is kept only in that browser's localStorage and is never
sent anywhere except api.github.com. This is a plain (non f-string) constant because
the JS below is full of literal `{`/`}` characters that would otherwise collide with
Python string formatting.
"""

WATCHLIST_MANAGER_HTML = """
<div id="watchlist-manager" style="font-family:-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;max-width:680px;margin:0 auto 24px;padding:20px 24px;background:#fff;border:1px solid #eee;border-radius:12px;">
  <div style="font-size:14px;font-weight:700;color:#333;margin-bottom:4px;">⚙️ 관심종목 관리</div>
  <div style="font-size:12px;color:#999;margin-bottom:12px;">
    티커를 추가/삭제하면 저장소의 config/watchlist.txt가 바로 갱신되고, 다음 날 아침 실행부터 반영됩니다.
    GitHub 토큰은 이 브라우저에만 저장되며 api.github.com 외에는 전송되지 않습니다.
  </div>
  <div id="wm-token-row" style="display:flex;gap:8px;margin-bottom:12px;">
    <input id="wm-token" type="password" placeholder="GitHub 토큰 (최초 1회만 입력)" style="flex:1;min-width:0;padding:8px 10px;border:1px solid #ddd;border-radius:6px;font-size:13px;">
    <button id="wm-save-token" style="padding:8px 14px;border:none;border-radius:6px;background:#7c3aed;color:#fff;font-size:13px;cursor:pointer;white-space:nowrap;">토큰 저장</button>
    <button id="wm-clear-token" style="padding:8px 14px;border:1px solid #ddd;border-radius:6px;background:#fff;color:#666;font-size:13px;cursor:pointer;white-space:nowrap;">지우기</button>
  </div>
  <div id="wm-list" style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px;"></div>
  <div style="display:flex;gap:8px;">
    <input id="wm-new-ticker" type="text" placeholder="티커 입력 후 Enter (예: TSLA)" style="flex:1;min-width:0;padding:8px 10px;border:1px solid #ddd;border-radius:6px;font-size:13px;text-transform:uppercase;">
    <button id="wm-add" style="padding:8px 14px;border:none;border-radius:6px;background:#7c3aed;color:#fff;font-size:13px;cursor:pointer;">추가</button>
  </div>
  <div id="wm-status" style="margin-top:10px;font-size:12px;color:#888;"></div>
</div>

<script>
(function () {
  var OWNER = "yohojin-afk";
  var REPO = "finance-yoo";
  var PATH = "config/watchlist.txt";
  var TRADES_PATH = "state/trades.json";
  var WORKFLOW_FILE = "daily-briefing.yml";
  var API = "https://api.github.com";
  var TOKEN_KEY = "fy_gh_token";

  var tokenInput = document.getElementById("wm-token");
  var statusEl = document.getElementById("wm-status");
  var listEl = document.getElementById("wm-list");
  var newTickerInput = document.getElementById("wm-new-ticker");

  var defaultBranch = null;
  var currentSha = null;
  var currentTickers = [];

  function getToken() { return localStorage.getItem(TOKEN_KEY) || ""; }
  function setToken(t) { localStorage.setItem(TOKEN_KEY, t); }
  function clearToken() { localStorage.removeItem(TOKEN_KEY); }

  function setStatus(msg, isError) {
    statusEl.textContent = msg;
    statusEl.style.color = isError ? "#d64545" : "#888";
  }

  function b64EncodeUnicode(str) {
    return btoa(encodeURIComponent(str).replace(/%([0-9A-F]{2})/g, function (_, p1) {
      return String.fromCharCode(parseInt(p1, 16));
    }));
  }

  function b64DecodeUnicode(str) {
    return decodeURIComponent(atob(str.replace(/\\n/g, "")).split("").map(function (c) {
      return "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2);
    }).join(""));
  }

  function ghFetch(path, opts) {
    var token = getToken();
    if (!token) return Promise.reject(new Error("먼저 GitHub 토큰을 입력하고 저장하세요."));
    opts = opts || {};
    var headers = Object.assign({
      "Authorization": "Bearer " + token,
      "Accept": "application/vnd.github+json",
    }, opts.headers || {});
    return fetch(API + path, Object.assign({}, opts, { headers: headers }));
  }

  function getDefaultBranch() {
    if (defaultBranch) return Promise.resolve(defaultBranch);
    return ghFetch("/repos/" + OWNER + "/" + REPO).then(function (res) {
      if (!res.ok) throw new Error("저장소 정보를 가져오지 못했습니다 (" + res.status + ")");
      return res.json();
    }).then(function (data) {
      defaultBranch = data.default_branch;
      return defaultBranch;
    });
  }

  function renderList() {
    listEl.innerHTML = "";
    currentTickers.forEach(function (t) {
      var chip = document.createElement("span");
      chip.style.cssText = "display:inline-flex;align-items:center;gap:6px;background:#f3e8ff;color:#7c3aed;font-size:13px;font-weight:600;padding:6px 10px;border-radius:999px;";
      chip.appendChild(document.createTextNode(t));
      var x = document.createElement("button");
      x.textContent = "×";
      x.style.cssText = "background:none;border:none;color:#7c3aed;font-weight:700;cursor:pointer;font-size:14px;line-height:1;padding:0;";
      x.onclick = function () { removeTicker(t); };
      chip.appendChild(x);
      listEl.appendChild(chip);
    });
  }

  function loadWatchlist() {
    setStatus("불러오는 중...");
    return getDefaultBranch().then(function (branch) {
      return ghFetch("/repos/" + OWNER + "/" + REPO + "/contents/" + PATH + "?ref=" + branch);
    }).then(function (res) {
      if (!res.ok) {
        if (res.status === 401 || res.status === 403) throw new Error("토큰이 유효하지 않거나 권한이 부족합니다.");
        throw new Error("불러오기 실패 (" + res.status + ")");
      }
      return res.json();
    }).then(function (data) {
      currentSha = data.sha;
      var content = b64DecodeUnicode(data.content);
      currentTickers = content.split("\\n").map(function (l) { return l.trim(); })
        .filter(function (l) { return l && l.charAt(0) !== "#"; });
      renderList();
      setStatus("불러오기 완료.");
    }).catch(function (e) {
      setStatus(e.message, true);
    });
  }

  function saveWatchlist() {
    var lines = [
      "# 한 줄에 티커 하나. #으로 시작하는 줄은 주석.",
      "# 이 파일은 대시보드의 '관심종목 관리'에서도 수정할 수 있습니다.",
    ].concat(currentTickers).concat([""]).join("\\n");
    return getDefaultBranch().then(function (branch) {
      return ghFetch("/repos/" + OWNER + "/" + REPO + "/contents/" + PATH, {
        method: "PUT",
        body: JSON.stringify({
          message: "Update watchlist via dashboard",
          content: b64EncodeUnicode(lines),
          sha: currentSha,
          branch: branch,
        }),
      });
    }).then(function (res) {
      if (!res.ok) {
        return res.json().catch(function () { return {}; }).then(function (err) {
          throw new Error("저장 실패: " + (err.message || res.status));
        });
      }
      return res.json();
    }).then(function (data) {
      currentSha = data.content.sha;
      return true;
    });
  }

  function triggerRun() {
    return getDefaultBranch().then(function (branch) {
      return ghFetch("/repos/" + OWNER + "/" + REPO + "/actions/workflows/" + WORKFLOW_FILE + "/dispatches", {
        method: "POST",
        body: JSON.stringify({ ref: branch, inputs: { dry_run: "false" } }),
      });
    }).catch(function () { /* best-effort, ignore */ });
  }

  function addTicker() {
    var t = newTickerInput.value.trim().toUpperCase();
    if (!t) return;
    if (currentTickers.indexOf(t) !== -1) { setStatus(t + "는 이미 목록에 있습니다.", true); return; }
    currentTickers.push(t);
    renderList();
    newTickerInput.value = "";
    setStatus("저장 중...");
    saveWatchlist().then(function () {
      setStatus(t + " 추가 완료. 대시보드를 지금 바로 갱신합니다 (몇 분 소요)...");
      triggerRun();
    }).catch(function (e) {
      currentTickers = currentTickers.filter(function (x) { return x !== t; });
      renderList();
      setStatus(e.message, true);
    });
  }

  function removeTicker(t) {
    var prev = currentTickers.slice();
    currentTickers = currentTickers.filter(function (x) { return x !== t; });
    renderList();
    setStatus("저장 중...");
    saveWatchlist().then(function () {
      setStatus(t + " 삭제 완료. 대시보드를 지금 바로 갱신합니다 (몇 분 소요)...");
      triggerRun();
    }).catch(function (e) {
      currentTickers = prev;
      renderList();
      setStatus(e.message, true);
    });
  }

  document.getElementById("wm-save-token").onclick = function () {
    var v = tokenInput.value.trim();
    if (!v) return;
    setToken(v);
    tokenInput.value = "";
    loadWatchlist();
  };
  document.getElementById("wm-clear-token").onclick = function () {
    clearToken();
    currentTickers = [];
    renderList();
    setStatus("토큰을 삭제했습니다.");
  };
  document.getElementById("wm-add").onclick = addTicker;
  newTickerInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter") addTicker();
  });

  if (getToken()) {
    loadWatchlist();
  } else {
    setStatus("GitHub 토큰을 입력하고 저장하면 종목을 관리할 수 있습니다.");
  }

  var dateInputs = document.querySelectorAll(".fy-trade-date");
  for (var i = 0; i < dateInputs.length; i++) {
    dateInputs[i].valueAsDate = new Date();
  }

  function mutateTrades(ticker, statusEl, mutator, commitMessage) {
    if (!getToken()) {
      statusEl.textContent = "먼저 위에서 GitHub 토큰을 저장하세요.";
      statusEl.style.color = "#d64545";
      return Promise.resolve();
    }
    statusEl.textContent = "저장 중...";
    statusEl.style.color = "#888";

    var branchName = null;
    return getDefaultBranch().then(function (branch) {
      branchName = branch;
      return ghFetch("/repos/" + OWNER + "/" + REPO + "/contents/" + TRADES_PATH + "?ref=" + branch);
    }).then(function (res) {
      if (!res.ok) throw new Error("불러오기 실패 (" + res.status + ")");
      return res.json();
    }).then(function (data) {
      var trades = {};
      try {
        trades = JSON.parse(b64DecodeUnicode(data.content) || "{}");
      } catch (e) {
        trades = {};
      }
      mutator(trades);
      return ghFetch("/repos/" + OWNER + "/" + REPO + "/contents/" + TRADES_PATH, {
        method: "PUT",
        body: JSON.stringify({
          message: commitMessage,
          content: b64EncodeUnicode(JSON.stringify(trades, null, 2)),
          sha: data.sha,
          branch: branchName,
        }),
      });
    }).then(function (res) {
      if (!res.ok) {
        return res.json().catch(function () { return {}; }).then(function (err) {
          throw new Error("저장 실패: " + (err.message || res.status));
        });
      }
      statusEl.textContent = "저장됨. 반영 중...";
      statusEl.style.color = "#888";
      return triggerRun();
    }).catch(function (e) {
      statusEl.textContent = e.message;
      statusEl.style.color = "#d64545";
    });
  }

  function recordTrade(ticker, kind) {
    var dateEl = document.getElementById("trade-date-" + ticker);
    var priceEl = document.getElementById("trade-price-" + ticker);
    var qtyEl = document.getElementById("trade-qty-" + ticker);
    var statusEl = document.getElementById("trade-status-" + ticker);
    var price = parseFloat(priceEl.value);
    var qty = parseFloat(qtyEl.value);
    var date = dateEl.value;

    if (!date || !(price > 0) || !(qty > 0)) {
      statusEl.textContent = "날짜/가격/수량을 확인하세요.";
      statusEl.style.color = "#d64545";
      return;
    }

    var label = kind === "sell" ? "Record sell" : "Record buy";
    mutateTrades(ticker, statusEl, function (trades) {
      if (!trades[ticker]) trades[ticker] = [];
      var entry = { date: date, price: price, quantity: qty };
      if (kind === "sell") entry.type = "sell";
      trades[ticker].push(entry);
    }, label + ": " + ticker + " " + qty + "@" + price).then(function () {
      priceEl.value = "";
      qtyEl.value = "";
      statusEl.textContent = "기록 완료. 평단가는 다음 갱신에 반영됩니다 (몇 분 소요)...";
    });
  }

  window.fyAddTrade = function (ticker) { recordTrade(ticker, "buy"); };
  window.fySellTrade = function (ticker) { recordTrade(ticker, "sell"); };

  window.fyResetPosition = function (ticker) {
    var statusEl = document.getElementById("trade-status-" + ticker);
    if (!window.confirm(ticker + "의 매수/매도 기록을 모두 지울까요? 되돌릴 수 없습니다.")) return;
    mutateTrades(ticker, statusEl, function (trades) {
      delete trades[ticker];
    }, "Reset position: " + ticker).then(function () {
      statusEl.textContent = "초기화 완료. 다음 갱신에 반영됩니다 (몇 분 소요)...";
    });
  };
})();
</script>
"""
