# Phase 9：Hypothesis Engine

## 本階段概念與物理意義

早期版本的 Diagnostic Agent 能依 Observation 完成固定的隔離判斷，但沒有留下「哪些候選原因正在競爭、哪些已被排除」的正式紀錄。Phase 9 加入 Hypothesis Engine，讓調查過程同時維護多個候選解釋。

物理上可把它想成工程師在白板列出可能原因。每次量測不只增加一筆紀錄，也必須標示它支持或反對哪些原因；正式 Evidence 仍需要 Planner 完成決策與 Safety Reviewer 審查，Hypothesis 本身不等於 Root Cause。

## 資料關係

```text
Incident
   ↓ 建立候選原因
HypothesisDefinition
   ↓
Observation ── HypothesisSignal（supports / contradicts）
   ↓
Hypothesis（open / inconclusive / supported / rejected）
   ↓ Planner 完成條件
Evidence
```

## 目前三個競爭假設

- 故障隔離在受影響工作站。
- 共用網路基礎設施不可用。
- 受影響工作站的 Telemetry 路徑不可用。

連線與 Telemetry Observation 會依資產範圍和量測值產生不同權重的支持或反對 Signal。Engine 將 Signal 聚合成 support score、contradiction score、狀態與信心值。

## 安全與稽核限制

- Signal 必須引用真實 Observation ID。
- 同一筆 Observation 不得同時支持又反對同一假設。
- `supported` 必須至少引用一筆支持 Observation。
- `rejected` 必須至少引用一筆反對 Observation。
- Hypothesis 會保存在 InvestigationRun；Phase 14 新增 Observation 品質欄位後，checkpoint schema 已更新至 v5。
- UI 與下載報告會分開呈現 Hypothesis 與 Evidence。

## 目前限制

- Signal規則與權重仍由工程規則事前定義，尚未從維修標註資料校準。
- Planner仍採原本固定的rule-based順序，尚未使用假設狀態挑選下一個Tool。
- 目前只涵蓋連線與Telemetry三個假設。

Phase 10會使用Hypothesis狀態、資訊價值、風險與成本，動態選擇下一個診斷Tool。
