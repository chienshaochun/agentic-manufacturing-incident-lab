# Phase 6：多 Agent 協作與比較

## 階段目標

Phase 6 將原本由單一 Agent 完成的調查，擴充成四個責任明確的角色：Coordinator、Diagnostic、Safety Reviewer 與 Reporter。角色之間只能使用結構化 handoff 交換工作，Coordinator 負責統一調度、驗證回覆與控制流程是否能前進。

本階段的 Multi-agent 不會讓診斷工具自動變多，也不會憑空提高推理能力。它增加的是職責隔離、獨立覆核、失敗邊界、稽核紀錄與正式報告。

系統仍使用 deterministic `RuleBasedPlanner`，沒有 LLM、模型訓練、網路請求或真實設備連線。

## 物理意義

可以把 Phase 6 想成一條受控的事件調查流水線：

```text
Incident / 調查目標
          ↓
      Coordinator
          ↓
  Diagnostic Agent ──量測──→ Read-only tools
          ↓
      Coordinator
          ↓
 Safety Reviewer ──覆核──→ 授權、動作、證據
          ↓ approved
      Coordinator
          ↓
   Reporter Agent ───────→ Evidence-bound report
```

Diagnostic 像檢測工程師，Safety Reviewer 像獨立品管，Reporter 像交班報告人員，Coordinator 則像負責派工與放行的現場主管。

## 為什麼採用中心化協作

目前所有需求與結果都必須通過 Coordinator：

```text
Diagnostic → Coordinator → Safety Reviewer
Safety Reviewer → Coordinator → Reporter
```

而不是讓角色彼此自由對話：

```text
Diagnostic ↔ Safety Reviewer ↔ Reporter
```

中心化設計帶來以下特性：

1. 每個角色只接收完成自己工作所需的資料。
2. Diagnostic 不能自行跳過 Safety Reviewer。
3. Reporter 不能使用未核准的診斷結果。
4. Coordinator 可以保存完整工作順序與失敗位置。
5. 相同 Incident 可以確定性重播與測試。

代價是 Coordinator 會成為單一協調點，而且目前角色只能依序執行。這是為了先把責任與安全邊界做清楚，再考慮平行執行或去中心化協作。

## 角色與權限

| 角色 | 主要責任 | 可使用的設備工具 | 不允許的工作 |
|---|---|---|---|
| `Coordinator` | 拆解需求、派工、驗證回覆、決定是否前進 | 無 | 不自行量測或建立診斷證據 |
| `Diagnostic` | 規劃檢查、呼叫工具、建立 Observation 與 Evidence | 僅 read-only registry | 不核准自己的結果、不產生正式報告 |
| `Safety Reviewer` | 獨立檢查授權、執行紀錄與證據完整性 | 無 | 不呼叫設備工具、不修改診斷結果 |
| `Reporter` | 將已核准紀錄整理成 evidence-bound report | 無 | 不接受未核准或無證據的調查 |

`DiagnosticAgent` 建立時會檢查 registry；只要其中包含非 `READ_ONLY` 工具就會拒絕啟動。Reviewer 和 Reporter 沒有 ToolRegistry，因此在結構上不能對設備採取行動。

## 結構化 Handoff

`AgentHandoff` 是角色間唯一的正式訊息，包含：

- `handoff_id`
- `incident_id`
- `kind`
- `sender` 與 `recipient`
- `purpose`
- `created_at`
- `action_ids` 與 `observation_ids`
- response 使用的 `in_reply_to`

正常完成流程固定有六次 handoff：

| 順序 | Kind | 路徑 | 物理意義 |
|---:|---|---|---|
| 1 | `investigation_request` | Coordinator → Diagnostic | 派發調查工作 |
| 2 | `diagnostic_result` | Diagnostic → Coordinator | 交回檢測紀錄與證據 |
| 3 | `safety_review_request` | Coordinator → Safety Reviewer | 要求獨立覆核 |
| 4 | `safety_review_result` | Safety Reviewer → Coordinator | 核准、要求注意或拒絕 |
| 5 | `report_request` | Coordinator → Reporter | 只將核准結果送去製作報告 |
| 6 | `report_result` | Reporter → Coordinator | 交回 evidence-bound report |

`HandoffLedger` 是 immutable ordered ledger，會驗證：

- 所有訊息屬於同一 Incident。
- Handoff ID 不重複。
- 時間必須向前移動。
- Response 必須指向較早的正確 request。
- Response 路徑必須反轉原 request 的 sender 與 recipient。
- 一個 request 最多只能收到一次 response。

因此 ledger 不只是 log，而是帶有流程不變量的正式協作紀錄。

## Diagnostic Agent

Diagnostic Specialist 內部仍使用 Phase 3 到 Phase 5 建立的 `SingleAgentRunner`：

```text
RuleBasedPlanner
      ↓
SingleAgentRunner
      ↓
Safety Policy / Recovery Policy / ToolRegistry
      ↓
InvestigationRun
```

它完成調查後，不會只回傳一句文字，而是回傳 `DiagnosticWorkProduct`：

- 完整 `InvestigationRun`
- `diagnostic_result` handoff
- 所有 Action ID
- 所有 Observation ID

Work product 會驗證 handoff 是否引用本次 Run 的每一個 Action 與 Observation。

## Safety Reviewer

Safety Reviewer 不重新執行診斷，而是獨立檢查既有紀錄：

- 所有執行 Action 是否經過安全政策評估。
- 需要人工批准的 Action 是否真的取得批准。
- 被拒絕的 Action 是否沒有執行。
- Completed Run 是否具有 Evidence。
- Evidence 是否引用實際收集到的 Observation。

審查結果分為：

