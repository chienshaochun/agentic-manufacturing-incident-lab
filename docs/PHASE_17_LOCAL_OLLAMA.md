# Phase 17：本機 Ollama 自然語言增強

## 本階段概念與物理意義

Phase 17 在原有 deterministic 調查核心之外，加上一個可選用的本機語言介面。物理上可把它理解成「工程師助理」：它能協助把口語報修內容填入標準表單，也能在調查完成後解釋紀錄，但不能碰控制盤、不能偽造量測值，也不能替安全審查簽名。

```text
公開模式
手動表單 → Hypothesis-driven investigation → Safety review → Evidence report

本機模式
自然語言 ─Ollama→ 嚴格 Intake Schema ─人工確認→ 原有 deterministic workflow
                                                       ↓
調查後問題 ─Ollama← Observation／Hypothesis／Evidence／Safety packet
```

兩種模式使用同一套程式碼。只有本機明確設定 `INCIDENT_LAB_ENABLE_OLLAMA=1` 時，Streamlit 才會附加兩個收合區塊；公開 Streamlit Cloud 不設定這個變數，因此原有 UI、調查流程與 Benchmark 不受影響。

## 新增能力

### 自然語言 Incident Intake

`OllamaIncidentTextParser` 把操作員描述轉成 Phase 16 已定義的欄位：

- `asset_id`
- `symptom_type`
- `duration_minutes`
- `network_reachable`
- `telemetry_available`
- `peer_affected`
- `parse_confidence`

Schema 禁止其他欄位，因此模型不能直接加入 `root_cause` 或處置命令。沒有明確資訊時應回傳 `null`；解析結果只會填回原有表單，必須由操作員按下「確認並執行調查」。

模型輸入與 Tool Observation 有不同證據層級：

```text
操作員文字／Ollama 解析 = reported context
Tool 回傳內容            = Observation
通過假設與安全規則       = Evidence
```

### Evidence-bound 調查問答

調查後問答只接收本次執行的 bounded packet：

- Incident ID 與設備；
- 實際執行的 Tool；
- Observation 與品質因子；
- 最終 Hypothesis 狀態及支持／反對 ID；
- 正式 Evidence；
- Safety Review；
- 已核准報告（若有）。

模型輸出的 Observation ID 與 Evidence ID 都會重新對照原始 run。引用不存在的 ID、沒有引用任何既有 Observation、加入 Schema 外欄位或回傳無效 JSON，都會被拒絕。模型回答不會寫回 `InvestigationRun`，也不會觸發 Tool。

## 安全邊界與 fallback

- Ollama client 只允許 `http://localhost`、`127.0.0.1` 或 `::1`；
- 使用固定 JSON Schema、`temperature=0` 與 bounded context；
- Intake 最多 2,000 字，問題最多 1,000 字；
- Ollama 無法連線或輸出不合法時，原有手動表單與 deterministic 調查仍可使用；
- Hypothesis 不會因模型文字而升級成 Evidence；
- 公開部署不會嘗試連接使用者電腦的 Ollama；
- 專案仍只使用合成情境，不連接真實設備。

## 本機執行

先安裝模型：

```powershell
ollama pull qwen3.5:2b-q4_K_M
```

啟用已安裝本專案的 Python 3.12 環境後執行：

```powershell
cd C:\Users\ru03g\side_project\agentic-manufacturing-incident-lab
conda activate dev
.\scripts\run_local_ollama.ps1
```

也可以不用腳本：

```powershell
$env:INCIDENT_LAB_ENABLE_OLLAMA = "1"
python -m streamlit run streamlit_app.py
```

若不設定環境變數，啟動的就是與公開部署相同的 deterministic 版本。

## 限制

- Qwen 2B 是小型量化模型，解析或說明仍可能出錯；
- 自然語言解析不會改變模擬批次的隱藏真相；
- 第一版不讓 LLM 規劃 Tool 或生成正式 Evidence；
- Streamlit Community Cloud 無法直接存取使用者電腦的 `localhost:11434`；
- Benchmark 衡量受控合成案例，不代表真實產線準確率。
