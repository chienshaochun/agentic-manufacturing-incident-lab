"""Interactive Streamlit workbench for the controlled incident lab."""

import os
from dataclasses import asdict, replace

import streamlit as st

from agentic_manufacturing_incident_lab.evaluation import (
    BenchmarkCase,
    BenchmarkCaseResult,
    build_benchmark_catalog,
    run_benchmark_case,
    run_benchmark,
    run_planner_comparison,
)
from agentic_manufacturing_incident_lab.presentation import (
    BenchmarkPresentation,
    CasePresentation,
    benchmark_csv,
    benchmark_json,
    build_benchmark_presentation,
    build_case_presentation,
    case_json,
    case_report_markdown,
)
from agentic_manufacturing_incident_lab.intake import (
    ConfirmedIncidentIntake,
    IncidentIntake,
    IntakeSource,
    OllamaIncidentTextParser,
    SymptomType,
    build_manual_intake,
    confirm_intake,
    intake_from_payload,
)
from agentic_manufacturing_incident_lab.local_llm import (
    DEFAULT_OLLAMA_MODEL,
    OllamaError,
    OllamaInvestigationQA,
)


CASE_LABELS = {
    "isolated-station-seed-42": "單一工作站故障｜Isolated ST-01",
    "isolated-station-seed-43": "單一工作站故障｜Isolated ST-02",
    "isolated-station-seed-44": "單一工作站故障｜Isolated ST-03",
    "shared-infrastructure-seed-73": "共用基礎設施疑點｜Shared infrastructure",
    "telemetry-path-seed-91": "遙測路徑疑點｜Telemetry path",
    "action-budget-safe-stop-seed-43": "動作額度耗盡｜Action budget safe stop",
    "sensor-staleness-seed-117": "製程訊號平線：感測器資料過期｜Sensor staleness",
    "configuration-drift-seed-118": "製程訊號平線：設定版本漂移｜Configuration drift",
    "conflicting-sensor-evidence-seed-119": "製程訊號平線：感測資料矛盾｜Conflicting evidence",
    "low-quality-configuration-evidence-seed-120": "製程訊號平線：設定資料品質不足｜Low-quality evidence",
    "multiple-supported-causes-seed-121": "製程訊號平線：同時支持多個原因｜Multiple causes",
    "diagnostic-exception-seed-43": "診斷 Agent 例外｜Diagnostic exception",
    "diagnostic-invalid-response-seed-43": "診斷回覆無效｜Invalid response",
    "safety-reviewer-exception-seed-43": "安全審查 Agent 例外｜Reviewer exception",
    "reporter-exception-seed-43": "報告 Agent 例外｜Reporter exception",
    "contradictory-approval-seed-43": "安全核准矛盾｜Contradictory approval",
}

SYMPTOM_CASES = {
    "單一設備無法連線": (
        "isolated-station-seed-43",
        "isolated-station-seed-42",
        "isolated-station-seed-44",
    ),
    "多台設備同時無法連線": (
        "shared-infrastructure-seed-73",
    ),
    "設備可連線，但 Telemetry 沒有更新": (
        "telemetry-path-seed-91",
    ),
    "設備在線，但製程數值持續平線": (
        "sensor-staleness-seed-117",
        "configuration-drift-seed-118",
        "conflicting-sensor-evidence-seed-119",
        "low-quality-configuration-evidence-seed-120",
        "multiple-supported-causes-seed-121",
    ),
}

SYMPTOM_TYPES = {
    "單一設備無法連線": SymptomType.STATION_UNREACHABLE,
    "多台設備同時無法連線": SymptomType.MULTI_STATION_UNREACHABLE,
    "設備可連線，但 Telemetry 沒有更新": SymptomType.TELEMETRY_MISSING,
    "設備在線，但製程數值持續平線": SymptomType.PROCESS_SIGNAL_FLATLINE,
}

SIMULATION_BATCH_LABELS = {
    "isolated-station-seed-43": "模擬批次 A｜ST-02 回報，可重播",
    "isolated-station-seed-42": "模擬批次 B｜ST-01 回報，可重播",
    "isolated-station-seed-44": "模擬批次 C｜ST-03 回報，可重播",
    "shared-infrastructure-seed-73": "模擬批次 A｜跨設備回報，可重播",
    "telemetry-path-seed-91": "模擬批次 A｜Telemetry 缺值回報，可重播",
    "sensor-staleness-seed-117": "模擬批次 A｜標準資料組，可重播",
    "configuration-drift-seed-118": "模擬批次 B｜標準資料組，可重播",
    "conflicting-sensor-evidence-seed-119": "模擬批次 C｜交叉來源不一致，可重播",
    "low-quality-configuration-evidence-seed-120": "模擬批次 D｜關鍵資料新鮮度偏低，可重播",
    "multiple-supported-causes-seed-121": "模擬批次 E｜多組訊號同時成立，可重播",
}

