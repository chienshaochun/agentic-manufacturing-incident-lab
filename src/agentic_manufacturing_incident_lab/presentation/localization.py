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
    "Planning policy station_hypothesis_utility_v1 started.":
        "假設效用規劃政策 station_hypothesis_utility_v1 已啟動。",
    "Planning policy manufacturing_signal_utility_v1 started.":
        "多來源製造診斷政策 manufacturing_signal_utility_v1 已啟動。",
    "Distinguish sensor staleness, configuration drift, planned maintenance, and transport-path failures.":
        "區分感測器資料過期、設定漂移、計畫性維護與傳輸路徑故障。",
    "Read alarm history for an initial symptom fingerprint.":
        "先讀取警報歷史，建立初步症狀指紋。",
    "Verify the affected station network path.":
        "確認受影響工作站的網路路徑。",
    "Verify that the telemetry transport still returns data.":
        "確認 Telemetry 傳輸仍能回傳資料。",
    "Compare the active and expected configuration versions.":
        "比較目前生效版本與預期設定版本。",
    "Check whether planned maintenance explains the signal gap.":
        "檢查計畫性維護是否能解釋訊號中斷。",
    "Measure whether source sensor values are still refreshing.":
        "量測來源感測器的數值是否仍持續更新。",
    "One cause is supported and every competing hypothesis is rejected by independent observations.":
        "一個原因已獲支持，且其他競爭假設都被獨立 Observation 排除。",
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
    "Shared network infrastructure is unavailable.":
        "共用網路基礎設施不可用。",
}

_PATTERNS = (
    (
        re.compile(r"The connectivity fault is isolated to (ST-\d+)\."),
        r"連線故障隔離在單一工作站 \1。",
    ),
    (
        re.compile(r"The telemetry path for (ST-\d+) is unavailable\."),
        r"工作站 \1 的 Telemetry 路徑不可用。",
    ),
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
        re.compile(r"Alarm history for (ST-\d+): (.*)\."),
        r"\1 的警報歷史：\2。",
    ),
    (
        re.compile(r"Configuration for (ST-\d+) matches the expected version\."),
        r"\1 的設定符合預期版本。",
    ),
    (
        re.compile(r"Configuration for (ST-\d+) differs from the expected version\."),
        r"\1 的設定與預期版本不同。",
    ),
    (
        re.compile(r"Planned maintenance for (ST-\d+) is (active|inactive)\."),
        lambda match: (
            f"{match.group(1)} 的計畫性維護"
            f"{'正在進行' if match.group(2) == 'active' else '未啟用'}。"
        ),
    ),
    (
        re.compile(r"Sensor data for (ST-\d+) is (fresh|stale) \(age=(\d+)s\)\."),
        lambda match: (
            f"{match.group(1)} 的感測器資料"
            f"{'持續更新' if match.group(2) == 'fresh' else '已過期'}"
            f"（資料年齡={match.group(3)} 秒）。"
        ),
    ),
    (
        re.compile(r"The network path for (ST-\d+) is unavailable\."),
        r"\1 的網路路徑不可用。",
    ),
    (
        re.compile(r"The telemetry service for (ST-\d+) is unavailable\."),
        r"\1 的 Telemetry 服務不可用。",
    ),
    (
        re.compile(r"Configuration drift affects (ST-\d+)\."),
        r"\1 發生設定版本漂移。",
    ),
    (
        re.compile(r"Planned maintenance explains the signal gap on (ST-\d+)\."),
        r"\1 的訊號中斷可由計畫性維護解釋。",
    ),
    (
        re.compile(r"Sensor data on (ST-\d+) is stale\."),
        r"\1 的感測器資料已過期。",
    ),
    (
        re.compile(r"The flatlined process signal is caused by stale sensor data on (ST-\d+)\."),
        r"\1 的製程訊號平線是由感測器資料過期造成。",
    ),
    (
        re.compile(r"The flatlined process signal is caused by configuration drift on (ST-\d+)\."),
        r"\1 的製程訊號平線是由設定版本漂移造成。",
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
        ("   observation quality:", "   Observation 品質："),
        ("Hypotheses:", "診斷假設 Hypotheses："),
        ("  status:", "  狀態："),
        ("  supports:", "  支持的 Observations："),
        ("  contradicts:", "  反對的 Observations："),
        ("  scoring:", "  品質加權評分："),
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
        ("- hypothesis resolution rate:", "- 假設解析率："),
        ("- unsupported claim rate:", "- 無根據主張率："),
        ("- redundant tool call rate:", "- 重複工具呼叫率："),
        ("- actions to evidence:", "- 取得 Evidence 的動作數："),
        ("- recovery success rate:", "- 恢復成功率："),
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
        ("- mean hypothesis resolution:", "- 平均假設解析率："),
        ("- unsupported claim rate:", "- 無根據主張率："),
        ("- redundant tool call rate:", "- 重複工具呼叫率："),
        ("- mean actions to evidence:", "- 平均取得 Evidence 動作數："),
        ("- recovery success rate:", "- 恢復成功率："),
        ("- all passed:", "- 是否全部通過："),
    )
    for source, target in replacements:
        localized = localized.replace(source, target)
    return localized
