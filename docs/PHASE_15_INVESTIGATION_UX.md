# Phase 15：症狀導向操作台與推理可視化

## 本階段概念與物理意義

前一版事件調查台直接列出「感測器資料過期」與「設定版本漂移」等案例名稱。雖然 Diagnostic Agent 執行時仍看不到 answer key，但對展示者而言，畫面像是先選好答案再開始調查。

本階段把操作員輸入與評估答案分開：操作員只選擇現場可觀察的症狀；模擬批次保存隱藏環境，Evaluator 則在調查結束後才以 answer key 驗收。這就像設備報修單只寫「製程數值持續平線」，真正原因要靠後續量測確認。

## 症狀與 Benchmark 的責任分離

事件調查台目前提供兩個症狀範圍：

- 設備無法連線或遙測中斷；
- 製程數值持續平線。

第二層只顯示中性的「模擬批次 A～E」，不顯示 Root Cause。批次的 seed 讓相同隱藏環境可以重播，並不是送給 Agent 的答案。

精準案例名稱、故障注入與 expected outcome 只保留在 Benchmark Dashboard，因為那一頁的用途是測試系統，不是模擬操作員報案。

自由文字的操作員補充目前只作為畫面備註，尚未用 NLP 解析；UI 會明確揭露這項限制。

## Hypothesis 演化時間線

調查一開始，所有候選原因都是 `open`。每收到一筆 Observation，Presentation layer 會用相同 deterministic policy 重播當時的資料前綴，產生新的 Hypothesis snapshot。

```text
初始狀態
  ↓ Observation 1
重新評估全部候選原因
  ↓ Observation 2
再次重新評估
  ↓
最終 supported / rejected / inconclusive / conflicted
```

UI 的狀態矩陣適合快速看演變；展開明細後則能看到每個狀態引用哪些支持與反對 Observation，以及品質加權後的分數。這回答了「哪一筆量測讓某個假設被排除」。

## Planner 候選決策

每次執行 Tool 前，Planner 會對當下所有候選 Probe 計分：

```text
Utility
= Information Value × Unresolved Hypothesis Coverage
− Execution Cost
− Risk Cost
− Repeat Cost
```

- `information_value`：這個 Tool 原本有多大辨識價值。
- `unresolved_coverage`：它能處理目前多少尚未解決的假設。
- `execution_cost`：呼叫工具的相對成本。
- `risk_cost`：操作風險；目前診斷工具皆為唯讀，因此為 0。
- `repeat_cost`：相同工具與參數已執行時加入 1.0，避免卡在同一檢查。
- `eligible`：Utility 大於 0 且沒有重複懲罰。
- `selected`：通過資格後 Utility 最高、實際被執行的候選。

候選評分是 Planner 的公開 deterministic API。Presentation layer 使用原始執行紀錄、Working Memory、Hypothesis 與 ToolSpec 重建每一個決策點，不靠 UI 猜測。

## Raw Trace 強化

下載的 `.txt` 稽核軌跡現在額外包含：

- 每筆 Observation 的來源可靠度、量測品質、新鮮度與合併品質；
- 最終所有 Hypothesis 的狀態、信心值、支持與反對 Observation IDs；
- 每個候選 Tool 的 Utility 完整拆解，以及是否符合資格、是否被選中。

因此工程師可以從最終 Evidence 反向追到 Hypothesis、Observation、Tool Action 與 Planner 選擇。

## 執行與測試結果

Phase 15 的測試涵蓋：

- 預設頁面只顯示症狀與中性批次；
- 不確定批次會安全停止且不產生正式報告；
- Connectivity 案例的 3 個 Hypothesis 有 4 個時間點；
- 多來源案例的 5 個 Hypothesis 有 7 個時間點；
- 每個實際 Action 恰有一個被選中的候選 Tool；
- 被選中的 Tool 是 eligible 候選中的最高 Utility；
- JSON 與 Raw Trace 都保存新增的推理資料。

## 尚未完成的限制

- Phase 16 已建立結構化 Incident Intake、Parser 契約與人工確認；自由文字仍要等 Ollama adapter 才會自動解析。
- 模擬批次仍是人工建立的合成環境，不能代表實際工廠故障分布。
- Hypothesis 時間線是依既有紀錄重播，尚未作為獨立 event stream 永久儲存。
- Utility 係數目前是工程設計值，尚未從歷史工單、Tool 延遲與風險資料校準。
