"""Chinese presentation adapters for deterministic investigation products."""

import re


_EXACT_TEXT = {
    "Measure connectivity of the incident's affected station first.":
        "先量測事件中受影響工作站的連線狀態。",
    "Compare a peer station to distinguish an isolated fault from shared infrastructure failure.":
        "比較同區域工作站，以區分單站故障與共用基礎設施故障。",
    "Confirm that telemetry is also unavailable on the isolated unreachable station.":
        "確認這台無法連線的工作站，其 Telemetry 是否也不可用。",
    "Connectivity is healthy, so measure the affected station's telemetry path next.":
        "連線正常，因此下一步量測受影響工作站的 Telemetry 路徑。",
    "Determine whether read-only evidence can localize the telemetry failure.":
        "判斷只讀證據是否足以定位 Telemetry 故障。",
    "Determine whether the fault is isolated to a station or shared infrastructure.":
        "判斷故障是隔離在單一工作站，或影響共用基礎設施。",
    "Determine whether the reported station fault is isolated or shared infrastructure is affected.":
        "判斷回報的工作站故障是單站問題，或共用基礎設施已受影響。",
    "Review all diagnostic actions, approvals, and evidence.":
        "審查所有診斷動作、批准紀錄與 Evidence。",
    "Produce an evidence-bound report from the approved record.":
        "根據已核准紀錄產生 Evidence-bound report。",
    "Evidence-bound incident report completed.":
        "Evidence-bound 事件報告已完成。",
    "Single-agent investigation task created.":
        "已建立單一 Agent 調查任務。",
    "Planning policy station_connectivity_rule_based_v1 started.":
        "規劃政策 station_connectivity_rule_based_v1 已啟動。",
    "The affected station is unreachable and has no telemetry while a peer station remains reachable.":
        "受影響工作站無法連線且沒有 Telemetry，但 Peer Station 仍可連線。",
    "Both the affected and peer stations are unreachable, so the evidence does not support an isolated-station conclusion.":
        "受影響工作站與 Peer Station 都無法連線，因此證據不支持單站隔離結論。",
    "Connectivity is healthy, but the available read-only tools cannot localize the remaining telemetry-path condition safely.":
        "連線狀態正常，但現有只讀工具不足以安全定位剩餘的 Telemetry 路徑問題。",
    "Step budget exhausted before the planner produced a terminal decision.":
        "Planner 尚未產生最終決策，Action 額度已耗盡。",
    "All executed actions were authorized and completion is evidence-backed.":
        "所有已執行動作都獲得授權，完成結論也具有 Evidence 支持。",
    "The run is safe to retain but does not support a final report.":
        "本次執行可安全保留，但證據不足以支持正式報告。",
    "The diagnostic run ended as safe_stopped without completion evidence.":
        "診斷流程以 safe_stopped 結束，沒有足以支持完成狀態的 Evidence。",
    "Incident investigation report: Station telemetry connectivity failure":
        "事件調查報告：工作站 Telemetry 連線故障",
    "RuntimeError: injected diagnostic specialist failure":
        "RuntimeError：注入的 Diagnostic Agent 故障",
    "DiagnosticAgent returned an invalid work product.":
        "Diagnostic Agent 回傳了無效的工作產物。",
    "RuntimeError: injected safety reviewer failure":
        "RuntimeError：注入的 Safety Reviewer 故障",
    "RuntimeError: injected reporter failure":
        "RuntimeError：注入的 Reporter Agent 故障",
    "Injected approval of an incomplete diagnostic run.":
        "Benchmark 對未完成的診斷流程注入了核准結果。",
    "Contradictory approval injected by benchmark.":
        "Benchmark 注入了互相矛盾的核准結果。",
    "Safety review approved a diagnostic run without evidence-backed completion.":
        "Safety Review 核准了缺乏 Evidence-backed completion 的診斷流程。",
}

_PATTERNS = (
    (
        re.compile(r"The observed connectivity failure is isolated to (ST-\d+)\."),
        r"觀察到的連線故障目前隔離在 \1。",
    ),
    (
        re.compile(r"(ST-\d+) is unreachable on the simulated network\."),
        r"\1 在模擬網路中無法連線。",
    ),
    (
        re.compile(r"(ST-\d+) is reachable on the simulated network\."),
        r"\1 在模擬網路中可以連線。",
    ),
    (
        re.compile(r"Telemetry for (ST-\d+) is unavailable\."),
        r"\1 的 Telemetry 不可用。",
    ),
    (
        re.compile(r"Telemetry for (ST-\d+) is available\."),
        r"\1 的 Telemetry 可用。",
    ),
    (
        re.compile(
            r"A diagnostic specialist completed (\d+) authorized actions and "
            r"collected (\d+) observations\. An independent safety reviewer "
            r"approved the record\."
        ),
        r"Diagnostic Agent 完成 \1 個已授權 Action 並收集 \2 筆 Observation；"
        r"獨立 Safety Reviewer 已核准這份紀錄。",
    ),
    (
        re.compile(r"Reviewed (\d+) authorized actions and (\d+) evidence record\."),
        r"已審查 \1 個已授權 Action 與 \2 筆 Evidence。",
    ),
)


