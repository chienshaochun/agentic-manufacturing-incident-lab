# Phase 4：工作記憶、步驟預算與 Checkpoint

## 階段目標

Phase 4 讓 Phase 3 的單 Agent 從「只能在單次程序中完成」進化成具備版本化工作記憶、正式 Action budget、JSON checkpoint，以及中斷後可驗證恢復的調查系統。

所有資料仍是合成資料，所有規劃仍由 deterministic `RuleBasedPlanner` 完成。本階段沒有加入 LLM、模型訓練或真實設備連線。

## 元件關係

```text
ActionExecutionRecord history
原始 Action、Result、Observation
              ↓ projection
WorkingMemory revisions
Facts、OpenQuestions、StepBudget
              ↓ aggregate
InvestigationRun
Task、Executions、Evidence、Memory history
              ↓ serialize
Versioned JSON checkpoint + SHA-256
              ↓ load and validate
Partial InvestigationRun
              ↓ environment replay
SingleAgentRunner.resume()
```

這四層各自負責不同事情：

- `ActionExecutionRecord` 保存沒有整理過的操作事實。
- `WorkingMemory` 保存 Planner 容易使用的目前認知。
- `InvestigationRun` 保存整次任務的所有狀態。
- Checkpoint 將 Run 轉成可保存、傳遞與重新載入的格式。

## WorkingMemory

一版 `WorkingMemory` 包含：

| Field | 意義 |
|---|---|
| `task_id` / `incident_id` | 限制記憶所屬範圍 |
| `revision` | 不可變記憶版本 |
| `facts` | 已由 Observation 支持的已知事實 |
| `open_questions` | 尚未回答的調查問題 |
| `step_budget` | Action 上限、已用與剩餘次數 |
| `updated_at` | 此版本形成時間 |

### MemoryFact

`MemoryFact` 不能只有一段敘述，至少必須引用一個 Observation ID。例如：

```text
Fact: ST-02 is unreachable.
Source: INC-CONNECTIVITY-0043-OBS-001
```

這避免 Planner 把自己的推測直接記成已知事實。

### OpenQuestion

初始記憶將 Incident goal 保存為 `Q-GOAL`。每次 Action 執行前，Action rationale 會成為一個子問題；成功取得 Observation 後關閉該子問題。工具失敗時，問題保持開啟。

調查成功完成時關閉所有問題；安全停止時則保留未解問題，供恢復或人工交班使用。

## StepBudget

`StepBudget` 計算嘗試過的工具 Action，而不是成功 Observation 數。Action 一旦準備執行就消耗一步，即使之後被拒絕或失敗也不退回。

```text
action_limit = 4
actions_used = 3
actions_remaining = 1
```

預算耗盡後，Runner 會以 `SAFE_STOPPED` 結束，不允許 remaining 變成負數。

Phase 3 的暫時硬安全上限已由這個可序列化的正式 budget 取代。

## 記憶版本

正常三步調查會形成八版記憶：

```text
revision 0：建立 Q-GOAL
revision 1：準備 ACT-001、扣除一步
revision 2：記錄 OBS-001、關閉 ACT-001 問題
revision 3：準備 ACT-002、扣除一步
revision 4：記錄 OBS-002、關閉 ACT-002 問題
revision 5：準備 ACT-003、扣除一步
revision 6：記錄 OBS-003、關閉 ACT-003 問題
revision 7：完成調查、關閉 Q-GOAL
```

舊 revision 不會被修改，使測試、重播與 checkpoint 可以驗證完整歷史。

## Checkpoint 格式

> 本章保留 Phase 4 完成當時的 schema v1 格式。Phase 5 加入 Attempt、Safety、Approval 與 Recovery 紀錄後，目前 schema 已升級為 v3；最新欄位請見 Phase 5 文件。

Checkpoint 外層格式為：

```json
{
  "kind": "agentic_manufacturing_investigation",
  "schema_version": 1,
  "payload_sha256": "...",
  "run": {}
}
```

`run` 會完整保存：

- Incident
- TaskState history
- ActionExecutionRecord history
- Evidence
- WorkingMemory history

序列化使用排序穩定的 JSON。相同 Run 會產生相同 checkpoint 內容。

## 載入驗證

Checkpoint 載入分為兩層：

1. 格式層：JSON、重複 key、schema version、必要與未知欄位、型別、enum、時間與 checksum。
2. 領域層：Incident scope、Task/Memory revision、時間順序、Action/Result、Evidence/Fact reference 與 budget。

SHA-256 可以偵測意外損壞或未同步修改，但沒有祕密金鑰，因此不是防偽簽章或身分驗證，也不提供加密。

## 原子寫入

`save_checkpoint()` 先在相同目錄建立暫存檔，完整寫入、flush 與 `fsync` 後，再原子替換正式檔案。這能降低程序在寫入中途終止時留下半份正式 checkpoint 的風險。

## Pause 與 Resume

Runner 可以在指定的累計 Action 數後暫停：

```python
partial = runner.run(
    incident=brief.incident,
    known_asset_ids=brief.known_asset_ids,
    pause_after_actions=1,
)
```

Partial run 保持 `INVESTIGATING`，不建立 Evidence，也不製造額外終止狀態。

讀回後使用：

```python
resumed = runner.resume(
    restored,
    known_asset_ids=brief.known_asset_ids,
)
```

Resume 會驗證 Task 仍在調查、沒有 Evidence、WorkingMemory 存在、Policy 名稱相同，以及 Runner action limit 與 checkpoint 相同。

## 為什麼需要環境重播

Checkpoint 保存的是 Agent 狀態，不等於外部世界狀態。新的模擬環境 observation counter 從零開始，若直接 Resume 會產生重複 Observation ID。

`replay_environment_to_run()` 會在新環境依序重播既有 Action，並要求每筆 ActionResult 與 Observation 完全等於 checkpoint。只有重播成功才回傳已前進到正確位置的 Environment。

```text
same scenario + same prior actions
        ↓ replay
same results and observations
        ↓
environment ready to resume
```

不同 seed、不同 Incident 或改變過的 hidden truth 都會被拒絕。

這個方法適用 deterministic simulator。真實設備不能假設重播過去 Action 後仍回到相同狀態，需要重新查詢現況、比對版本與設計外部系統專用的 reconciliation adapter。

## 等價性驗收

本階段最重要的測試是：

```python
assert resumed_run == uninterrupted_run
```

也就是「執行一步、存檔、讀檔、重播、繼續」與「一次不中斷完成」必須得到完全相同的 Task、Executions、Observations、Memory 與 Evidence。

## 手動驗證

```powershell
python examples\single_agent_walkthrough.py
python examples\checkpoint_resume_walkthrough.py
python -m pytest
```

第一個 walkthrough 顯示完整 Agent 與最終 WorkingMemory；第二個 walkthrough 顯示 pause、save、load、replay 與 resume。

## 尚未實作

- Checkpoint 中正式的 scenario、seed 與 policy metadata
- 真實外部系統的狀態 reconciliation
- 自動 checkpoint 排程與保留政策
- 檔案鎖與多程序並行寫入控制
- Planner decision 的獨立序列化軌跡
- Timeout、retry、替代工具與故障恢復政策
- 人工批准與高風險工具
- 多 Agent 協作
- Benchmark、正式報告與 Streamlit UI
- LLM、本機模型或遠端 API adapter

Phase 5 將加入批准、安全政策與工具故障恢復，讓 Agent 不只可以中斷續跑，也能在動作有風險或工具失敗時做受控處理。
