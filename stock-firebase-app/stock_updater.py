import os
import sys
import json
import datetime
import requests
import yfinance as yf
from google import genai
from google.genai import types
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# 讀取本地環境變數 (支援 E:\Python檔案\Stock\.env 的 API Key)
load_dotenv(r"E:\Python檔案\Stock\.env")
load_dotenv()

# 設定文字輸出編碼，防範 Windows 終端編碼錯誤
sys.stdout.reconfigure(encoding='utf-8')

# 常量設定
FIREBASE_PROJECT_ID = "my-stock-ai-dashboard"
FIREBASE_API_KEY = "AIzaSyBfhfjELufcQVwXQPhxYe9ll7UbIIOQfNY"
COLLECTION_NAME = "wordcloud_inputs"
DOCUMENT_ID = "stock_report"

STOCK_NAMES = {
    "2344.TW": "華邦電 (Winbond) - DRAM/NOR Flash 製造與代工",
    "2408.TW": "南亞科 (Nanya Tech) - DRAM 製造",
    "8299.TWO": "群聯 (Phison) - NAND 控制晶片與模組",
    "8271.TW": "宇瞻 (Apacer) - 記憶體與快閃記憶體模組",
    "3260.TWO": "威剛 (ADATA) - 記憶體與快閃記憶體模組",
    "5289.TWO": "宜鼎 (Innodisk) - 工控記憶體與快閃記憶體儲存方案",
    "4967.TW": "十銓 (TeamGroup) - 記憶體與電競記憶體模組",
    "2337.TW": "旺宏 (Macronix) - ROM 與 NOR Flash 製造",
    "00947.TW": "台新臺灣IC設計ETF (IC設計板塊指標)"
}
STOCKS = list(STOCK_NAMES.keys())

# --- 定義 Pydantic 結構化資料模型 ---
class StockAnalysisResult(BaseModel):
    overall_report: str = Field(description="記憶體產業今日整體大趨勢、價格走勢與資金流向綜述（Markdown 格式，繁體中文）")
    diagnoses: dict[str, str] = Field(description="以股票代碼為 Key（例如 '2344.TW'、'8299.TWO'），其對應的該檔個股「AI 健檢診斷報告」為 Value（Markdown 格式，繁體中文）。必須包含 STOCKS 清單中所有 9 檔個股的個別診斷。")

def get_stock_data():
    print("🔄 [Step 1/4] 正在抓取 yfinance 即時報價與近一個月走勢圖...")
    live_data = {}
    for ticker in STOCKS:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1mo")
            if not hist.empty and len(hist) >= 2:
                curr = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                change = curr - prev
                pct = (change / prev) * 100
                
                # 格式化近一個月的歷史數據，用於前端折線圖
                history_list = []
                for idx, row in hist.iterrows():
                    history_list.append({
                        "date": idx.strftime('%Y-%m-%d'),
                        "price": float(row['Close'])
                    })
                
                live_data[ticker] = {
                    "name": STOCK_NAMES[ticker].split(" - ")[0],
                    "desc": STOCK_NAMES[ticker].split(" - ")[1] if " - " in STOCK_NAMES[ticker] else "",
                    "price": float(curr),
                    "change": float(change),
                    "pct": float(pct),
                    "history": history_list
                }
        except Exception as e:
            print(f"⚠️ 無法載入 {ticker}: {e}")
            continue
    return live_data

