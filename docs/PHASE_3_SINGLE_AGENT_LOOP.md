# Phase 3：單一 Agent 決策循環

## 階段目標

Phase 3 在 Phase 2 的模擬環境與受控工具上加入可替換的 Planning Policy，並以 `SingleAgentRunner` 組合成 observe-plan-act-reflect-stop 循環。

這裡的「Agent」是能依目前狀態選擇下一個動作的軟體控制迴路，不代表系統已使用 LLM。預設 `RuleBasedPlanner` 是可重播、可測試的確定性決策策略，未經資料訓練。

## 元件關係

```text
Incident + known asset IDs
            ↓
      AgentContext ← ActionExecutionRecord history
            ↓
      PlanningPolicy
       ├─ ActionDecision ─→ ToolRegistry ─→ ActionExecutor
       │                                      ↓
       ├──────────────────────────── Observation / Result
       │
       ├─ CompleteDecision ─→ Evidence ─→ COMPLETED
       │
       └─ StopDecision ────────────────→ SAFE_STOPPED
```

每次工具執行完成後，Runner 會用累積的執行紀錄建立新的 `AgentContext`，再讓 planner 重新判斷。這個回饋迴路就是 Phase 2 固定 workflow 與 Phase 3 Agent 的主要差別。

## Planner 資訊邊界

`AgentContext` 只提供：

- Incident 與調查目標
- 已知資產 ID
- 目前 TaskState
- ToolSpec 公開描述，不包含工具 handler
- 已執行的 Action、ActionResult 與 Observation

Planner 不會收到 `ScenarioDefinition`、`AssetTruth`、`faulted_asset_id` 或 `root_cause_code`。它必須透過工具量測取得證據，不能直接讀取模擬答案。

## 決策契約

Planning Policy 每次只能回傳一種決定：

| Decision | 意義 | Runner 行為 |
|---|---|---|
| `ActionDecision` | 提議一個工具與參數 | 驗證 allowlist、建立 Action 並執行 |
| `CompleteDecision` | 證據足以支持明確 claim | 驗證 Observation ID、建立 Evidence 並完成 Task |
| `StopDecision` | 無法安全或合理地繼續 | 不建立 Evidence，將 Task 設為 `SAFE_STOPPED` |

`ActionDecision` 不允許 planner 指定 Action ID、時間或風險。這些欄位由 runtime 決定，工具風險以 ToolRegistry 的正式 ToolSpec 為準。

## RuleBasedPlanner 路徑

目前策略處理單一工作站 connectivity 異常：

```text
量測 affected station connectivity
            ↓ unreachable
量測 peer station connectivity
            ↓ reachable
量測 affected station telemetry
            ↓ unavailable
建立 isolated-station claim
```

若 affected station connectivity 正常，策略會跳過 peer comparison，直接量測 affected station telemetry。現有工具不足以繼續定位時，策略會安全停止，而不是套用原本的三步流程。

以下情況也會停止：

- 必要工具不在 allowlist
- 同一檢查已失敗，避免無限自動重試
- 找不到另一台 station 作為對照
- affected 與 peer 都無法連線
- Observation 缺少預期布林欄位
- connectivity 與 telemetry 證據互相衝突

## Runner 的防護

`SingleAgentRunner` 會額外檢查：

1. Planner 提出的工具必須存在於 runtime registry。
2. CompleteDecision 引用的 Observation 必須真的屬於本次調查。
3. Planner 未終止時，硬安全動作上限會阻止無限循環。
4. 所有 Action、Result、Observation、Evidence 與 TaskState 都保存於 `InvestigationRun`。

硬安全上限只是 Phase 3 的最後防線。Phase 4 會加入正式的任務 step budget、記憶與可序列化 checkpoint。

## 與固定 Baseline 的差異

| 特性 | Phase 2 Baseline | Phase 3 Agent |
|---|---|---|
| 動作順序 | 預先固定三步 | 每一步重新依證據規劃 |
| 中途改道 | 不會 | 會 |
| Planner 介面 | 無 | 可替換 PlanningPolicy |
| 工具結果回饋 | 最後一次判斷 | 每次執行後回到 Context |
| 終止方式 | 完成或失敗 | 完成或受控安全停止 |

規則策略本身仍是人工設計的 if/else 決策，因此不能把它描述成已訓練 AI 模型。Agentic 特性來自狀態回饋、動態工具選擇、執行循環與停止控制。

## 手動驗證

在已安裝 editable package 的 Python 3.12 環境中執行：

```powershell
python examples\single_agent_walkthrough.py
python -m pytest
```

Walkthrough 會顯示 Incident、Policy、每一步 PLAN/ACT/RESULT/OBSERVE、TaskState 歷史與最後 Evidence。

## 尚未實作

- 可序列化的 planner decision trace
- 長短期記憶、正式 step budget 與 checkpoint
- 中斷後恢復執行
- Timeout、retry 與替代工具路徑
- 人工批准與高風險工具
- 多 Agent 協作
- Benchmark、報告產生器與 Streamlit UI
- LLM、本機模型或遠端 API adapter

Phase 4 將把目前只存在於 `InvestigationRun` 的歷史整理成可恢復的任務記憶與檢查點。
