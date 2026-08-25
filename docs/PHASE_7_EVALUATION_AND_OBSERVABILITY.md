# Phase 7：評估、故障注入與可觀測性

## 階段目標

Phase 7 將 Phase 6「可以執行的 Multi-agent 流水線」轉成「可以用已知答案量化驗證的系統」。本階段建立 controlled benchmark cases、答案契約、自動評分、Specialist fault injection、aggregate metrics、summary table 與單案 audit trace。

系統仍然使用 deterministic `RuleBasedPlanner` 與合成資料，沒有 LLM、模型訓練、網路請求或真實設備連線。

## 物理意義

可以把 Phase 7 想成產線的自動測試站：

```text
已知故障與答案
      ↓
BenchmarkCase
      ↓
Multi-agent 調查流水線
      ↓
實際狀態、Evidence、工具與 Handoff
      ↓
與 BenchmarkExpectation 比對
      ↓
BenchmarkMetrics
      ↓
Summary dashboard / Detailed trace
```

Phase 6 證明流水線能運作；Phase 7 則用一組固定考題重複檢查它是否答對、是否越權、是否在資源上限內完成，以及故障時是否停在正確位置。

## 單元測試與 Benchmark 的差異

兩者都重要，但回答的問題不同：

| 方法 | 主要問題 | 範例 |
|---|---|---|
| Unit test | 一個資料型別或函式是否符合契約 | Handoff response 是否引用正確 request |
| Integration test | 多個元件組合後是否依序運作 | Coordinator 是否依序呼叫三個 Specialists |
| Controlled benchmark | 完整系統面對一批已知事故時，結果與成本是否符合答案 | 是否得到正確 Evidence、正確停止並沒有超出 calls |

Benchmark 不取代 pytest。Benchmark runner 本身也必須接受 unit 與 integration tests。

## BenchmarkCase：考題、限制與答案綁定

每個 `BenchmarkCase` 包含：

- 完整 `ScenarioDefinition`
- 每條診斷路徑的 `action_limit`
- `BenchmarkExpectation`
- 可選的 deterministic `specialist_fault`

Case 會驗證：

```text
expectation.scenario_id == scenario.scenario_id
expectation.seed        == scenario.seed
expectation.incident_id == scenario.incident.incident_id
max_tool_calls          <= action_limit
```

這避免測試輸入使用 seed 43，卻拿 seed 44 的答案來評分。

## Agent 看不到 Hidden Truth

`ScenarioDefinition` 包含 evaluator 使用的：

- `faulted_asset_id`
- `root_cause_code`
- 每個 Asset 的 hidden truth

執行 benchmark 時，Runner 只將 `ScenarioBrief` 交給 Agent：

```python
environment = SimulatedEnvironment(case.scenario)
brief = environment.brief

coordinator.run(
    incident=brief.incident,
    known_asset_ids=brief.known_asset_ids,
)
```

Diagnostic Agent 必須透過 allowlisted tools 取得 Observation，不能直接讀取答案。

## BenchmarkExpectation

答案表描述：

- 預期 Multi-agent status
- 預期 Diagnostic status
- 預期工具順序
- 預期 Evidence claims
- 預期 Safety Review outcome
- 是否應該產生 Report
- 預期 CollaborationFailure kinds
- 最大 physical tool calls
- 最大 coordination handoffs

Expectation 本身也有安全不變量。例如預期產生 Report 時，必須同時預期：

```text
Multi-agent completed
Diagnostic completed
Safety Review approved
至少一筆 Evidence claim
沒有 CollaborationFailure
```

## BenchmarkMetrics

每個案例產生以下量測：

