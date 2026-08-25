# Phase 5：批准、安全與故障恢復

## 階段目標

Phase 5 讓單一 Agent 從「可以執行工具」進化成「只能在安全邊界內執行工具，並且知道工具失敗後何時改道、何時停止」。

本階段加入四層保護：

1. 每個 Action 執行前都要接受風險評估。
2. Controlled write 必須等待明確的人工批准。
3. Timeout 與暫時性錯誤只能在固定次數內重試。
4. 重試耗盡後只能走未嘗試過的替代路徑，否則安全停止。

所有設備、事件與錯誤都是合成資料。Planner 仍是 deterministic rule-based policy，沒有 LLM、模型訓練、網路請求或真實設備連線。

## 完整控制流程

```text
Planner 提出 Action
        ↓
SafetyPolicy 評估風險
        ├─ ALLOW ────────────────┐
        ├─ REQUIRE_APPROVAL ──→ 等待人員決定
        │                         ├─ APPROVED ─┐
        │                         └─ REJECTED → SAFE_STOPPED
        └─ DENY ─────────────────────────────→ SAFE_STOPPED
                                  ↓
                            ActionExecutor
                                  ↓
                    bounded physical attempts
                    ├─ success → 回到 Planner
                    ├─ timeout/transient → 有限重試
                    └─ terminal failure
                                  ↓
                           RecoveryPolicy
                    ├─ one safe alternative → 重新通過 SafetyPolicy
                    └─ no safe alternative → SAFE_STOPPED
```

安全評估、批准、每次工具嘗試與復原判斷都會保存到 `InvestigationRun` 和 checkpoint。

## Safety Policy

預設的 `RiskBasedSafetyPolicy` 依 `ActionRisk` 分流：

| ActionRisk | SafetyDisposition | 執行結果 |
|---|---|---|
| `READ_ONLY` | `ALLOW` | 可以直接執行 |
| `CONTROLLED_WRITE` | `REQUIRE_APPROVAL` | 進入 `WAITING_APPROVAL` |
| `HIGH_IMPACT` | `DENY` | 不建立批准請求，直接安全停止 |

安全政策評估的是 Planner 已提出、但尚未執行的 Action。評估發生在 Action Budget 消耗與工具呼叫之前。

### 為什麼先評估再扣 Budget

Action Budget 代表實際允許嘗試的操作。等待批准不是設備操作，因此：

```text
WAITING_APPROVAL
tool calls = 0
actions_used = 0
```

核准後才消耗一步。拒絕則永遠不會執行該 Action。

## Human Approval

Controlled write 會產生：

- `SafetyAssessment`
- `ApprovalRequest`
- `TaskStatus.WAITING_APPROVAL`

外部操作者使用 `resolve_approval()` 提交決定：

```python
resolved = runner.resolve_approval(
    waiting_run,
    outcome=ApprovalOutcome.APPROVED,
    decided_by="operator-01",
    rationale="Maintenance window confirmed.",
    known_asset_ids=brief.known_asset_ids,
)
```

批准紀錄包含操作者、理由與時間。核准 Action 只能執行一次；拒絕 Action 不得出現在 Execution history。

## Action 與 Attempt 的差異

一個 Action 是 Agent 的一項邏輯決策；Attempt 是工具底層的一次實際呼叫。

```text
ACT-001: check_connectivity
  attempt 1: timed_out
  attempt 2: transient_tool_error
  attempt 3: succeeded
```

以上只消耗一個 Action Budget，但保存三筆 `ExecutionAttempt`。這避免把短暫通訊抖動誤算成三次不同的 Agent 規劃，同時保留實際操作次數。

## Retry Policy

`RetryPolicy(max_attempts=3)` 限制同一 Action 最多執行三次。

| 錯誤 | 是否重試 | 終端錯誤碼 |
|---|---|---|
| Tool timeout | 是 | `tool_timeout` |
| 暫時性工具錯誤 | 是 | `transient_tool_error` |
| 永久性工具錯誤 | 否 | `permanent_tool_error` |
| 未登錄工具 | 否 | `tool_not_allowed` |
| 不合法參數 | 否 | `invalid_parameters` |
| 風險宣告不符 | 否 | `risk_mismatch` |
| Incident scope 不符 | 否 | `incident_scope_mismatch` |

重試不使用無限迴圈，也不以隨機等待掩蓋失敗。達到上限後一定產生 terminal `ActionResult`。

## Deterministic Fault Injection

`FaultInjectingTool` 用固定腳本模擬錯誤：

```python
faulty_tool = FaultInjectingTool(
    ConnectivityTool(environment),
    (
        InjectedFault.TIMEOUT,
        InjectedFault.TRANSIENT,
    ),
)
```

前兩次呼叫依序失敗，第三次才交給原始工具。相同情境、Action 與故障腳本會得到相同 Execution history，適合測試與面試展示。

這裡的 Timeout 是合成工具主動回報的錯誤，不是作業系統層級的強制中止。未來接真實 I/O adapter 時，需要額外設計 async、subprocess 或外部服務 deadline。

## Recovery Policy

重試耗盡後，`RuleBasedRecoveryPolicy` 只對 retryable error 選擇一次未嘗試過的獨立通道：

```text
check_connectivity → read_telemetry
read_telemetry    → check_connectivity
```

替代 Action 仍會重新經過 allowlist、Safety Policy、Approval gate 與 Action Budget，Recovery Policy 不能繞過權限。

如果替代工具不存在、已使用過、原始錯誤不可復原，或替代工具也失敗，系統會 `SAFE_STOPPED`。它不會在兩個工具之間循環，也不會在證據不足時建立 Evidence。

## 稽核資料與 Checkpoint

Phase 5 的 `InvestigationRun` 新增：

- `safety_assessments`
- `approval_requests`
- `approval_decisions`
- 每筆 Execution 的 `attempts`
- `recovery_assessments`

Checkpoint schema 目前為版本 3，會保存以上紀錄並以 SHA-256 檢查 payload 完整性。

等待批准、工具失敗後暫停，以及完成 Recovery 的 Run 都能序列化與還原。舊的 schema v1、v2 尚未提供 migration。

## 手動操作

### 同時演示核准與 Recovery

```powershell
python examples\safety_recovery_walkthrough.py --scenario all --approval approve
```

應看到核准前：

```text
status before decision: waiting_approval
tool calls before decision: 0
action budget before decision: 0
```

核准後應看到工具只執行一次，接著展示兩次 Timeout 與一次替代 Telemetry Action。

### 演示人工拒絕

```powershell
python examples\safety_recovery_walkthrough.py --scenario approval --approval reject
```

拒絕後應看到：

```text
status after decision: safe_stopped
tool calls after decision: 0
action budget after decision: 0
```

### 只演示故障恢復

```powershell
python examples\safety_recovery_walkthrough.py --scenario recovery
```

最後會安全停止而不是產生沒有根據的結論：

```text
final status: safe_stopped
evidence records: 0
```

### 完整測試

```powershell
python -m pytest
```

## 尚未實作

- 真實 I/O 的 wall-clock timeout 與取消機制
- Retry backoff、jitter 與服務 rate limit
- Checkpoint v1、v2 migration
- 由設定檔載入 Safety 與 Recovery 規則
- 真實身分驗證、角色權限與批准簽章
- 多 Agent 協作與交接協定
- Benchmark、正式報告與 Streamlit UI
- LLM、本機模型或遠端 API adapter

Phase 6 將拆分協調、診斷、安全審查與報告角色，並比較多 Agent 與目前單 Agent baseline 的成本、結果和失敗模式。