WORKBENCH_PAGE = "事件調查台 Incident Workbench"
BENCHMARK_PAGE = "基準測試 Benchmark Dashboard"
ABOUT_PAGE = "關於專案 About"
APP_RELEASE = "Local Ollama Enhancement v1"
LOCAL_OLLAMA_ENV = "INCIDENT_LAB_ENABLE_OLLAMA"

NETWORK_STATUS_OPTIONS = {
    "未知／尚未檢查": None,
    "可以連線": True,
    "無法連線": False,
}

TELEMETRY_STATUS_OPTIONS = {
    "未知／尚未檢查": None,
    "持續更新": True,
    "沒有更新": False,
}

PEER_STATUS_OPTIONS = {
    "未知／尚未檢查": None,
    "其他設備也受影響": True,
    "其他設備正常": False,
}

HYPOTHESIS_STATUS_LABELS = {
    "open": "⚪ open",
    "inconclusive": "🟡 inconclusive",
    "supported": "🟢 supported",
    "rejected": "⚫ rejected",
    "conflicted": "🔴 conflicted",
}


def _local_ollama_enabled() -> bool:
    """Keep the public deployment unchanged unless local mode is explicit."""
    return os.getenv(LOCAL_OLLAMA_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _status_label(options: dict[str, bool | None], value: bool | None) -> str:
    return next(label for label, option_value in options.items() if option_value is value)


def _render_local_intake_assistant(
    *,
    raw_text: str,
    asset_id: str,
    symptom_type: SymptomType,
) -> IncidentIntake | None:
    """Optionally populate existing form widgets without changing their layout."""
    suggestion = st.session_state.get("ollama_intake_suggestion")
    if not isinstance(suggestion, IncidentIntake) or suggestion.raw_text != raw_text:
        suggestion = None

    with st.expander("本機 Ollama 輔助填表（選用）", expanded=False):
        st.caption(
            "只在本機模式出現。模型會把上方文字整理成現有欄位；"
            "內容仍需按下原本的確認按鈕，且不會直接成為 Evidence。"
        )
        if st.button(
            "使用 Ollama 解析異常描述",
            key="ollama_parse_intake",
            icon=":material/auto_awesome:",
        ):
            try:
                with st.spinner("Ollama 正在整理事件描述..."):
                    parsed = OllamaIncidentTextParser().parse(
                        raw_text,
                        known_asset_ids=(asset_id,),
                    )
            except (OllamaError, ValueError) as error:
                st.error(f"Ollama 解析失敗，現有手動表單仍可使用：{error}")
            else:
                st.session_state["ollama_intake_suggestion"] = parsed
                suggestion = parsed
                if parsed.symptom_type is symptom_type:
                    st.session_state["intake_duration"] = parsed.duration_minutes
                    st.session_state["intake_network"] = _status_label(
                        NETWORK_STATUS_OPTIONS, parsed.network_reachable
                    )
                    st.session_state["intake_telemetry"] = _status_label(
                        TELEMETRY_STATUS_OPTIONS, parsed.telemetry_available
                    )
                    st.session_state["intake_peer"] = _status_label(
                        PEER_STATUS_OPTIONS, parsed.peer_affected
                    )
                    st.success(
                        "已將解析結果填入原有欄位；請在執行調查前人工確認。"
                    )
                else:
                    st.warning(
                        "模型判斷的症狀類型與上方選項不同，因此沒有自動套用。"
                        "請先確認並調整「回報症狀」。"
                    )
        if suggestion is not None:
            st.write(
                f"解析來源：`{suggestion.parser_name}` · "
                f"信心值：`{suggestion.parse_confidence:.2f}` · "
                f"症狀：`{suggestion.symptom_type.value}`"
            )
    return suggestion


def _intake_from_form(
    *,
    raw_text: str,
    asset_id: str,
    symptom_type: SymptomType,
    known_asset_ids: tuple[str, ...],
    duration_minutes: int | None,
    network_reachable: bool | None,
    telemetry_available: bool | None,
    peer_affected: bool | None,
    ollama_suggestion: IncidentIntake | None,
) -> IncidentIntake:
    """Preserve Ollama provenance only while its interpretation is still applicable."""
    if (
        ollama_suggestion is not None
        and ollama_suggestion.raw_text == raw_text
        and ollama_suggestion.asset_id == asset_id
        and ollama_suggestion.symptom_type is symptom_type
    ):
        return intake_from_payload(
            raw_text,
            {
                "asset_id": asset_id,
                "symptom_type": symptom_type.value,
                "duration_minutes": duration_minutes,
                "network_reachable": network_reachable,
                "telemetry_available": telemetry_available,
                "peer_affected": peer_affected,
                "parse_confidence": ollama_suggestion.parse_confidence,
            },
            parser_name=ollama_suggestion.parser_name,
            source=IntakeSource.OLLAMA,
            known_asset_ids=known_asset_ids,
        )
    return build_manual_intake(
        raw_text=raw_text,
        asset_id=asset_id,
        symptom_type=symptom_type,
        known_asset_ids=known_asset_ids,
        duration_minutes=duration_minutes,
        network_reachable=network_reachable,
        telemetry_available=telemetry_available,
        peer_affected=peer_affected,
    )


def _render_local_investigation_qa(result: BenchmarkCaseResult) -> None:
    """Append optional local Q&A after the unchanged investigation result."""
    with st.expander("本機 Ollama 調查問答（選用）", expanded=False):
        st.caption(
            "回答只使用本次調查的 Observation、Hypothesis、Evidence 與安全審查；"
            "不會改寫正式結果，也不會執行 Tool。"
        )
        with st.form("ollama_investigation_qa_form"):
            question = st.text_input(
                "詢問本次調查",
                placeholder="例如：為什麼這個假設被支持？接下來還應檢查什麼？",
            )
            submitted = st.form_submit_button(
                "詢問本機模型",
                icon=":material/question_answer:",
            )
        if submitted:
            try:
                with st.spinner("Ollama 正在根據調查證據回答..."):
                    answer = OllamaInvestigationQA().answer(question, result.run)
            except (OllamaError, ValueError) as error:
                st.error(f"本機問答失敗，正式調查結果不受影響：{error}")
            else:
                st.session_state["ollama_case_answer"] = (result.case_id, answer)

        stored = st.session_state.get("ollama_case_answer")
        if not isinstance(stored, tuple) or len(stored) != 2 or stored[0] != result.case_id:
            return
        answer = stored[1]
        st.markdown("##### 模型說明")
        st.write(answer.answer)
        st.caption(
            f"模型：{answer.model} · 引用 Observation："
            f"{', '.join(answer.observation_ids)} · 引用 Evidence："
            f"{', '.join(answer.evidence_ids) or '無'}"
        )
        if answer.next_checks:
            st.markdown("##### 建議的下一步檢查（尚未執行）")
            st.dataframe(
                [asdict(item) for item in answer.next_checks],
                hide_index=True,
                width="stretch",
            )
        if answer.limitations:
            st.markdown("##### 限制")
            for limitation in answer.limitations:
                st.markdown(f"- {limitation}")


def _metric_grid(metrics) -> None:
    columns = st.columns(4)
    for index, metric in enumerate(metrics):
        columns[index % len(columns)].metric(
            metric.label,
            metric.value,
            help=metric.help_text,
            border=True,
        )


def _case_lookup():
    return {case.case_id: case for case in build_benchmark_catalog()}


def _case_with_confirmed_intake(
    case_id: str,
    confirmed: ConfirmedIncidentIntake,
) -> BenchmarkCase:
    case = _case_lookup()[case_id]
    incident = case.scenario.incident
    if confirmed.intake.asset_id != incident.asset_id:
        raise ValueError("confirmed intake asset must match the selected simulation")
    updated_incident = replace(
        incident,
        description=(
            f"{incident.description} "
            f"Operator-confirmed report: {confirmed.intake.raw_text} "
            f"[symptom_type={confirmed.intake.symptom_type.value}; "
            f"duration_minutes={confirmed.intake.duration_minutes}; "
            f"network_reachable={confirmed.intake.network_reachable}; "
            f"telemetry_available={confirmed.intake.telemetry_available}; "
            f"peer_affected={confirmed.intake.peer_affected}]"
        ),
    )
    return replace(
        case,
        scenario=replace(case.scenario, incident=updated_incident),
    )


def _run_selected_case(
    case_id: str,
    confirmed: ConfirmedIncidentIntake,
) -> None:
    case = _case_with_confirmed_intake(case_id, confirmed)
    with st.spinner("Running deterministic multi-agent investigation..."):
        result = run_benchmark_case(case)
    st.session_state["case_result"] = result
    st.session_state["confirmed_intake"] = confirmed


def _current_case_result(case_id: str) -> BenchmarkCaseResult | None:
    result = st.session_state.get("case_result")
    if isinstance(result, BenchmarkCaseResult) and result.case_id == case_id:
        return result
    return None


def _run_full_benchmark() -> None:
    with st.spinner("Running all controlled benchmark cases..."):
        summary = run_benchmark()
    st.session_state["benchmark_view"] = build_benchmark_presentation(summary)
    st.session_state["planner_comparison"] = run_planner_comparison()


def _current_benchmark_view() -> BenchmarkPresentation | None:
    view = st.session_state.get("benchmark_view")
    return view if isinstance(view, BenchmarkPresentation) else None


def _render_case_status(view: CasePresentation) -> None:
    if view.passed and view.workflow_status == "completed":
        st.success("調查完成：輸出已通過安全審查，且所有結論皆綁定 Evidence。")
    elif view.passed and view.failures:
        st.warning("協作故障已被安全收斂，系統沒有偽造缺失的 Agent 產物。")
    elif view.passed:
        st.info("現有證據不足以產生報告，工作流已安全停止。")
    else:
        st.error("本次執行未符合受控 Benchmark 的預期結果。")


def _hypothesis_evolution_rows(view: CasePresentation) -> list[dict[str, object]]:
    rows_by_step: dict[int, dict[str, object]] = {}
    for snapshot in view.hypothesis_timeline:
        row = rows_by_step.setdefault(
            snapshot.step,
            {
                "步驟": snapshot.step,
                "新 Observation": snapshot.trigger_observation,
            },
        )
        row[snapshot.candidate] = HYPOTHESIS_STATUS_LABELS[snapshot.status]
    return list(rows_by_step.values())


def _render_full_case_details(view: CasePresentation) -> None:
    st.subheader("調查總覽 Investigation overview")
    _metric_grid(view.metrics)
    _render_case_status(view)
    handoff_tab, hypothesis_tab, action_tab, evidence_tab, outcome_tab, trace_tab = st.tabs(
        (
            "交接紀錄 Handoffs",
            "診斷假設 Hypotheses",
            "動作與嘗試 Actions & attempts",
            "證據與安全 Evidence & safety",
            "報告與失敗 Report & failures",
            "完整軌跡 Raw trace",
        )
    )

    with handoff_tab:
        st.markdown("#### Coordinator 交接帳本")
        st.caption("記錄每一筆跨越 Agent 責任邊界的請求與回覆。")
        st.dataframe(
            [asdict(handoff) for handoff in view.handoffs],
            hide_index=True,
            width="stretch",
            column_config={
                "sequence": "順序",
                "sender": "發送者 Sender",
                "recipient": "接收者 Recipient",
                "kind": "訊息類型",
                "purpose": "交接目的",
                "reply_to": "回覆對象",
            },
        )

    with hypothesis_tab:
        st.markdown("#### 競爭中的故障假設")
        st.caption(
            "每個候選原因都分別累積支持與反對它的 Observation；"
            "Hypothesis 不是正式 Evidence，也不等同已確認 Root Cause。"
        )
        if view.hypotheses:
            st.markdown("##### 假設演化時間線")
            st.caption(
                "由上往下閱讀：每取得一筆新 Observation，就重新評估全部候選原因。"
                "紅色 conflicted 表示支持與反對訊號同時很強，不能硬選答案。"
            )
            st.dataframe(
                _hypothesis_evolution_rows(view),
                hide_index=True,
                width="stretch",
            )

            st.markdown("##### 最終假設狀態")
            st.dataframe(
                [asdict(hypothesis) for hypothesis in view.hypotheses],
                hide_index=True,
                width="stretch",
                column_config={
                    "hypothesis_id": "Hypothesis ID",
                    "statement": "候選原因",
                    "status": "狀態",
                    "confidence": "信心值",
                    "supporting_observation_ids": "支持的 Observations",
                    "contradicting_observation_ids": "反對的 Observations",
                    "rationale": "評分摘要",
                },
            )
            with st.expander("查看每一步的支持／反對 Observation"):
                st.dataframe(
                    [asdict(snapshot) for snapshot in view.hypothesis_timeline],
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "step": "步驟",
                        "trigger_observation": "新 Observation",
                        "candidate": "候選代碼",
                        "hypothesis_id": "Hypothesis ID",
                        "statement": "候選原因",
                        "status": "狀態",
                        "confidence": "信心值",
                        "supporting_observation_ids": "支持的 Observations",
                        "contradicting_observation_ids": "反對的 Observations",
                        "rationale": "品質加權評分",
                    },
                )
        else:
            st.info("Diagnostic Agent 沒有產生可顯示的診斷假設。")

    with action_tab:
        st.markdown("#### Planner 候選決策")
        st.caption(
            "每一步都先替所有候選 Tool 計算 Utility = Information × 未解假設涵蓋率 "
            "− 執行成本 − 風險成本 − 重複成本；selected 才是實際執行者。"
        )
        if view.planner_candidates:
            st.dataframe(
                [asdict(candidate) for candidate in view.planner_candidates],
                hide_index=True,
                width="stretch",
                column_config={
                    "step": "決策步驟",
                    "tool": "候選 Tool",
                    "parameters": "參數",
                    "information_value": "資訊價值",
                    "unresolved_coverage": "未解假設涵蓋率",
                    "execution_cost": "執行成本",
                    "risk_cost": "風險成本",
                    "repeat_cost": "重複成本",
                    "utility": "Utility",
                    "eligible": "符合資格",
                    "selected": "實際選擇",
                },
            )
        else:
            st.info("本次執行沒有可重建的 Planner 候選評分。")

        st.markdown("#### 診斷動作與實際嘗試")
        st.caption("一個邏輯 Action 在重試時，可能包含多個實際 Attempt。")
        st.caption(
            "Hypothesis-driven Planner會在Action理由中記錄Utility、"
            "未解假設涵蓋率、風險與成本。"
        )
        if view.action_attempts:
            st.dataframe(
                [asdict(attempt) for attempt in view.action_attempts],
                hide_index=True,
                width="stretch",
                column_config={
                    "action_sequence": "Action 順序",
                    "action_id": "Action ID",
                    "tool": "工具 Tool",
                    "parameters": "參數",
                    "risk": "風險",
                    "rationale": "執行理由",
                    "attempt": "嘗試 Attempt",
                    "status": "狀態",
                    "error_code": "錯誤碼",
                    "observations": "觀察結果 Observations",
                },
            )
        else:
            st.info("Diagnostic Agent 沒有回傳可執行的工作產物。")

    with evidence_tab:
        st.markdown("#### 證據 Evidence")
        if view.evidence:
            st.dataframe(
                [asdict(evidence) for evidence in view.evidence],
                hide_index=True,
                width="stretch",
                column_config={
                    "evidence_id": "Evidence ID",
                    "claim": "證據主張 Claim",
                    "confidence": "信心值",
                    "observation_ids": "引用的 Observation IDs",
                },
            )
        else:
            st.info("本案例沒有建立 Evidence claim。")

        st.markdown("#### 獨立安全審查 Independent safety review")
        if view.safety is None:
            st.warning("Safety Reviewer 沒有回傳工作產物。")
        else:
            if view.safety.outcome == "approved":
                st.success(f"安全審查結果 Safety outcome：{view.safety.outcome}")
            else:
                st.warning(f"安全審查結果 Safety outcome：{view.safety.outcome}")
            st.write(view.safety.rationale)
            for finding in view.safety.findings:
                st.markdown(f"- {finding}")

    with outcome_tab:
        st.markdown("#### 證據綁定報告 Evidence-bound report")
        if view.report is None:
            st.info("本次執行沒有產生正式報告。")
        else:
            st.markdown(f"**{view.report.title}**")
            st.write(view.report.executive_summary)
            st.markdown(f"**Conclusion:** {view.report.conclusion}")
            st.caption(f"Evidence records: {view.report.evidence_ids}")

        st.markdown("#### 協作失敗 Collaboration failures")
        if view.failures:
            st.dataframe(
                [asdict(failure) for failure in view.failures],
                hide_index=True,
                width="stretch",
                column_config={
                    "failure_id": "Failure ID",
                    "stage": "失敗階段 Stage",
                    "role": "Agent 角色",
                    "kind": "失敗類型",
                    "request_id": "Request ID",
                    "detail": "錯誤明細",
                },
            )
        else:
            st.success("沒有記錄到 Agent 協作失敗。")

    with trace_tab:
        st.markdown("#### 完整且可重播的稽核軌跡")
        st.code(view.trace_text, language="text", line_numbers=True)

    _render_downloads(view)


