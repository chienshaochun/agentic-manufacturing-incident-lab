# Phase 16：結構化 Incident Intake

## 本階段概念與物理意義

本階段先完成 Ollama 外圍的安全資料流，不呼叫模型，也不新增模型套件。物理上相當於先建立標準報修單、允許填寫的欄位與操作員簽名程序，之後才讓語言模型協助填表。

```text
操作員文字與結構化選項
        ↓
Incident Intake Schema 驗證
        ↓
操作員預覽與確認
        ↓
寫入 Incident
        ↓
Coordinator → Diagnostic → Safety → Reporter
```

未確認的內容不能進入 Agent 流程。未來 Ollama 只能替換第一段的文字解析器，不能繞過驗證與確認。

## 四種可觀察症狀

事件調查台目前區分：

- 單一設備無法連線；
- 多台設備同時無法連線；
- 設備可連線，但 Telemetry 沒有更新；
- 設備在線，但製程數值持續平線。

這些是操作員能看到的現象，不是 `sensor_staleness` 或 `configuration_drift` 等 Root Cause。

## Incident Intake Schema

允許欄位固定為：

- `asset_id`
- `symptom_type`
- `duration_minutes`
- `network_reachable`
- `telemetry_available`
- `peer_affected`
- `parse_confidence`

Schema 設定 `additionalProperties: false`。因此未來即使模型輸出 `root_cause`、`recommended_action` 或其他未授權欄位，也會在進入 Agent 前被拒絕。

`symptom_type` 只允許四個代碼：

```text
station_unreachable
multi_station_unreachable
telemetry_missing
process_signal_flatline
```

此外還會驗證設備是否屬於已知資產、時間是否為非負整數、布林值是否真的為 Boolean，以及 parse confidence 是否在 0 到 1 之間。

## Parser 介面

`IncidentTextParser` 是 provider-neutral Protocol。未來的 Ollama adapter 必須實作：

```python
parse(raw_text, known_asset_ids) -> IncidentIntake
```

目前使用 `manual_structured_input_v1`：症狀與設備來自操作員選擇，不宣稱自由文字已被模型理解。這個 fallback 與未來 Ollama 共用相同 `IncidentIntake` 型別。

## 可編輯確認表單與人工閘門

主畫面不要求工程師閱讀或編輯 JSON，而是提供中文表單，讓操作員修改異常描述、持續時間、網路狀態、Telemetry 狀態與其他設備狀態。未知資訊可以保持「尚未檢查」，不會被偽裝成確定值。

原始 JSON 收在「技術與稽核資料」展開區，只供系統整合與除錯。按下「確認並執行調查」本身就是明確的人工確認動作，因此不再要求使用者重複勾選 checkbox。

確認後的文字會附加到真正送入 Coordinator 的 Incident description，並保存在中文 Raw Trace 中。它已不再只是頁面上的裝飾文字。

## 執行與測試重點

測試涵蓋：

- JSON Schema 不允許額外欄位；
- Root Cause 不能冒充症狀代碼；
- 未知設備、負時間、字串布林值與超界 confidence 都會被拒絕；
- Manual fallback 與未來 Ollama 使用相同契約；
- 描述、持續時間及三種設備狀態可以由操作員修改；
- 單一按鈕同時建立確認紀錄並啟動調查；
- 操作員確認的全部欄位確實寫入 Incident 與 Raw Trace；
- 四種症狀及其可重播批次可正常路由。

## 尚未完成的限制

- 目前沒有 Ollama adapter，自由文字中的時間、連線與 Peer 狀態不會自動填入 Schema。
- `parse_confidence` 未經真實標註資料校準；未來不能只依模型自評決定是否自動接受。
- 人工確認目前保存在單次 Streamlit session，尚未寫入獨立 audit database。
- Streamlit Cloud 無法直接連接使用者電腦的 `localhost:11434`；公開部署需要遠端受保護服務，或只在本機啟用 Ollama。