| Outcome | 意義 | Coordinator 行為 |
|---|---|---|
| `approved` | 執行與證據完整 | 可以進入 Reporter |
| `requires_attention` | 紀錄可以保留，但不足以產生結論 | 安全停止，不產生報告 |
| `rejected` | 發現不應接受的安全違規 | 安全停止，不產生報告 |

Reviewer 不會修改 Diagnostic 的結果。它只能對原始紀錄作出獨立 disposition。

## Reporter 與 Evidence-bound Report

Reporter 只接受：

1. `report_request`
2. 同一 Incident 的 Diagnostic 結果
3. `approved` Safety Review
4. 完整 Action、Observation 與 Evidence references

產生的 `IncidentReport` 包含：

- Report ID 與 Incident ID
- Title、executive summary 與 conclusion
- 所有 Action ID
- 所有 Observation ID
- 所有 Evidence ID
- 產生時間

Reporter 不能新增另一個沒有 Observation 支持的診斷主張；報告 conclusion 必須來自 Diagnostic 已建立的 Evidence。

## 正常安全停止與協作故障

兩種停止都使用 `MultiAgentStatus.SAFE_STOPPED`，但原因不同：

| 類型 | 範例 | `failures` | 物理意義 |
|---|---|---:|---|
| 正常安全停止 | Action budget 不足，Reviewer 回傳 `requires_attention` | 0 | 品管正常運作並阻止證據不足的產品出貨 |
| 協作故障 | Agent exception、錯誤格式、矛盾核准 | 1 | 流水線工作站或交接本身發生故障 |

協作故障由 `CollaborationFailure` 記錄：

- 發生階段：`diagnostic`、`safety_review`、`reporting`
- 失敗角色
- 失敗種類
- 錯誤內容
- 對應的 request ID
- 發生時間

目前的失敗種類：

| Kind | 說明 |
|---|---|
| `specialist_error` | Specialist 呼叫期間拋出 Python exception |
| `invalid_response` | 回傳型別或 handoff 不符合契約 |
| `conflicting_result` | Reviewer 核准未完成或沒有證據的診斷 |

Coordinator 會保留故障前已完成的 work products 與 ledger。如果 request 尚未收到 response，它必須由對應的 failure 解釋，避免出現無原因消失的工作。

## Single-agent / Multi-agent 公平比較

比較工作流不會讓兩條路徑共用一個有狀態的模擬器，而是建立兩個相同的數位分身：

```text
ScenarioDefinition
       ├── SimulatedEnvironment A → SingleAgentRunner
       └── SimulatedEnvironment B → Coordinator + Specialists
```

比較時忽略 run-specific ID 與時間戳，只比較具有診斷意義的內容：

- Action：tool、risk、parameters
- Observation：source、kind、values
- Evidence：claim、confidence
- Diagnostic final status

同時量測 Multi-agent 增加的治理資訊：

- Coordination handoff count
- Safety review outcome
- 是否產生報告
- Collaboration failure count
- Diagnostic action delta

目前正常 `seed=43` 的結果：

| 指標 | 結果 |
|---|---:|
| Single-agent diagnostic actions | 3 |
| Multi-agent diagnostic actions | 3 |
| Diagnostic action delta | 0 |
| Action / Observation / Evidence match | yes |
| Coordination handoffs | 6 |
| Safety review | approved |
| Report generated | yes |
| Collaboration failures | 0 |

這代表目前 Multi-agent 並沒有比 Single-agent 多做設備量測；它增加的是交接、覆核與報告責任。

## 手動操作

### 正常完成

```powershell
python examples\multi_agent_walkthrough.py
```

預期摘要：

```text
single diagnostic status: completed
multi diagnostic status: completed
coordination handoffs: 6
safety review: approved
report generated: yes
```

### 展示審查後安全停止

將每條診斷路徑限制為一次 Action：

```powershell
python examples\multi_agent_walkthrough.py --action-limit 1
```

預期摘要：

```text
single diagnostic status: safe_stopped
multi diagnostic status: safe_stopped
coordination handoffs: 4
safety review: requires_attention
report generated: no
```

### 選擇另一個 deterministic seed

```powershell
python examples\multi_agent_walkthrough.py --seed 44
```

Seed 只決定合成 Scenario，不是模型的隨機推理參數。相同 seed 與設定會產生相同結果。

### 查看參數

```powershell
python examples\multi_agent_walkthrough.py --help
```

### 完整測試

```powershell
python -m pytest
```

## 關鍵程式位置

| 元件 | 檔案 |
|---|---|
| Handoff contracts 與 ledger | `collaboration/contracts.py` |
| Specialist work products 與 failure records | `collaboration/products.py` |
| Coordinator | `collaboration/coordinator.py` |
| Diagnostic Agent | `collaboration/diagnostic.py` |
| Safety Reviewer | `collaboration/safety_reviewer.py` |
| Reporter | `collaboration/reporter.py` |
| Single/Multi comparison | `workflows/comparison.py` |
| 手動展示 | `examples/multi_agent_walkthrough.py` |

## 尚未實作

- Specialist 平行執行與非同步 message queue
- 真實 wall-clock timeout、取消與 heartbeat
- 多個 Diagnostic Agent 對相同問題提出不同假設
- Agent 間的反覆討論、仲裁與動態重新派工
- 外部身分驗證、角色權限與數位簽章
- LLM、本機模型或遠端 API adapter
- Benchmark、trace viewer 與量化安全指標
- Streamlit 操作介面與報告匯出

Phase 7 將以已知故障與預期答案建立 benchmark、評估指標和可觀測軌跡，從「流程可以執行」前進到「可以量化判斷流程是否可靠」。
