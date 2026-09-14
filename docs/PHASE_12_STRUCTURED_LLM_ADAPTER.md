# Phase 12：可插拔的結構化 LLM Planner

## 本階段概念與物理意義

LLM 適合閱讀非結構化描述並提出下一步，但不應直接取得工廠控制權。本階段把 LLM 放在「提案者」的位置：它只能回傳一份結構化決策，真正的工具授權、參數驗證、風險分類與 Evidence 建立仍由 deterministic runtime 負責。

這就像現場工程師可以提出「下一步量測網路」，但必須由既有作業規範確認該儀器可用、參數合理、操作風險符合權限後才執行。

## 決策契約

`StructuredLLMPlanner` 接受 provider-neutral 的 callable，因此核心程式不依賴任何特定 LLM SDK。輸入只包含 Incident 公開內容、Tool schema、Action budget、已取得的 Observation 與 Hypothesis；不會包含 simulator 的 `root_cause_code`。

LLM 只能提出三種結果：

- `action`：指定 allowlist 內的 Tool、符合 schema 的 parameters 與理由。
- `complete`：指定目前已是 `supported` 的 Hypothesis ID；claim、Observation IDs 與 confidence 由系統紀錄取得，不能由 LLM 自行捏造。
- `stop`：使用既定的 `StopReason` 安全停止。

若 provider timeout、JSON 結構錯誤、Tool 越權、參數錯誤、重複呼叫或引用不存在的 Hypothesis，adapter 會 fail closed，改由傳入的 deterministic Planner 決策。

## 為何不需要 API Key

公開 App 仍使用 deterministic Planner，確保免費部署可重播。`examples/structured_llm_walkthrough.py` 用錄製的結構化回覆模擬 provider 邊界；它測的是契約、驗證和 fallback，不是假裝真的呼叫模型。

```powershell
python examples/structured_llm_walkthrough.py --mode replay
python examples/structured_llm_walkthrough.py --mode invalid
python -m pytest tests/unit/test_structured_llm_planner.py
```

`replay` 會走過合法的六步調查；`invalid` 每次故意要求不存在的 `shutdown_factory`，可看到系統拒絕提案並由 deterministic Planner 完成調查。

## 安全邊界與限制

- Adapter 本身不是模型，也沒有訓練模型；它是模型與 Agent runtime 之間的防護契約。
- 尚未接入任何線上 provider、API key、prompt management 或 token accounting。
- deterministic fallback 能維持已知案例可用，但不能消除 LLM 對未知案例的推理風險。
- 若未來接入真實 Tool，仍需身份驗證、網路隔離、人工批准、稽核儲存與現場 E-stop 等外部控制。

