# Phase 8：Streamlit 事件調查操作台

## 本階段概念與物理意義

前七個階段完成的是「引擎」：合成工廠、工具、單 Agent、多 Agent、安全規則、Checkpoint、故障注入與 Benchmark。Phase 8 加入的是「駕駛艙」。它不改變 Agent 的推理結果，而是讓使用者能選擇案例、啟動工作流、觀察交接與證據、比較測試結果，最後下載工程產物。

物理上可以把畫面理解成製造現場的事件控制台：Coordinator 是值班主管，Diagnostic Agent 是診斷工程師，Safety Reviewer 是獨立安全審查者，Reporter Agent 是文件工程師。畫面把四個角色的結構化訊息、實際工具嘗試與最終判斷攤開，因此使用者看到的不是聊天紀錄，而是一條可追溯的數位調查流水線。

## 新增及修改的檔案

| 檔案 | 作用 |
|---|---|
| `streamlit_app.py` | Streamlit 入口、單案操作台、Benchmark Dashboard、詳細稽核面板與下載按鈕。 |
| `presentation/models.py` | 與 UI framework 無關、不可變的畫面資料模型。 |
| `presentation/builders.py` | 將領域層的執行結果轉成卡片、表格與 trace 所需資料。 |
| `presentation/exports.py` | 產生 Markdown、JSON、CSV 與文字交付物。 |
| `requirements.txt` | 供 Streamlit Community Cloud 安裝本專案與 Streamlit。 |
| `.streamlit/config.toml` | 操作台配色與 headless server 設定。 |
| `tests/unit/test_presentation_builders.py` | 驗證領域結果轉換成 UI view model 的契約。 |
| `tests/unit/test_presentation_exports.py` | 驗證下載檔內容與欄位穩定性。 |
| `tests/integration/test_streamlit_app.py` | 用 AppTest 模擬切頁、選案例、按鈕與畫面結果。 |

## 關鍵程式碼解釋

### UI 不直接承擔 Agent 邏輯

`streamlit_app.py` 只呼叫既有的 `run_benchmark_case()` 或 `run_phase7_benchmark()`。Coordinator、Specialist、Safety 與 Report 規則仍留在領域層。這樣同一套引擎未來可接 CLI、API 或其他前端，不會因畫面改版而改變診斷結果。

### Session state 保存一次執行的結果

按下執行後，結果放入 `st.session_state`。Streamlit 每次互動都會重新執行 script；session state 讓結果在切換 tab 或下載檔案時不會消失，也避免只為了重畫畫面就重跑 Agent。

### View model 隔離 domain 與 presentation

`build_case_presentation()` 將巢狀的 workflow result 攤平成 Handoff、ActionAttempt、Evidence、Safety、Report 與 Failure。這是明確的 anti-corruption boundary：畫面不需要知道 Agent 內部類別的所有細節，領域模型也不需要依賴 Streamlit。

### Action 與 Attempt 分開

Action 是 Agent 決定要做的一個邏輯檢查；Attempt 是工具執行器真正送出的一次物理嘗試。發生 retry 時，一個 Action 會有多個 Attempt。Dashboard 顯示 physical calls 而不是只數 Action，因此不會把重試成本藏起來。

### 報告只能使用已存在的證據

Markdown 報告不是再次自由生成文字，而是由 `CasePresentation` 的 Evidence、Safety Review 與正式 Report 組合。Reporter 沒有產物時，下載報告也會明確標示沒有正式報告，不會自行補造結論。

## 如何具體操作

### 安裝與啟動

```powershell
cd C:\Users\ru03g\side_project\agentic-manufacturing-incident-lab
conda activate dev
python -m pip install -e ".[dev,ui]"
python -m streamlit run streamlit_app.py
```

瀏覽器通常會開啟 `http://localhost:8501`。

### 建議手動展示流程

1. 進入 `Incident Workbench`，先執行預設的 `isolated-station-seed-43`。
2. 在 Handoffs 看 Coordinator 如何依序要求 Diagnostic、Safety Reviewer 與 Reporter 工作。
3. 在 Actions & attempts 對照 Agent 的邏輯 Action 與實際 physical attempts。
4. 在 Evidence & safety 確認結論引用哪些 observation，以及獨立安全審查是否核准。
5. 在 Report & failures 查看 evidence-bound report。
6. 在 Raw trace 查看可重播、可稽核的完整文字紀錄。
7. 下載 Markdown、JSON 或 TXT，展示人類與機器可讀的交付方式。
8. 改跑 `reporter-exception-seed-43`，觀察 Reporter 故障被安全收斂，且既有 Evidence 與 Safety Review 沒有消失。
9. 前往 `Benchmark Dashboard`，執行全部 11 案，確認正常、模糊、資源受限與故障注入案例全部通過既定驗收閘門。

## 執行與測試

```powershell
python -m pytest
python examples\benchmark_walkthrough.py
```

`pytest` 驗證領域規則、工具邊界、單／多 Agent 流程、恢復、安全、評估、presentation 與 Streamlit 互動。Benchmark 則是產品行為層的固定答案測試；兩者用途互補。

## Streamlit Community Cloud 部署

1. 將 GitHub repository 與目標 branch 推送完成。
2. 在 Streamlit Community Cloud 建立 app。
3. Repository 選本專案，Main file path 填 `streamlit_app.py`。
4. Python 版本選 `3.12`。
5. 不需設定 API key、Secrets 或外部資料庫。

`requirements.txt` 會安裝本地 package 與 UI dependency；專案的 Python 契約固定為 `>=3.12,<3.13`。

## 尚未完成的限制

- 所有情境與 observation 都是合成資料，不代表真實產線準確率。
- Planner 是 deterministic rule-based policy，不是訓練完成的 ML model，也沒有 LLM。
- 工具只讀取模擬環境，不會連接 PLC、MES、機台、網路設備或客戶系統。
- Agent 角色以同一個 Python process 依序協作，不是跨服務、跨主機的平行 Agent runtime。
- Benchmark 的 11 個案例驗證已知邊界，不等於涵蓋所有現場故障。
- App 是教學與面試展示用 prototype，不是可直接上線的生產監控系統。

## 面試時如何解釋

可以用一句話開場：

> 這是一個不用 LLM 也能展示 Agentic AI 核心機制的製造事件調查實驗室；Agent 會根據狀態選工具、多角色交接、接受獨立安全審查，並留下可量測、可重播、可下載的證據鏈。

接著強調三點：第一，Agentic 不等於聊天或一定要有大模型，核心是狀態驅動的決策、工具使用與 feedback loop；第二，多 Agent 的價值來自責任與權限分離，而不是單純多個 prompt；第三，這個作品把故障與安全停止也當成正式輸出，因此可以驗證「出問題時是否仍然可信」。
