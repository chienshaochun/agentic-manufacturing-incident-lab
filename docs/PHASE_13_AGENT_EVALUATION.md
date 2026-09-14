# Phase 13：Agent 能力評估與 Planner A/B

## 本階段概念與物理意義

傳統分類模型常用 Precision、Recall 評估答案；Agent 還需要評估「取得答案的過程」。一個最後答對的 Agent，仍可能重複量測、引用不存在的資料、留下大量未排除原因，或在工具失效後無法恢復。因此本階段把答案品質、調查效率與安全行為放在同一個 Dashboard。

## 五個過程指標

| 指標 | 計算方式 | 物理意義 |
|---|---|---|
| Hypothesis resolution rate | `supported + rejected`／全部候選假設 | 停止前有多少候選原因已被證據支持或排除 |
| Unsupported claim rate | 不符合 answer key 或缺少 Observation／supported hypothesis 的 Evidence 比例 | Agent 是否在沒有足夠根據時下結論 |
| Redundant tool call rate | 重複的 `tool + parameters`／全部邏輯 Action | 是否卡在同一檢查反覆執行 |
| Actions to evidence | 有 Evidence 的案例在完成前執行的邏輯 Action 數 | 取得可用結論的診斷成本 |
| Recovery success rate | 成功的替代 Tool／`TRY_ALTERNATIVE` 次數 | 原工具失效後，替代量測是否真的可用 |

`n/a` 表示該案例沒有觸發相應事件。例如正常 benchmark 沒有故障恢復動作，所以 Recovery 顯示 `n/a`，不應誤寫成 0 或 100%。

## 如何解讀目前結果

目前 13 個 controlled cases 全部通過 answer key，Evidence precision 與 recall 都是 1.0，Unsupported claim rate 與 Redundant tool call rate 都是 0。這只代表固定案例符合規格，不代表未知產線事故有 100% 準確率。

平均 Hypothesis resolution 約為 0.636，因為部分 connectivity 案例在任務目標已足以回答時，仍保留一個與目標無關或證據不足的 `inconclusive` 假設；這項指標刻意把未決狀態揭露出來，而不是把它藏在最終 PASS 後面。兩個 Phase 11 的多來源平線案例則要求一個 `supported`、其餘全部 `rejected`，解析率為 1.0。

## Planner A/B

Dashboard 使用相同 Scenario、seed、Action limit 與公開 Incident brief，分別在隔離的 simulator 執行：

- `RuleBasedPlanner`：依固定 if/else 規則選擇下一步。
- `HypothesisDrivenPlanner`：依候選假設的資訊價值、成本、風險與重複懲罰選擇 Probe。

目前五個 connectivity 案例的狀態、Evidence、工具順序與 Action 數完全一致。這表示新 Planner 在既有受控案例維持行為相容；它的新增價值是保留候選假設與量測如何改變假設的稽核軌跡，而不是刻意聲稱在簡單案例減少工具數。

## 操作方式

```powershell
python -m pytest
python -m streamlit run streamlit_app.py
```

進入 `基準測試 Benchmark Dashboard`，按下執行按鈕後依序看：

1. 上方卡片確認 13/13 與 Evidence precision／recall。
2. 檢查 Resolution、Unsupported、Redundant 與 Actions 指標。
3. 在案例表比較 sensor staleness 與 configuration drift。
4. 在 Planner A/B 表確認兩種 Planner 的狀態、Action 差值與 Evidence 是否一致。

## 限制

- 所有數值來自 deterministic 合成案例，無法取代現場 shadow test、工程師標註與長期 drift monitoring。
- Answer key 是人工事前定義，因此它衡量規格一致性，不是自動發現未知 Root Cause 的能力。
- Planner A/B 目前只比較兩者都支援的 connectivity scenarios；多來源情境沒有硬套進功能較窄的舊 RuleBasedPlanner。

