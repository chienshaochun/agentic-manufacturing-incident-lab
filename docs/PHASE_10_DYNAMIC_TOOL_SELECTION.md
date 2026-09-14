# Phase 10：動態工具選擇

## 本階段概念與物理意義

Phase 9讓Agent看見競爭中的故障假設；Phase 10讓這些假設真正影響下一個Action。Planner先建立目前可執行的診斷Probe，再計算每個Probe能區分多少未解假設，並扣除風險、執行成本與重複呼叫懲罰。

物理上相當於現場工程師不再照固定檢查表從頭做到尾，而是問：「現在做哪個量測，最能縮小故障範圍，而且不會帶來不必要風險？」

## Utility

```text
Utility = information_value × unresolved_coverage
          - execution_cost
          - risk_cost
          - repeat_cost
```

- `unresolved_coverage`：此Probe能區分的open／inconclusive假設比例。
- `risk_cost`：read-only為0、controlled-write為0.40、high-impact為1.00。
- `execution_cost`：工具本身的相對成本。
- `repeat_cost`：相同Tool與參數已執行時為1，避免卡在同一檢查。

只有正Utility且尚未執行的Probe可以被選中；若沒有安全且有資訊價值的選項，Planner會safe stop。

## Baseline與新Planner

- `RuleBasedPlanner`保留為固定規則baseline。
- `HypothesisDrivenPlanner`使用相同的完成與停止安全閘門，但動態排序可用Probe。
- Benchmark預設使用`HypothesisDrivenPlanner`，既有預期Tool sequence與安全結果仍需通過。

## 目前限制

- Information value與cost仍為工程設定，尚未從真實執行時間或案例統計估計。
- 目前Probe集合仍只涵蓋Connectivity與Telemetry。
- 仍是deterministic policy，尚未接入LLM。

Phase 11會加入Alarm history、Configuration、Maintenance與Sensor freshness，讓Utility排序在更真實的多來源診斷中發揮作用。
