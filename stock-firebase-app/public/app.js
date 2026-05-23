// Firebase Configuration (與 wordcloud-app 共享相同專案與憑證)
const firebaseConfig = {
  projectId: "my-stock-ai-dashboard",
  appId: "1:257256401647:web:9db61fe50e7f22274cc91a",
  storageBucket: "my-stock-ai-dashboard.firebasestorage.app",
  apiKey: "AIzaSyBfhfjELufcQVwXQPhxYe9ll7UbIIOQfNY",
  authDomain: "my-stock-ai-dashboard.firebaseapp.com",
  messagingSenderId: "257256401647",
  projectNumber: "257256401647"
};

// 初始化 Firebase
firebase.initializeApp(firebaseConfig);
const db = firebase.firestore();
const collectionName = "wordcloud_inputs";
const documentId = "stock_report";

// DOM 元素
const connStatusEl = document.getElementById("conn-status");
const updateTimeEl = document.getElementById("update-time");
const tickerGridEl = document.getElementById("ticker-grid");
const reportContentEl = document.getElementById("report-content");
const chartTitleEl = document.getElementById("chart-title");
const canvasCtx = document.getElementById("price-chart").getContext("2d");
const btnToggleReport = document.getElementById("btn-toggle-report");
const reportTitleEl = document.getElementById("report-title");

// 全域變數
let stockData = {}; // 存放所有股票資料的 Map
let activeTicker = ""; // 當前高亮選中的股票代碼
let chartInstance = null; // Chart.js 圖表實例
let overallReport = ""; // 整體產業日報
let diagnosesData = {}; // 所有個股診斷
let reportMode = "stock"; // "stock" (個股診斷) 或 "overall" (整體日報)

// 1. 初始化讀取：讀取專案部署的最新盤中數據與 AI 日報
function initDataLoad() {
  console.log("🔄 正在讀取儲存庫最新股市與日報數據 (data.json)...");
  loadLocalData();
}

async function loadLocalData() {
  try {
    const response = await fetch("data.json?t=" + new Date().getTime());
    if (response.ok) {
      const data = await response.json();
      console.log("🎉 數據載入成功！");
      
      const formattedData = {
        prices_json: JSON.stringify(data.prices),
        ai_report: data.ai_report,
        diagnoses_json: JSON.stringify(data.diagnoses || {}),
        updated_at: data.updated_at
      };
      updateUI(formattedData, true);
    } else {
      showError("❌ 無法讀取資料檔案 (data.json)，請運行 updater 後再次部署。");
    }
  } catch (err) {
    console.error("讀取資料檔案出錯：", err);
    showError("❌ 載入資料檔案失敗：" + err.message);
  }
}

// 3. 解析數據並重繪全網頁 UI
function updateUI(data, isOnline = true) {
  try {
    const prices = JSON.parse(data.prices_json);
    const aiReportMarkdown = data.ai_report;
    const diagnoses = data.diagnoses_json ? JSON.parse(data.diagnoses_json) : {};
    const updatedAt = data.updated_at;
    
    stockData = prices;
    overallReport = aiReportMarkdown;
    diagnosesData = diagnoses;
    
    // 更新連線狀態文字
    if (isOnline) {
      connStatusEl.innerHTML = `<i class="fa-solid fa-cloud-bolt text-glow-green"></i> 雲端同步連線中`;
      connStatusEl.style.background = "rgba(16, 185, 129, 0.08)";
      connStatusEl.style.color = "#10b981";
      connStatusEl.style.borderColor = "rgba(16, 185, 129, 0.2)";
    }
    
    // 更新最後刷新時間
    updateTimeEl.textContent = `最後更新：${updatedAt}`;
    
    // 渲染股票卡片清單
    renderStockCards(prices);
    
    // 自動高亮第一張卡片並繪製圖表 (如果是首次載入)
    const tickers = Object.keys(prices);
    if (tickers.length > 0) {
      if (!activeTicker || !prices[activeTicker]) {
        activeTicker = tickers[0];
      }
      highlightActiveCard(activeTicker);
      drawHistoryChart(activeTicker);
    }
    
    // 渲染 AI 報告與個股健檢診斷
    renderAIReport();
    
  } catch (err) {
    console.error("解析資料更新 UI 失敗：", err);
    showError("❌ 解析雲端資料失敗：" + err.message);
  }
}

// 3-1. 渲染 AI 報告與健檢診斷 (支援雙模式切換)
function renderAIReport() {
  if (!stockData || !stockData[activeTicker]) return;
  
  const stockName = stockData[activeTicker].name;
  
  if (reportMode === "stock") {
    // 顯示選中的個股診斷
    reportTitleEl.innerHTML = `<i class="fa-solid fa-robot icon-margin text-glow-purple"></i> 🤖 ${stockName} AI 深度健檢診斷`;
    btnToggleReport.textContent = "📋 查看整體產業日報";
    
    const diagnosis = diagnosesData[activeTicker];
    if (diagnosis) {
      reportContentEl.innerHTML = marked.parse(diagnosis);
    } else {
      reportContentEl.innerHTML = `<p style="color: #cbd5e1; padding: 10px 0;">暫無 ${stockName} (${activeTicker}) 的個股 AI 診斷書。請執行後台 updater 生成數據檔案。</p>`;
    }
  } else {
    // 顯示整體產業日報
    reportTitleEl.innerHTML = `<i class="fa-solid fa-robot icon-margin text-glow-purple"></i> 🤖 記憶體產業分析研究日報`;
    btnToggleReport.textContent = `🔍 返回 ${stockName} 診斷`;
    
    if (overallReport) {
      reportContentEl.innerHTML = marked.parse(overallReport);
    } else {
      reportContentEl.innerHTML = `<p style="color: #cbd5e1; padding: 10px 0;">暫無整體產業日報內容。</p>`;
    }
  }
}

