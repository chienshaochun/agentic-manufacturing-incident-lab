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

## 目前完成的能力

- 可重播的合成製造異常情境
- 具工具選擇與重新規劃能力的單 Agent
- 任務狀態、短期記憶與檢查點
- 工具白名單、人工作業批准與安全停止
- 可比較的多 Agent 協作
- 故障注入、評估指標與完整追蹤紀錄
- Streamlit 操作介面與事件調查報告
- 症狀導向輸入、Hypothesis 演化與 Planner 候選決策可視化
- 可替換文字 Parser 的嚴格 Incident Intake 契約與人工確認閘門

詳細邊界與驗收條件見 [產品契約](docs/PRODUCT_CONTRACT.md)，逐步實作方式見 [學習路線圖](docs/LEARNING_ROADMAP.md)，Phase 1 的資料關係見 [領域模型](docs/DOMAIN_MODEL.md)，Phase 2 的執行架構見 [模擬環境與工具系統](docs/PHASE_2_SIMULATOR_AND_TOOLS.md)，Phase 3 的決策流程見 [單一 Agent 決策循環](docs/PHASE_3_SINGLE_AGENT_LOOP.md)，Phase 4 的恢復架構見 [工作記憶與 Checkpoint](docs/PHASE_4_MEMORY_AND_CHECKPOINTS.md)，Phase 5 的安全邊界見 [批准、安全與故障恢復](docs/PHASE_5_SAFETY_AND_RECOVERY.md)，Phase 6 的角色分工見 [多 Agent 協作與比較](docs/PHASE_6_MULTI_AGENT_COLLABORATION.md)，Phase 7 的量化驗證見 [評估、故障注入與可觀測性](docs/PHASE_7_EVALUATION_AND_OBSERVABILITY.md)，Phase 8 的完整操作方式見 [Streamlit 事件調查操作台](docs/PHASE_8_STREAMLIT_WORKBENCH.md)，Phase 9 的假設推理見 [Hypothesis Engine](docs/PHASE_9_HYPOTHESIS_ENGINE.md)，Phase 10 的決策方式見 [動態工具選擇](docs/PHASE_10_DYNAMIC_TOOL_SELECTION.md)，Phase 11 的跨來源案例見 [多來源製造診斷情境](docs/PHASE_11_REALISTIC_MANUFACTURING_SCENARIOS.md)，Phase 12 的模型邊界見 [結構化 LLM Planner](docs/PHASE_12_STRUCTURED_LLM_ADAPTER.md)，Phase 13 的驗證方式見 [Agent 能力評估與 Planner A/B](docs/PHASE_13_AGENT_EVALUATION.md)。

Phase 14 的可靠性設計見 [Evidence 品質與不確定性](docs/PHASE_14_EVIDENCE_QUALITY.md)。

Phase 15 的操作與推理呈現見 [症狀導向操作台與推理可視化](docs/PHASE_15_INVESTIGATION_UX.md)。

Phase 16 的模型接入前置設計見 [結構化 Incident Intake](docs/PHASE_16_STRUCTURED_INCIDENT_INTAKE.md)。

## 目前進度

Phase 16 已完成：操作員可從 4 種可觀察症狀建立嚴格的結構化 Incident Intake，並直接修改描述、持續時間與設備狀態。JSON 僅收在稽核展開區；按下「確認並執行」才會建立確認紀錄並啟動 Agent。自由文字會進入 Incident 與 Raw Trace，但目前不宣稱已經過 NLP 理解；未來 Ollama 只能透過相同 Schema 插入。完整 benchmark 維持 16 個受控案例。

## 本機手動演練

建立 Python 3.12 Conda 環境，並以 editable mode 安裝專案與開發依賴：

```powershell
cd agentic-manufacturing-incident-lab
conda create -n agentic-lab python=3.12 -y
conda activate agentic-lab
python -m pip install -e ".[dev,ui]"
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
python examples\safety_recovery_walkthrough.py --scenario all --approval approve
python examples\multi_agent_walkthrough.py
python examples\benchmark_walkthrough.py
python examples\structured_llm_walkthrough.py --mode replay
python examples\structured_llm_walkthrough.py --mode invalid
python -m streamlit run streamlit_app.py
python -m pytest
```

也可以分別驗證人工拒絕與故障恢復：

```powershell
python examples\safety_recovery_walkthrough.py --scenario approval --approval reject
python examples\safety_recovery_walkthrough.py --scenario recovery
python examples\multi_agent_walkthrough.py --action-limit 1
python examples\benchmark_walkthrough.py --case reporter-exception-seed-43
```

目前所有 walkthrough 都只使用合成資料與本機 deterministic Python 邏輯，不會呼叫 LLM、網路、真實工具或設備。

## 技術原則

- Python 3.12
- 先完成可預測、可測試的確定性核心，再考慮接入 LLM
- 公開版本只使用合成資料，不含任何公司機密或真實製程參數
- LLM 與本機模型屬於後續可替換元件，不是系統正確性的唯一來源