| Metric | 說明 |
|---|---|
| `status_correct` | Workflow 與 Diagnostic status 是否符合答案 |
| `tool_sequence_correct` | 工具決策順序是否完全相同 |
| `evidence_precision` | 實際 claims 中有多少屬於預期答案 |
| `evidence_recall` | 預期 claims 中有多少被找到 |
| `evidence_grounding_correct` | Evidence 是否只引用本次實際 Observation |
| `safety_outcome_correct` | Safety Reviewer 結果是否正確 |
| `report_outcome_correct` | 應產生或不應產生 Report 的判斷是否正確 |
| `failure_signature_correct` | Failure kind 順序是否符合答案 |
| `tool_call_count` | 實際設備工具 invocation 次數 |
| `handoff_count` | Coordinator ledger 的訊息數 |
| `tool_budget_met` | Physical calls 是否未超出上限 |
| `handoff_budget_met` | Handoffs 是否未超出上限 |

只有所有 correctness、safety 與 resource gates 都通過，案例的 `passed` 才是 true。

## Precision、Recall 與正確保持沉默

Evidence claims 使用集合方式計算：

```text
precision = 正確的實際 claims / 所有實際 claims
recall    = 找到的預期 claims / 所有預期 claims
```

例子：

| Expected | Actual | Precision | Recall | 意義 |
|---|---|---:|---:|---|
| `{isolated ST-02}` | `{isolated ST-02}` | 1.0 | 1.0 | 正確找到答案 |
| `{isolated ST-02}` | `{}` | 1.0 | 0.0 | 沒亂猜，但漏掉答案 |
| `{}` | `{isolated ST-02}` | 0.0 | 1.0 | 不該下結論卻產生 false finding |
| `{}` | `{}` | 1.0 | 1.0 | 正確保持沉默 |

Shared-infrastructure 與 telemetry ambiguity 案例預期沒有 Evidence。此時安全停止且不建立 claim 是正確行為，不應被視為「Agent 沒有回答所以失敗」。

## Logical Action 與 Physical Tool Call

Phase 5 已區分 Action 和 Attempt；Phase 7 的資源指標採用 physical attempts：

```text
ACT-001: check_connectivity
  attempt 1: timed_out
  attempt 2: transient_tool_error
  attempt 3: succeeded
```

以上代表：

```text
Agent logical actions = 1
Physical tool calls   = 3
```

Benchmark 使用 physical calls，因為每次 attempt 都可能消耗設備、網路、服務配額與調查時間。

## Controlled Behavior Catalog

一般行為 catalog 有六個 cases：

| Case | Expected actions | Outcome | 主要驗證 |
|---|---:|---|---|
| Isolated ST-01 | 3 | completed / report | 故障站位置變化 |
| Isolated ST-02 | 3 | completed / report | Phase 6 主要案例 |
| Isolated ST-03 | 3 | completed / report | 故障站位置變化 |
| Shared infrastructure | 2 | safe stopped | 不得誤稱單站故障 |
| Telemetry-path ambiguity | 2 | safe stopped | 工具不足時不得猜 root cause |
| Action-budget limited | 1 | safe stopped | 資源耗盡後停止 |

三個 isolated cases 讓每台 Station 都輪流成為受影響設備，避免策略只對固定 `ST-02` 有效。

Shared-infrastructure case 的 hidden root cause 在 `GW-01`。Agent 量到 affected station 與 peer 都 unreachable 後，證據不支持 isolated-station conclusion，因此必須停止。

Telemetry-path case 中 affected station connectivity 正常但 telemetry unavailable。現有唯讀工具不足以區分 station process、設定、routing 或 gateway service，因此正確答案是保留現象並要求進一步調查。

## Specialist Failure Catalog

故障 catalog 有五個 cases：

| Case | Tool calls | Handoffs | 預期 Failure |
|---|---:|---:|---|
| Diagnostic exception | 0 | 1 | `specialist_error` |
| Diagnostic invalid response | 0 | 1 | `invalid_response` |
| Safety Reviewer exception | 3 | 3 | `specialist_error` |
| Reporter exception | 3 | 5 | `specialist_error` |
| Contradictory approval | 1 | 4 | `conflicting_result` |