// 4. 動態繪製股票卡片 grid
function renderStockCards(prices) {
  tickerGridEl.innerHTML = "";
  
  Object.entries(prices).forEach(([ticker, data]) => {
    const isUp = data.change >= 0;
    const changeSign = isUp ? "+" : "";
    const cardClass = isUp ? "stock-up" : "stock-down";
    const colorClass = isUp ? "color-up" : "color-down";
    
    const card = document.createElement("div");
    card.className = `stock-card ${cardClass}`;
    card.id = `card-${ticker.replace('.', '-')}`;
    
    card.innerHTML = `
      <div class="stock-card-top">
        <span class="stock-name">${data.name}<small class="stock-ticker">${ticker}</small></span>
        <span class="stock-price ${colorClass}">${data.price.toFixed(2)}</span>
      </div>
      <div class="stock-card-bottom">
        <span class="stock-desc">${data.desc}</span>
        <span class="stock-change ${colorClass}">${changeSign}${data.change.toFixed(2)} (${changeSign}${data.pct.toFixed(2)}%)</span>
      </div>
    `;
    
    // 點擊事件：切換選中狀態並重新繪製歷史圖表與連動 AI 診斷書
    card.addEventListener("click", () => {
      activeTicker = ticker;
      highlightActiveCard(ticker);
      drawHistoryChart(ticker);
      renderAIReport();
    });
    
    tickerGridEl.appendChild(card);
  });
}

// 5. 高亮選中的卡片
function highlightActiveCard(ticker) {
  // 移除所有卡片的高亮
  document.querySelectorAll(".stock-card").forEach(el => {
    el.classList.remove("stock-active");
  });
  
  // 為當前點擊的卡片加入高亮樣式
  const activeCard = document.getElementById(`card-${ticker.replace('.', '-')}`);
  if (activeCard) {
    activeCard.classList.add("stock-active");
  }
}

// 6. 使用 Chart.js 繪製近一個月歷史價格折線圖
function drawHistoryChart(ticker) {
  const data = stockData[ticker];
  if (!data || !data.history || data.history.length === 0) return;
  
  const history = data.history;
  const labels = history.map(h => h.date);
  const prices = history.map(h => h.price);
  
  // 更新圖表標題
  chartTitleEl.innerHTML = `<i class="fa-solid fa-chart-area icon-margin text-glow-cyan"></i> ${data.name} (${ticker}) 近一個月股價走勢圖`;
  
  // 銷毀舊有的 Chart 實例，防止 Canvas 重疊渲染 Bug
  if (chartInstance) {
    chartInstance.destroy();
  }
  
  const isUp = data.change >= 0;
  const glowColor = isUp ? 'rgba(239, 68, 68, 0.8)' : 'rgba(16, 185, 129, 0.8)'; // 漲紅跌綠
  const areaBg = isUp ? 'rgba(239, 68, 68, 0.03)' : 'rgba(16, 185, 129, 0.03)';
  
  // 建立新 Chart 實例 (使用精美炫彩霓虹效果)
  chartInstance = new Chart(canvasCtx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: '收盤價 (元)',
        data: prices,
        borderColor: glowColor,
        borderWidth: 2.5,
        backgroundColor: areaBg,
        fill: true,
        tension: 0.2, // 平滑折線
        pointBackgroundColor: glowColor,
        pointBorderColor: 'rgba(255,255,255,0.1)',
        pointRadius: 3,
        pointHoverRadius: 6,
        hoverBorderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false // 不顯示上方標籤
        },
        tooltip: {
          backgroundColor: 'rgba(15, 23, 42, 0.95)',
          titleColor: '#e2e8f0',
          bodyColor: '#38bdf8',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
          padding: 12,
          displayColors: false,
          callbacks: {
            label: function(context) {
              return `收盤價：${context.parsed.y.toFixed(2)} 元`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: {
            color: 'rgba(255, 255, 255, 0.03)'
          },
          ticks: {
            color: '#64748b',
            font: { size: 10 }
          }
        },
        y: {
          grid: {
            color: 'rgba(255, 255, 255, 0.03)'
          },
          ticks: {
            color: '#64748b',
            font: { size: 10 },
            callback: function(value) {
              return value.toFixed(2) + ' 元';
            }
          }
        }
      }
    }
  });
}

// 7. 錯誤渲染器
function showError(message) {
  tickerGridEl.innerHTML = `<div style="grid-column: 1/-1; color: #ef4444; text-align: center; padding: 20px;">${message}</div>`;
  reportContentEl.innerHTML = `<div style="color: #ef4444; text-align: center; padding: 20px;">${message}</div>`;
}

// 頁面加載完成後啟動數據加載與點擊事件註冊
window.addEventListener("DOMContentLoaded", () => {
  initDataLoad();
  
  // 註冊 AI 報告雙模式切換按鈕點擊事件
  btnToggleReport.addEventListener("click", () => {
    reportMode = reportMode === "stock" ? "overall" : "stock";
    renderAIReport();
  });
});
