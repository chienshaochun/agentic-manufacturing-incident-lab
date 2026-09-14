# Phase 14：Evidence 品質與不確定性

## 本階段概念與物理意義

前一版能把 Observation 組成 Hypothesis 與 Evidence，但預設每一筆量測都同樣可信。真實製造現場並非如此：資料可能來自不穩定來源、感測器本身可能失準，也可能因傳輸延遲而過期。

因此本階段把「讀到了什麼」和「這筆資料有多可信」分開。就像工程師不會只抄下儀表數字，還會確認儀表是否校正、訊號品質是否正常、時間戳是否仍有效。

## Observation 品質

每筆 Observation 有三個介於 0 與 1 的係數：

- `source_reliability`：資料來源長期是否可靠。
- `measurement_quality`：這一次量測本身的品質。
- `freshness`：資料是否仍新鮮。

有效品質採乘法計算：

```text
quality_factor = source_reliability × measurement_quality × freshness
effective_signal = 原始 Signal 權重 × quality_factor
```

乘法的物理意義是任一環節接近失效時，整筆資料的證明力就應明顯下降。例如可靠度 1.0、量測品質 1.0，但新鮮度只有 0.4，原始權重 0.7 的 Signal 最後只貢獻 0.28。

## Hypothesis 的五種狀態

- `open`：還沒有有效相關資料。
- `inconclusive`：已有線索，但不足以支持或排除。
- `supported`：支持分數足夠、反對分數低，而且符合來源要求。
- `rejected`：反對分數達到門檻。
- `conflicted`：高品質支持與高品質反對同時成立。

`conflicted` 不等於程式錯誤，而是現場資料彼此不一致，應要求補測、校正或人工確認。

## 為何要要求不同來源

設定漂移不能只靠兩筆來自同一個 alarm historian 的紀錄就視為證實。本專案要求 Configuration Hypothesis 同時取得：

1. alarm historian 的異常線索；
2. configuration store 的實際版本比較。

Sensor staleness 也必須由 alarm historian 與 sensor monitor 交叉驗證。同來源重複回報可以增加紀錄數，卻不能假裝成兩個獨立證人。

## 三個新增受控案例

### 1. Alarm 與直接量測不一致

Alarm historian 出現 `SENSOR_STALE`，但 sensor monitor 直接量到資料仍新鮮。弱 Alarm 線索被較直接的反證推翻，因此 Sensor Hypothesis 為 `rejected`；其他原因也未被證實，流程安全停止。

### 2. 設定資料過期

Alarm 與 configuration store 都指向設定漂移，但 configuration store 的 freshness 只有 0.4。加權後支持分數不足，Configuration Hypothesis 維持 `inconclusive`，不產生 Evidence。

### 3. 同時支持兩個原因

設定漂移與感測器過期都有各自跨來源支持。系統不擅自把複合問題壓成單一 root cause，而是保留兩個 `supported` Hypothesis 並安全停止，交由工程師決定後續隔離或補測。

## 驗收方式

完整 benchmark 共 16 個案例。新增三案都必須：

- 執行六個唯讀診斷 Tool；
- 保留最終 Hypothesis 狀態；
- 不產生無法唯一成立的 Evidence；
- Safety Reviewer 回傳 `requires_attention`；
- Workflow 與 Diagnostic 都進入 `safe_stopped`；
- 不讓 Reporter 生成結論報告。

## 尚未完成的限制

- 品質係數與門檻目前是工程規則，不是由真實廠區資料校準。
- 目前只在模擬情境中指定來源品質，尚未接收真實 sensor health、校正紀錄或資料延遲。
- 多重原因目前選擇安全停止，尚未建立複合故障的 Evidence 與處置模型。
- 品質門檻尚未由真實產線資料校準；Phase 15 已補上每一步 Hypothesis 演化的 UI 與稽核軌跡。
