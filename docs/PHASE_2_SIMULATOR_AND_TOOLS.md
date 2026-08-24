# Phase 2：模擬環境與工具系統

## 階段目標

Phase 2 建立一個不依賴 LLM、可重播且具工具邊界的調查環境。它讓後續 Planner 能在不知道答案的情況下提出 Action，並透過受控工具取得 Observation。

目前所有資料都是合成資料，所有決策都是固定程式邏輯。本階段不包含 AI 或機器學習模型。

## 元件關係

```text
ScenarioDefinition
完整情境與隱藏答案
        ↓
SimulatedEnvironment
保存演練狀態與 deterministic clock
        ↓
Diagnostic Tools
把環境量測包成標準工具介面
        ↓
ToolRegistry
驗證白名單、風險與參數
        ↓
ActionExecutor
建立 ActionResult 與執行紀錄
        ↓
Baseline Workflow
依固定 SOP 建立 Evidence 與 TaskState 歷史
```

## 資訊邊界

### Agent-visible view

`ScenarioBrief` 只包含：

- Scenario ID
- Incident
- 已知資產 ID

### Evaluator and simulator view

`ScenarioDefinition` 額外包含：

- Seed
- 每個 AssetTruth
- Faulted asset ID
- Root cause code

Agent 不應收到完整 ScenarioDefinition。Python 的底線欄位只是架構慣例而非安全沙盒，因此 runtime 必須透過依賴注入維持這項邊界。

## Deterministic replay

重播條件是：

```text
相同情境模板
+ 相同 seed
+ 相同 Action 順序
= 相同 Observation、ActionResult 與 InvestigationRun
```

Seed 決定模擬世界初始狀態，不決定 Planner 的下一個 Action，也不會出現在 Agent brief。

每次成功量測使模擬時間增加 30 秒。無效工具名稱、參數或資產不會產生 Observation，也不會推進環境計數器。

## 工具契約

每個工具透過 ToolSpec 宣告：

- 唯一 lower_snake_case 名稱
- 用途描述
- ActionRisk
- 必要與選配參數
- 參數基本型別

ToolRegistry 依序檢查工具白名單、風險、缺少參數、未知參數與參數型別，全部通過後才呼叫 handler。

目前登錄兩個唯讀工具：

| Tool | Parameter | Environment measurement |
|---|---|---|
| `check_connectivity` | `asset_id: string` | `measure_connectivity()` |
| `read_telemetry` | `asset_id: string` | `measure_telemetry()` |

## 執行結果分類

ActionExecutor 將工具回應或已知錯誤轉成正式 ActionResult：

| Condition | Status | Error code |
|---|---|---|
| Tool completed | `SUCCEEDED` | none |
| Tool not registered | `DENIED` | `tool_not_allowed` |
| Invalid parameters | `DENIED` | `invalid_parameters` |
| Risk mismatch | `DENIED` | `risk_mismatch` |
| Incident mismatch | `DENIED` | `incident_scope_mismatch` |
| Unknown asset | `FAILED` | `unknown_asset` |

未預期的 Exception 不會被全面捕捉，確保程式 bug 能讓測試失敗，而不是被錯誤包裝成正常的工具失敗。

## 固定 Baseline

`run_station_connectivity_baseline()` 依固定順序執行：

1. 量測報案工作站 connectivity。
2. 量測另一台工作站 connectivity。
3. 量測報案工作站 telemetry。
4. 檢查是否符合單一工作站故障圖樣。
5. 建立 Evidence，並完成或失敗 Task。

這是 workflow，不是 Agent。它不會根據中間 Observation 改變後續 Action，作用是提供 Phase 3 的比較基準。

Evidence confidence `0.95` 是固定規則中的合成分數，未經真實資料校準，不能解讀為真實故障機率。

## InvestigationRun

一次 baseline 結果保存為：

```text
InvestigationRun
├─ Incident
├─ TaskState history
├─ ActionExecutionRecords
│  ├─ Action
│  ├─ ActionResult
│  └─ Observations
└─ Evidence
```

Aggregate 會驗證 ID、Incident scope、Task revision、時間順序與 Evidence reference，避免產生表面成功但無法追查的紀錄。

## 手動驗證

```powershell
python examples\scenario_preview.py
python examples\environment_walkthrough.py
python examples\tool_execution_walkthrough.py
python examples\baseline_workflow.py
python -m pytest
```

## 尚未實作

- 動態 Planner 與 Agent loop
- 記憶、step budget 與 checkpoint
- Timeout、retry 與 fault injection
- 人工批准與高風險工具
- 多 Agent 協作
- Benchmark 與報告介面
- 真實資料 adapter
- LLM adapter

Phase 3 將在同一套 Environment、Registry、Executor 與 InvestigationRun 上加入動態決策，避免把固定 SOP 誤稱為 Agent。