def _render_downloads(view: CasePresentation) -> None:
    st.subheader("下載調查產物 Download artifacts")
    report_column, json_column, trace_column = st.columns(3)
    report_column.download_button(
        "下載工程報告 (.md)",
        data=case_report_markdown(view),
        file_name=f"{view.case_id}-report.md",
        mime="text/markdown",
        on_click="ignore",
        width="stretch",
    )
    json_column.download_button(
        "下載結構化結果 (.json)",
        data=case_json(view),
        file_name=f"{view.case_id}-result.json",
        mime="application/json",
        on_click="ignore",
        width="stretch",
    )
    trace_column.download_button(
        "下載稽核軌跡 (.txt)",
        data=view.trace_text,
        file_name=f"{view.case_id}-trace.txt",
        mime="text/plain",
        on_click="ignore",
        width="stretch",
    )


def _compact_action_rows(view: CasePresentation) -> list[dict[str, object]]:
    rows: dict[int, dict[str, object]] = {}
    for attempt in view.action_attempts:
        row = rows.setdefault(
            attempt.action_sequence,
            {
                "步驟": attempt.action_sequence,
                "檢查工具": attempt.tool,
                "檢查目的": attempt.rationale.split(" Utility=", 1)[0],
                "Observation": "尚未取得觀察結果",
            },
        )
        if attempt.observations:
            row["Observation"] = attempt.observations.split(" values=", 1)[0]
    return list(rows.values())