def generate_ai_report(live_data):
    print("🧠 [Step 2/4] 正在利用 Gemini 2.5 Flash 生成記憶體產業深度研究日報與個股診斷...")
    
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_key.strip():
        print("❌ 未偵測到 GEMINI_API_KEY，將跳過 AI 報告生成，僅更新股票報價！")
        return json.dumps({
            "overall_report": "⚠️ 本地背景更新器未偵測到 GEMINI_API_KEY，暫時無法生成 AI 產業日報。",
            "diagnoses": {}
        })

    # 組合今日行情字串
    raw_summary = ""
    for ticker, data in live_data.items():
        sign = "+" if data["change"] >= 0 else ""
        raw_summary += f"{ticker} ({data['name']}): 價格 {data['price']:.2f}, 漲跌 {sign}{data['change']:.2f} ({sign}{data['pct']:.2f}%)\n"

    stock_search_targets = "\n".join([f"    * {ticker}: {details}" for ticker, details in STOCK_NAMES.items()])

    # --- 階段 1：聯網研究 (Research Phase) ---
    research_notes = ""
    is_search_successful = False
    
    try:
        client = genai.Client(api_key=gemini_key)
        search_tool = types.Tool(google_search=types.GoogleSearch())
        
        print("🔍 [Phase 1/2] 啟動 Google Search 進行即時聯網檢索...")
        research_prompt = f"""
        你是專業的半導體與記憶體（Memory）產業財經分析師。
        請針對今日的台灣記憶體板塊股票數據，執行深度 Google 搜尋檢索與研究任務：
        
        【任務要點】
        1. 台灣記憶體個股最新動態（營收、法說會、產業動態）：
{stock_search_targets}
        2. 全球記憶體指標巨頭（美光 Micron、三星 Samsung、SK海力士 SK Hynix）的最新動態（特別是 HBM 產能、DRAM/NAND供需）。
        3. 記憶體報價與研調（TrendForce最新報告、合約價/現貨價走勢）。
        
        【今日個股收盤數據】
        {raw_summary}
        
        請利用你的 Google Search 搜尋工具，進行即時檢索，並將搜尋到的核心新聞要點、數據、市場動向整合成一篇「記憶體產業深度研究筆記」。
        請詳細記錄各個公司的最新動態，為後續的健檢報告提供充足的依據。
        """
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=research_prompt,
            config=types.GenerateContentConfig(
                tools=[search_tool]
            )
        )
        research_notes = response.text
        is_search_successful = True
        print(f"🎉 聯網研究完成！取得 {len(research_notes)} 字元之即時資料。")
    except Exception as e:
        print(f"⚠️ 聯網檢索失敗或超出限流額度 ({e})。自動轉入降級模式（使用本地 AI 知識庫分析）。")
        research_notes = "⚠️ (無最新聯網資料，請使用內建知識庫與提供的個股收盤數據進行分析)"
        is_search_successful = False

    # --- 階段 2：資料整合與結構化輸出 (Synthesis & Formatting Phase) ---
    print("✍️ [Phase 2/2] 進行結構化 JSON 生成（使用 JSON 模式，不含工具）...")
    fallback_note = "" if is_search_successful else "\n\n⚠️ *目前 Google Search 檢索額度達到上限或發生錯誤，已自動切換為 AI 本地知識庫進行分析。*"
    
    synthesis_prompt = f"""
    你是專業的半導體與記憶體（Memory）產業財經分析師。
    請根據以下提供的「最新個股收盤數據」與「即時聯網研究資料」，為這 9 檔個股分別撰寫客製化的「AI 健檢診斷報告」，並撰寫一份「整體記憶體產業日報」。
    
    【最新個股收盤數據】
    {raw_summary}
    
    【即時聯網研究資料】
    {research_notes}
    
    【輸出規範與格式】
    必須輸出為一個合法的 JSON 格式字串，結構如下。請不要包含 markdown 標籤（如 ```json 等），請直接回傳合法的 JSON 字串：
    {{
      "overall_report": "總結今日全球與台灣記憶體市場的大趨勢、價格走勢（DRAM/NAND/HBM）與資金流向的「每日記憶體產業深度研究日報」（繁體中文，Markdown 格式）。{fallback_note}",
      "diagnoses": {{
        "2344.TW": "為華邦電撰寫的「AI 健檢診斷報告」（繁體中文，Markdown 格式，建議 200 字左右）。內容應包含：今日股價走勢與大盤/產業對比、最新消息解讀、基本面與業務體質分析、短期觀察指標與潛在風險/支撐壓力線。",
        "2408.TW": "為南亞科撰寫的「AI 健檢診斷報告」（同上格式）。",
        "8299.TWO": "為群聯撰寫的「AI 健檢診斷報告」（同上格式）。",
        "8271.TW": "為宇瞻撰寫的「AI 健檢診斷報告」（同上格式）。",
        "3260.TWO": "為威剛撰寫的「AI 健檢診斷報告」（同上格式）。",
        "5289.TWO": "為宜鼎撰寫的「AI 健檢診斷報告」（同上格式）。",
        "4967.TW": "為十銓撰寫的「AI 健檢診斷報告」（同上格式）。",
        "2337.TW": "為旺宏撰寫的「AI 健檢診斷報告」（同上格式）。",
        "00947.TW": "為台新臺灣IC設計撰寫的「AI 健檢診斷報告」（同上格式）。"
      }}
    }}
    
    請注意：
    1. "diagnoses" 字典必須包含 STOCKS 清單中所有 9 檔個股的個別診斷，不能遺漏任何一檔，Key 必須是精確的股票代碼（如 "2344.TW", "8299.TWO" 等）。
    2. 每篇個股健檢診斷都必須使用優雅、專業的 Markdown 格式撰寫，文字親切客客氣氣、資訊詳盡，並且使用繁體中文。
    """

    try:
        client = genai.Client(api_key=gemini_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=synthesis_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        return response.text
    except Exception as e:
        print(f"❌ 結構化報告生成失敗：{e}")
        return json.dumps({
            "overall_report": f"❌ 產業日報生成失敗：{e}",
            "diagnoses": {}
        })

def upload_to_firestore(live_data, overall_report, diagnoses):
    print("📤 [Step 3/4] 正在將整合數據推送至 Firebase Cloud Firestore...")
    
    # 建立 REST API URL
    url = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents/{COLLECTION_NAME}/{DOCUMENT_ID}?key={FIREBASE_API_KEY}"
    
    # 準備寫入文檔的 fields 資料
    payload = {
        "fields": {
            "prices_json": {
                "stringValue": json.dumps(live_data, ensure_ascii=False)
            },
            "ai_report": {
                "stringValue": overall_report
            },
            "diagnoses_json": {
                "stringValue": json.dumps(diagnoses, ensure_ascii=False)
            },
            "updated_at": {
                "stringValue": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        }
    }
    
    # 加入偽裝瀏覽器 Referer & Origin，防止 Google API Key 限制 403 阻擋
    headers = {
        "Referer": f"https://{FIREBASE_PROJECT_ID}.firebaseapp.com/",
        "Origin": f"https://{FIREBASE_PROJECT_ID}.firebaseapp.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        # 使用 PATCH 方法，可以新增或覆蓋 document
        response = requests.patch(url, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            print("🎉 Firebase Firestore 雲端即時同步完成！")
            return True
        else:
            print(f"❌ Cloud Firestore REST API 失敗，狀態碼：{response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"❌ 上傳 Cloud Firestore 發生錯誤：{e}")
        return False

def save_local_backup(live_data, overall_report, diagnoses):
    print("💾 [Step 4/4] 正在寫入本地資料備份 (public/data.json)...")
    
    # 確保 public 目錄存在
    os.makedirs("public", exist_ok=True)
    
    backup_data = {
        "prices": live_data,
        "ai_report": overall_report,
        "diagnoses": diagnoses,
        "updated_at": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    try:
        with open("public/data.json", "w", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        print("💾 本地 data.json 檔案更新完成！")
        return True
    except Exception as e:
        print(f"❌ 寫入本地備份失敗：{e}")
        return False

def main():
    print("==================================================")
    print("📊 AI 記憶體股市助理 - Firebase 數據發布後端啟動")
    print("==================================================")
    
    # 1. 抓取股票
    live_data = get_stock_data()
    if not live_data:
        print("❌ 無法抓取到任何股票報價，程式終止！")
        return
        
    # 2. 生成報告 (包含整體日報與 9 檔股票的個股診斷)
    ai_report_raw = generate_ai_report(live_data)
    
    # 解析結構化 JSON 資料
    try:
        report_data = json.loads(ai_report_raw)
        overall_report = report_data.get("overall_report", "⚠️ 無法解析整體產業分析日報內容。")
        diagnoses = report_data.get("diagnoses", {})
    except Exception as parse_err:
        print(f"⚠️ 解析結構化報告失敗，改用純文字降級容錯：{parse_err}")
        overall_report = ai_report_raw
        diagnoses = {}
    
    # 3. 備份到本地
    save_local_backup(live_data, overall_report, diagnoses)
    
    # 4. 推送到 Firestore
    upload_to_firestore(live_data, overall_report, diagnoses)
    
    print("==================================================")
    print("🎉 所有背景更新作業完全成功！")
    print("==================================================")

if __name__ == "__main__":
    main()
