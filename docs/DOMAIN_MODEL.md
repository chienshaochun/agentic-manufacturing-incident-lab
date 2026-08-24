# Phase 1 領域模型

## 為什麼先建立領域模型

Agent、工具、模擬器與 Streamlit 最終都必須交換相同資料。若每個元件各自使用沒有規則的 dictionary，欄位名稱、時間格式與狀態意義很容易逐漸不一致。

Phase 1 先把調查過程中的主要名詞轉成不可變的 Python 型別，讓後續元件共用同一份資料契約。

## 完整資料關係

```text
Incident（收到什麼問題）
    ↓ incident_id
TaskState（調查目前在哪個階段）
    ↓
Action（準備呼叫什麼工具以及原因）
    ↓ action_id
ActionResult（工具處理結果）
    ↓ observation_ids
Observation（工具觀察到的原始資料）
    ↓ observation_ids
Evidence（哪些觀察支持哪個判斷）
```

## 四個必須分開的概念

### 報案不等於觀察

`Incident.description` 是通報內容；`Observation` 才是工具取得的資料。使用者說「網路壞了」不能直接成為已證實的根因。

### 意圖不等於結果

`Action` 是工具呼叫請求；`ActionResult` 才說明它成功、失敗、被拒絕或逾時。開出工單不代表工單已完成。

### 原始資料不等於判斷

`Observation` 保存量測；`Evidence` 保存由哪些量測支持哪一項 claim。這讓最終報告可以反查證據來源。

### 現在狀態不等於完整歷史

每次 `transition_task()` 都建立新的 `TaskState` 並增加 revision。後續的記憶與檢查點元件會保存這些快照，而不是覆寫舊狀態。

## 任務狀態機

```text
CREATED
  ├─ INVESTIGATING
  │    ├─ WAITING_APPROVAL ── INVESTIGATING
  │    ├─ COMPLETED
  │    ├─ FAILED
  │    └─ SAFE_STOPPED
  └─ SAFE_STOPPED
```

`COMPLETED`、`FAILED` 與 `SAFE_STOPPED` 是終止狀態。Phase 1 不允許終止後重新開啟；若未來需要重新調查，應建立具關聯的新任務，而不是改寫已結束的歷史。

## 不可變資料的用途

主要 record 使用 `@dataclass(frozen=True, slots=True)`，mapping 則複製後包成唯讀 view。這能防止 Agent、工具或 UI 在不同時間偷偷改寫同一筆紀錄。

不可變不代表資料永遠不會更新，而是每次更新都要建立可追蹤的新紀錄。

## Phase 1 的責任邊界

Phase 1 只定義合法資料與狀態轉換，沒有：

- 自動選擇 Action
- 真正執行工具
- 自動產生 Observation 或 Evidence
- 保存狀態歷史
- 人工批准機制

這些能力會分別在後續的模擬環境、Agent loop、記憶與安全 Phase 加入。