def _compact_hypothesis_rows(view: CasePresentation) -> list[dict[str, object]]:
    return [
        {
            "候選原因": hypothesis.statement,
            "狀態": HYPOTHESIS_STATUS_LABELS[hypothesis.status],
            "支持／反對": (
                f"支持 {len(hypothesis.supporting_observation_ids.split(', ')) if hypothesis.supporting_observation_ids else 0}｜"
                f"反對 {len(hypothesis.contradicting_observation_ids.split(', ')) if hypothesis.contradicting_observation_ids else 0}"
            ),
        }
        for hypothesis in view.hypotheses
    ]


def _render_compact_case_details(view: CasePresentation) -> None:
    st.subheader("調查結果")
    columns = st.columns(4)
    columns[0].metric("工作流", view.workflow_status, border=True)
    columns[1].metric("工具呼叫", str(len(_compact_action_rows(view))), border=True)
    columns[2].metric("Evidence", str(len(view.evidence)), border=True)
    columns[3].metric(
        "安全審查",
        view.safety.outcome if view.safety is not None else "none",
        border=True,
    )
    _render_case_status(view)

    st.markdown("#### 結論")
    if view.report is not None:
        st.success(view.report.conclusion)
    elif view.safety is not None:
        st.warning(f"未產生正式結論：{view.safety.rationale}")
    else:
        st.warning("本次執行沒有足夠產物形成結論。")

    st.markdown("#### 關鍵檢查")
    action_rows = _compact_action_rows(view)
    if action_rows:
        st.dataframe(action_rows, hide_index=True, width="stretch")
    else:
        st.info("沒有可顯示的診斷檢查。")

    st.markdown("#### 最終候選原因")
    if view.hypotheses:
        st.dataframe(
            _compact_hypothesis_rows(view),
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("沒有可顯示的診斷假設。")

    st.markdown("#### Evidence")
    if view.evidence:
        for evidence in view.evidence:
            st.markdown(f"- {evidence.claim}（信心值 {evidence.confidence:.2f}）")
    else:
        st.info("目前沒有足以成立的 Evidence claim。")

    with st.expander("查看 Hypothesis 演化"):
        st.caption("每筆 Observation 如何改變所有候選原因。")
        st.dataframe(
            _hypothesis_evolution_rows(view),
            hide_index=True,
            width="stretch",
        )

    with st.expander("查看 Planner 選擇理由"):
        selected_candidates = [
            asdict(candidate)
            for candidate in view.planner_candidates
            if candidate.selected
        ]
        if selected_candidates:
            st.dataframe(selected_candidates, hide_index=True, width="stretch")
        else:
            st.info("沒有可顯示的 Planner 候選評分。")

    _render_downloads(view)


def _incident_workbench() -> None:
    st.title("製造事件調查台")
    st.caption(
        "操作員只輸入可觀察的症狀；隱藏原因由模擬環境保存，"
        "不會預先交給 Diagnostic Agent。"
    )
    cases = _case_lookup()
    selected_symptom = st.selectbox(
        "回報症狀 Observed symptom",
        options=tuple(SYMPTOM_CASES),
        help="這是現場人員實際看得到的異常範圍，不是 Root Cause。",
    )
    case_ids = SYMPTOM_CASES[selected_symptom]
    selected_id = st.selectbox(
        "選擇可重播模擬批次 Simulation batch",
        options=case_ids,
        format_func=lambda case_id: SIMULATION_BATCH_LABELS[case_id],
        help="批次只用來固定模擬世界；標籤不會透露隱藏故障原因。",
    )
    selected = cases[selected_id]
    incident = selected.scenario.incident
    st.markdown(f"**事件 Incident：** `{incident.incident_id}` — {incident.title}")
    st.markdown(
        f"**設備 Asset：** `{incident.asset_id}` · "
        f"**嚴重度 Severity：** `{incident.severity.value}`"
    )
    st.markdown(f"**調查目標 Goal：** {incident.goal}")
    st.caption(
        f"模擬批次 seed={selected.scenario.seed} · Action 上限={selected.action_limit}。"
        "Root Cause 與 Benchmark answer key 在調查期間對 Agent 隱藏。"
    )
    with st.expander("為什麼還需要模擬批次？"):
        st.write(
            "本專案沒有連接真實機台，因此批次負責提供可重播的隱藏環境。"
            "Diagnostic Agent 只能透過 Tool 讀取 Observation；調查結束後，"
            "Evaluator 才使用 answer key 驗證結果。"
        )

    st.markdown("#### 請確認事件內容")
    st.caption(
        "以下是工程師可直接修改的現場回報。未知欄位可以保持未提供；"
        "Agent 後續仍會用 Tool 驗證，而不會把回報直接當成 Evidence。"
    )
    operator_note = st.text_area(
        "異常描述",
        value=selected_symptom,
        placeholder="例如：ST-02 可以 ping，但數值已經三十分鐘沒有更新。",
        help=(
            "這段內容會寫入 Incident 與 Raw Trace；本機模式可選用 Ollama 協助填表。"
            if _local_ollama_enabled()
            else "這段內容會寫入 Incident 與 Raw Trace；目前不會由 NLP 自動解析。"
        ),
    )
    raw_text = operator_note.strip() or selected_symptom
    ollama_suggestion = (
        _render_local_intake_assistant(
            raw_text=raw_text,
            asset_id=incident.asset_id,
            symptom_type=SYMPTOM_TYPES[selected_symptom],
        )
        if _local_ollama_enabled()
        else None
    )
    duration_minutes = st.number_input(
        "已知持續時間（分鐘）",
        min_value=0,
        value=None,
        step=1,
        placeholder="未提供",
        help="留空代表目前不知道，不會被當成 0 分鐘。",
        key="intake_duration",
    )
    status_columns = st.columns(3)
    network_status = status_columns[0].selectbox(
        "網路狀態",
        options=tuple(NETWORK_STATUS_OPTIONS),
        key="intake_network",
    )
    telemetry_status = status_columns[1].selectbox(
        "Telemetry 狀態",
        options=tuple(TELEMETRY_STATUS_OPTIONS),
        key="intake_telemetry",
    )
    peer_status = status_columns[2].selectbox(
        "其他設備狀態",
        options=tuple(PEER_STATUS_OPTIONS),
        key="intake_peer",
    )

    known_asset_ids = selected.scenario.to_brief().known_asset_ids
    intake = _intake_from_form(
        raw_text=raw_text,
        asset_id=incident.asset_id,
        symptom_type=SYMPTOM_TYPES[selected_symptom],
        known_asset_ids=known_asset_ids,
        duration_minutes=(
            int(duration_minutes) if duration_minutes is not None else None
        ),
        network_reachable=NETWORK_STATUS_OPTIONS[network_status],
        telemetry_available=TELEMETRY_STATUS_OPTIONS[telemetry_status],
        peer_affected=PEER_STATUS_OPTIONS[peer_status],
        ollama_suggestion=ollama_suggestion,
    )
    with st.expander("技術與稽核資料（JSON）"):
        st.caption(
            "這是系統交換格式，不需要工程師直接修改。未來 Ollama 也必須通過相同 Schema。"
        )
        st.json(asdict(intake), expanded=True)

    if st.button(
        "確認並執行調查 Confirm & run",
        type="primary",
        width="stretch",
        icon=":material/play_arrow:",
        help="按下此按鈕即代表確認上方可編輯內容，並留下確認紀錄。",
    ):
        confirmed = confirm_intake(
            intake,
            confirmed_by="streamlit_operator",
            confirmed_at=incident.reported_at,
        )
        _run_selected_case(selected_id, confirmed)

    result = _current_case_result(selected_id)
    if result is None:
        st.info("請選擇症狀與模擬批次並執行調查，畫面才會顯示該次結果。")
        return
    st.divider()
    full_audit = st.toggle(
        "顯示完整稽核模式",
        value=False,
        help="開啟後顯示全部 12 個指標、Handoff、Attempt、Utility 與 Raw Trace。",
    )
    view = build_case_presentation(result)
    if full_audit:
        _render_full_case_details(view)
    else:
        st.caption("目前為精簡展示；技術細節可由上方切換至完整稽核模式。")
        _render_compact_case_details(view)
    if _local_ollama_enabled():
        _render_local_investigation_qa(result)


def _benchmark_dashboard() -> None:
    st.title("基準測試儀表板")
    st.caption(
        "以相同且可重播的驗收閘門，測試正常、模糊、資源受限與故障注入流程。"
    )
    if st.button(
        "執行完整 Benchmark",
        type="primary",
        width="stretch",
        icon=":material/speed:",
    ):
        _run_full_benchmark()

    view = _current_benchmark_view()
    if view is None:
        st.info("執行 Benchmark 後，即可比較全部 16 個受控案例。")
        return

    _metric_grid(view.metrics)
    if all(row.passed for row in view.rows):
        st.success("所有案例都通過正確性、安全性與資源限制閘門。")
    else:
        failed_count = sum(not row.passed for row in view.rows)
        st.error(f"有 {failed_count} 個 Benchmark 案例未通過全部閘門。")

    st.subheader("案例比較 Case comparison")
    st.dataframe(
        [asdict(row) for row in view.rows],
        hide_index=True,
        width="stretch",
        column_config={
            "case": "案例 Case",
            "workflow": "工作流狀態",
            "diagnostic": "診斷狀態",
            "precision": "Evidence precision",
            "recall": "Evidence recall",
            "hypothesis_resolution": "假設解析率",
            "unsupported_claim_rate": "無根據主張率",
            "redundant_tool_rate": "重複工具率",
            "tool_calls": "實際工具呼叫",
            "handoffs": "Agent 交接",
            "failure": "故障類型",
            "passed": "是否通過",
        },
    )
    st.subheader("Planner A/B 比較")
    st.caption(
        "在相同 Scenario 與 seed 下隔離執行 rule-based 與 hypothesis-driven Planner；"
        "確認動作成本與結果一致，同時顯示假設解析程度。"
    )
    st.dataframe(
        [asdict(row) for row in st.session_state["planner_comparison"]],
        hide_index=True,
        width="stretch",
        column_config={
            "case": "案例 Case",
            "rule_status": "Rule 狀態",
            "hypothesis_status": "Hypothesis 狀態",
            "rule_actions": "Rule Actions",
            "hypothesis_actions": "Hypothesis Actions",
            "action_delta": "Action 差值",
            "same_tool_sequence": "工具順序相同",
            "same_evidence": "Evidence 相同",
            "hypothesis_resolution": "假設解析率",
        },
    )
    with st.expander("彙總文字 Aggregate summary"):
        st.code(view.summary_text, language="text")

    st.subheader("下載 Benchmark 產物")
    json_column, csv_column, text_column = st.columns(3)
    json_column.download_button(
        "下載完整 Benchmark (.json)",
        data=benchmark_json(view),
        file_name="agent-evaluation-benchmark.json",
        mime="application/json",
        on_click="ignore",
        width="stretch",
    )
    csv_column.download_button(
        "下載案例表格 (.csv)",
        data=benchmark_csv(view),
        file_name="agent-evaluation-benchmark.csv",
        mime="text/csv",
        on_click="ignore",
        width="stretch",
    )
    text_column.download_button(
        "下載彙總結果 (.txt)",
        data=view.summary_text,
        file_name="agent-evaluation-benchmark.txt",
        mime="text/plain",
        on_click="ignore",
        width="stretch",
    )


def _about() -> None:
    st.title("關於本實驗室")
    st.markdown(
        """
這是一個用於學習與展示「安全 Agentic AI」的製造事件調查實驗室。系統使用
合成情境、受限制工具、結構化 Handoff、獨立安全審查、Evidence-bound report
與受控 Benchmark，讓每個決策都能被重播與稽核。

目前 App 預設採用 deterministic hypothesis-driven utility policy，並保留 rule-based baseline。
核心另提供 provider-neutral 的 Structured LLM Planner adapter，但公開 App **沒有呼叫 LLM 或外部 API**；
只有在本機明確開啟 Ollama 模式時，才會增加自然語言 Intake 與 Evidence-bound 問答。
模型只能提出結構化決策，Tool allowlist、參數、Evidence 與 fallback 仍由 deterministic runtime 控制。
專案也不連接真實生產設備或使用機密工廠資料，因此畫面結果不代表真實產線準確率。
"""
    )


def main() -> None:
    st.set_page_config(
        page_title="Agentic 製造事件實驗室",
        page_icon=":material/precision_manufacturing:",
        layout="wide",
    )
    st.sidebar.title("Agentic 事件實驗室")
    page = st.sidebar.radio(
        "功能選單 Workspace",
        (WORKBENCH_PAGE, BENCHMARK_PAGE, ABOUT_PAGE),
    )
    st.sidebar.caption(
        "可重播 · 合成資料 · 只讀診斷 · 預設無 LLM"
    )
    if _local_ollama_enabled():
        st.sidebar.success(f"本機 Ollama 增強模式 · {DEFAULT_OLLAMA_MODEL}")
    st.sidebar.caption(f"介面版本：{APP_RELEASE}")

    if page == WORKBENCH_PAGE:
        _incident_workbench()
    elif page == BENCHMARK_PAGE:
        _benchmark_dashboard()
    else:
        _about()


if __name__ == "__main__":
    main()