Failure injection 只存在 evaluation runtime。正常 `BenchmarkCase.specialist_fault` 為 `none`，不會改寫正式 Coordinator 或 Specialist。

### 保存故障前成果

故障停止時，系統不會清空先前紀錄：

```text
Diagnostic failure
  → 沒有 Diagnostic result，只保留 investigation request

Safety Reviewer failure
  → 保留 Diagnostic actions、Observations 與 Evidence

Reporter failure
  → 保留 Diagnostic 與 approved Safety Review

Contradictory approval
  → 保留 review response，但 Coordinator 不建立 report request
```

這讓操作者能判斷哪些工作已完成，以及下一次應從哪個責任邊界恢復。

## Aggregate Result

目前完整 Phase 7 benchmark 結果：

```text
Cases: 11
Passed: 11
Failed: 0
Pass rate: 1.000
Mean evidence precision: 1.000
Mean evidence recall: 1.000
Physical tool calls: 21
Coordination handoffs: 44
All passed: yes
```

這些數字表示目前 deterministic implementation 在這 11 個 controlled cases 中完全符合既定答案。它不代表對未知真實工廠事故具有 100% 準確率，也不是模型泛化能力的統計證明。

## Summary 與 Detailed Trace

Summary table 用來快速查看整批案例：

```text
Case | Workflow | Diagnostic | Precision | Recall | Calls | Handoffs | Failure | Pass
```

Detailed trace 用來追查單一案例：

```text
Handoff ledger
  ↓
Diagnostic Actions
  ↓
Physical Attempts
  ↓
Observations
  ↓
Evidence
  ↓
Safety Review
  ↓
Report / CollaborationFailure
  ↓
Evaluation Metrics
```

Trace 不只顯示錯誤文字，也會顯示 Failure stage、role、kind、related request 與 detail。

## 手動操作

### 執行完整 11 案與 Summary

```powershell
python examples\benchmark_walkthrough.py
```

### 查看正常完成案例

```powershell
python examples\benchmark_walkthrough.py --case isolated-station-seed-43
```

### 查看 Shared-infrastructure 安全停止

```powershell
python examples\benchmark_walkthrough.py --case shared-infrastructure-seed-73
```

### 查看 Reporter failure 完整 Trace

```powershell
python examples\benchmark_walkthrough.py --case reporter-exception-seed-43
```

### 查看矛盾核准

```powershell
python examples\benchmark_walkthrough.py --case contradictory-approval-seed-43
```

### 查看所有可用 Case ID

```powershell
python examples\benchmark_walkthrough.py --help
```

### 完整測試

```powershell
python -m pytest
```

## 關鍵程式位置

| 元件 | 檔案 |
|---|---|
| Expectations 與 Metrics | `evaluation/contracts.py` |
| Controlled 與 Failure catalogs | `evaluation/catalog.py` |
| Runner、Evaluator 與 Aggregate | `evaluation/runner.py` |
| Summary 與 Detailed trace | `evaluation/rendering.py` |
| 新 Scenario builders | `simulation/catalog.py` |
| 手動展示 | `examples/benchmark_walkthrough.py` |

## 尚未實作

- 真實資料集、真實故障標註與人工 reviewer labels
- 統計信賴區間、隨機抽樣與多次 trial 分布
- Wall-clock latency、CPU、memory、Token 與 API cost
- JSON、CSV、HTML 或 database benchmark artifacts
- 非同步 message queue、heartbeat 與 network partition fault injection
- 多 Agent 同時故障與恢復 benchmark
- Trace 搜尋、篩選、時間線與視覺化 dashboard
- LLM、本機模型或遠端 API adapter
- Streamlit 操作介面與報告下載

Phase 8 將把情境選擇、benchmark summary、單案 trace、批准操作與報告展示整合到 Streamlit，形成可供面試手動展示的操作台。
