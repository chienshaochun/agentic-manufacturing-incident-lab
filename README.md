# Agentic Manufacturing Incident Response Lab

這是一個以教學與作品集展示為目的的 Agentic AI 專案：在完全模擬、可重播的製造環境中，讓 AI Agent 接收異常事件，蒐集證據、選擇工具、規劃處置步驟，並在安全規則下完成調查報告。

專案不會連接真實工廠、機台或客戶資料，也不會對實體設備下指令。它要展示的核心能力不是「聊天」，而是讓一個軟體代理在有限工具、有限資訊與明確安全邊界內完成任務。

## Agent 的核心循環

```text
目標
  ↓
觀察環境 → 選擇工具 → 執行工具 → 檢查結果
  ↑                                  ↓
  └──────── 必要時重新規劃 ──────────┘
                      ↓
                   安全停止
```

它和一般問答機器人的差異在於：回答文字不是唯一結果。Agent 必須根據目前狀態決定下一個動作、留下可稽核的工具呼叫紀錄，並知道何時需要批准或停止。

## 物理意義

可以把本專案想成一位「虛擬製造現場值班主管」：

- 異常事件像產線亮起警報燈。
- 工具像量測儀器、系統紀錄與標準作業程序。
- Agent 像主管，根據證據決定下一項檢查，而不是預先走死板流程。
- 安全政策像權限與聯鎖，避免未經批准的高風險操作。
- 執行軌跡與報告像交班紀錄，讓後續人員能重現判斷過程。

## 預計完成的能力

- 可重播的合成製造異常情境
- 具工具選擇與重新規劃能力的單 Agent
- 任務狀態、短期記憶與檢查點
- 工具白名單、人工作業批准與安全停止
- 可比較的多 Agent 協作
- 故障注入、評估指標與完整追蹤紀錄
- Streamlit 操作介面與事件調查報告

詳細邊界與驗收條件見 [產品契約](docs/PRODUCT_CONTRACT.md)，逐步實作方式見 [學習路線圖](docs/LEARNING_ROADMAP.md)，Phase 1 的資料關係見 [領域模型](docs/DOMAIN_MODEL.md)，Phase 2 的執行架構見 [模擬環境與工具系統](docs/PHASE_2_SIMULATOR_AND_TOOLS.md)，Phase 3 的決策流程見 [單一 Agent 決策循環](docs/PHASE_3_SINGLE_AGENT_LOOP.md)，Phase 4 的恢復架構見 [工作記憶與 Checkpoint](docs/PHASE_4_MEMORY_AND_CHECKPOINTS.md)。

## 目前進度

Phase 4 已完成：單 Agent 現在具備版本化 WorkingMemory、正式 Action budget、具完整性檢查的 JSON checkpoint，以及經環境重播驗證的 pause/resume。下一階段將加入人工批准、安全政策、逾時、重試與故障恢復。

## 本機手動演練

建立 Python 3.12 Conda 環境，並以 editable mode 安裝專案與開發依賴：

```powershell
cd agentic-manufacturing-incident-lab
conda create -n agentic-lab python=3.12 -y
conda activate agentic-lab
python -m pip install -e ".[dev]"
```

執行完整領域流程與測試：

```powershell
python examples\domain_walkthrough.py
python examples\scenario_preview.py
python examples\environment_walkthrough.py
python examples\tool_execution_walkthrough.py
python examples\baseline_workflow.py
python examples\single_agent_walkthrough.py
python examples\checkpoint_resume_walkthrough.py
python -m pytest
```

目前所有 walkthrough 都只使用合成資料與本機 deterministic Python 邏輯，不會呼叫 LLM、網路、真實工具或設備。

## 技術原則

- Python 3.12
- 先完成可預測、可測試的確定性核心，再考慮接入 LLM
- 公開版本只使用合成資料，不含任何公司機密或真實製程參數
- LLM 與本機模型屬於後續可替換元件，不是系統正確性的唯一來源
