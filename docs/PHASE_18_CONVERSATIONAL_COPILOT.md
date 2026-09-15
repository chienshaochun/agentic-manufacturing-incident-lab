# Phase 18：多輪 Hybrid Investigation Copilot

## 本階段概念與物理意義

Phase 18 將 Phase 17 的單次問答改成真正可連續追問的本機對話區。物理上相當於工程師拿著同一份調查紀錄和助理討論：助理記得最近在談哪個候選原因，但每次回答前，系統仍會重新翻到對應的 Observation、Hypothesis 與 Evidence 頁面，不能只靠聊天記憶回答。

```text
工程師問題
    ↓
deterministic intent router
    ↓
選取與本題相關的 Hypothesis／Observation／Evidence
    ↓
最近 6 輪對話 + Grounded context
    ↓
本機 Qwen 產生結構化回答
    ↓
引用 ID 驗證 + 程式產生可驗證依據
    ↓
Streamlit chat message
```

## UI 行為

本機模式完成調查後，最下方顯示「本機 Ollama 調查對話」：

- 使用 `st.chat_message` 呈現工程師與 Copilot；
- 使用 `st.chat_input` 接收新問題；
- 每個 benchmark case 保存獨立對話，不會把不同事故混在一起；
- 可清除目前案例的對話；
- 每則回答保留問題類型、模型名稱、建議檢查與限制；
- 技術引用預設收合，需要時才展開查看原始 Observation／Evidence。

公開 Streamlit 未設定 `INCIDENT_LAB_ENABLE_OLLAMA=1`，因此不顯示對話區，上方既有調查 UI 不變。

## 問題意圖與資料選取

系統先用 deterministic keyword router 區分：

- 事故摘要；
- 假設支持；
- 假設排除；
- Evidence；
- Safety Review；
- 下一步檢查；
- 一般調查問題。

它也會辨識設定、感測器、Telemetry、網路、維護、共用基礎設施與單一工作站等主題。例如問題是「為什麼不是感測器資料過期」，送給小模型的核心內容是該 rejected Hypothesis 與它的 `contradicting_observations`，而不是整包六筆 Observation。

## 多輪上下文

每次請求最多帶入最近 6 輪、合計 6,000 字的對話。歷史只用來理解「那它呢」「第二個原因呢」等指涉；Grounded context 才是事實來源。使用者或模型在前一輪講錯時，後一輪仍必須以本次 run 的正式紀錄為準。

## Hybrid Grounding

Qwen 2B 有時會回答過短，甚至可能誤讀支持與反對關係。因此系統不只顯示模型文字：

1. 模型只能引用本題 context 中存在的完整 Observation／Evidence ID；
2. 回答下方由 Python 直接產生「程式整理的可驗證依據」；
3. 支持問題只列 `supporting_observations`；
4. 排除問題只列 `contradicting_observations`；
5. 原始引用紀錄仍可在 expander 中核對。

這使對話語氣由 LLM 提供，而證據關係仍由 deterministic domain model 提供。

## 建議 Demo

使用 `configuration-drift-seed-118`，依序詢問：

```text
為什麼支持設定版本漂移？
那為什麼不是感測器資料過期？
Safety Reviewer 為什麼核准這次結果？
目前還有哪些資訊沒有確認？
```

第一題應聚焦 `INC-SIGNAL-0118-OBS-001` 與 `INC-SIGNAL-0118-OBS-004`；第二題應聚焦 `INC-SIGNAL-0118-OBS-006`。即使模型文字省略細節，程式整理的依據也必須顯示正確關係。

## 限制

- 對話只解釋已完成的同一個調查，不會自行執行 Tool；
- 不會因聊天內容修改 Hypothesis、Evidence 或 Safety Review；
- 下一步是建議，不是已執行動作；
- 小模型仍可能誤讀自然語言，因此原始引用比模型文字更具權威；
- 目前不是一般知識聊天機器人，也不會回答 Investigation Packet 以外的設備資料；
- 對話記憶存在 Streamlit session，重啟 App 後不保留。