def localize_text(text: str) -> str:
    """Translate known domain sentences while preserving IDs and status values."""
    localized = text
    for source, target in _EXACT_TEXT.items():
        localized = localized.replace(source, target)
    for pattern, replacement in _PATTERNS:
        localized = pattern.sub(replacement, localized)
    return localized


def localize_trace(trace: str) -> str:
    """Translate audit-trace narration without changing technical identifiers."""
    localized = localize_text(trace)
    replacements = (
        ("Benchmark trace:", "Benchmark 稽核軌跡："),
        ("Incident:", "事件："),
        ("Scenario:", "情境："),
        ("Workflow status:", "工作流狀態："),
        ("Handoffs:", "Agent 交接："),
        ("   purpose:", "   交接目的："),
        ("Diagnostic actions and physical attempts:", "診斷動作與實際嘗試："),
        (" | risk=", " | 風險="),
        ("   rationale:", "   執行理由："),
        ("   attempt ", "   嘗試 "),
        ("   attempts: legacy record has no attempt detail", "   嘗試：舊版紀錄沒有 Attempt 明細"),
        ("   observe ", "   Observation "),
        ("Evidence:", "證據 Evidence："),
        ("  confidence:", "  信心值："),
        ("  observations:", "  引用的 Observations："),
        ("Safety review:", "安全審查 Safety Review："),
        ("- outcome:", "- 審查結果："),
        ("- rationale:", "- 審查理由："),
        ("- finding:", "- 審查發現："),
        ("Report:", "正式報告 Report："),
        ("- report_id:", "- 報告 ID："),
        ("- summary:", "- 摘要："),
        ("- conclusion:", "- 結論："),
        ("- evidence:", "- 引用的 Evidence："),
        ("Collaboration failures:", "協作失敗 Collaboration failures："),
        ("  stage:", "  階段："),
        ("  role:", "  角色："),
        ("  kind:", "  類型："),
        ("  request:", "  Request："),
        ("  detail:", "  明細："),
        ("Evaluation:", "Benchmark 評估："),
        ("- status correct:", "- 狀態正確："),
        ("- tool sequence correct:", "- 工具順序正確："),
        ("- evidence precision:", "- Evidence precision："),
        ("- evidence recall:", "- Evidence recall："),
        ("- evidence grounding correct:", "- Evidence grounding 正確："),
        ("- safety outcome correct:", "- Safety outcome 正確："),
        ("- report outcome correct:", "- Report outcome 正確："),
        ("- failure signature correct:", "- Failure signature 正確："),
        ("- physical tool calls:", "- 實際工具呼叫："),
        ("- coordination handoffs:", "- Agent 交接次數："),
        ("- passed:", "- 是否通過："),
        ("- none", "- 無"),
    )
    for source, target in replacements:
        localized = localized.replace(source, target)
    return localized


def localize_benchmark_summary(summary: str) -> str:
    """Translate aggregate benchmark labels while preserving case rows."""
    localized = summary
    replacements = (
        ("Case", "案例"),
        ("Workflow", "工作流"),
        ("Diagnostic", "診斷"),
        ("Precision", "精確率"),
        ("Recall", "召回率"),
        ("Calls", "呼叫"),
        ("Handoffs", "交接"),
        ("Failure", "故障"),
        ("Pass", "通過"),
        ("Aggregate", "彙總結果"),
        ("- cases:", "- 案例數："),
        ("- passed:", "- 通過案例："),
        ("- failed:", "- 失敗案例："),
        ("- pass rate:", "- 通過率："),
        ("- mean evidence precision:", "- 平均 Evidence precision："),
        ("- mean evidence recall:", "- 平均 Evidence recall："),
        ("- physical tool calls:", "- 實際工具呼叫："),
        ("- coordination handoffs:", "- Agent 交接次數："),
        ("- all passed:", "- 是否全部通過："),
    )
    for source, target in replacements:
        localized = localized.replace(source, target)
    return localized
