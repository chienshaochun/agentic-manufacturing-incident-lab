# Phase 11：多來源製造診斷情境

## 本階段概念與物理意義

現場看到「製程數值超過 30 分鐘沒有變化」時，畫面症狀相同，物理原因卻可能完全不同。它可能是感測器停止更新、設定版本錯誤、設備正在維護，也可能是網路或 Telemetry 傳輸失效。因此系統不能看到單一警報就直接宣告 Root Cause，而要把不同來源的 Observation 合併成可稽核的 Evidence。

本階段加入兩個表面症狀相同的受控案例：

- `sensor-staleness-seed-117`：網路、Telemetry 與設定都正常，但感測器資料年齡為 1860 秒。
- `configuration-drift-seed-118`：網路、Telemetry 與感測器更新正常，但生效設定與預期版本不同。

兩個案例都依序讀取 Alarm historian、Connectivity、Telemetry、Configuration、Maintenance 與 Sensor freshness。Agent 只有在一個假設獲得支持、其餘競爭假設都被排除後，才能建立 Evidence。

## 新增的診斷來源

| Tool | 對應的物理問題 | 主要 Observation |
|---|---|---|
| `read_alarm_history` | 過去出現哪些症狀指紋 | `alarm_codes_csv` |
| `check_connectivity` | 工作站網路路徑是否可達 | `network_reachable` |
| `read_telemetry` | 遙測服務是否仍回傳資料 | `telemetry_available` |
| `inspect_configuration` | 生效與預期設定是否一致 | `configuration_matches` |
| `read_maintenance_record` | 訊號中斷是否屬於計畫維護 | `maintenance_active` |
| `check_sensor_freshness` | 來源感測值是否持續更新 | `sensor_fresh`、`sensor_age_seconds` |

所有工具目前都是 deterministic、read-only 的模擬工具。公開專案不連接真實產線，也不包含公司資料。

## 推理邏輯

`ManufacturingSignalHypothesisPolicy` 同時維護五個候選原因：Network、Telemetry、Configuration、Maintenance 與 Sensor。Alarm 只提供部分支持，不能單獨形成結論；後續的來源量測才負責支持或排除假設。

`ManufacturingSignalPlanner` 使用 Phase 10 的 Utility scoring 選下一個 Probe。當五個候選原因中恰好一個為 `supported`，其餘全部為 `rejected`，才回傳 `CompleteDecision`。這項完成條件避免 Agent 把「最像的原因」錯當成「已被證據確認的原因」。

## 執行方式

```powershell
python -m pytest tests/unit/test_manufacturing_tools.py
python -m pytest tests/integration/test_manufacturing_signal_agent.py
python examples/benchmark_walkthrough.py --case sensor-staleness-seed-117
python examples/benchmark_walkthrough.py --case configuration-drift-seed-118
python -m streamlit run streamlit_app.py
```

完整 benchmark 現在包含 13 個案例。兩個新案例應產生不同 Evidence，但都必須符合 Tool 順序、狀態、安全審查、Evidence claim 與資源上限的 answer key。

## 限制

- Alarm、設定、維護與感測器狀態都是合成資料，不能代表實際設備分布。
- 規則與門檻由開發者事前定義，尚未從維修紀錄或標註資料學習。
- 目前確認的是「受控情境內的原因隔離」，不是對未知工廠事故的泛化能力證明。

