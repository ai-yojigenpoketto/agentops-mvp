"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";

type Json = any;

type Step = {
  id: string;
  title: string;
  what: string; // 做了什么
  check: string; // 检查了什么
  saw: string; // 看到了什么
  means: string; // 说明了什么
  endpoint?: string;
  method?: "GET" | "POST";
};

function pretty(x: any) {
  try {
    return JSON.stringify(x, null, 2);
  } catch {
    return String(x);
  }
}

async function safeFetchJSON(url: string, init?: RequestInit) {
  try {
    const res = await fetch(url, init);
    const text = await res.text();
    let json: any = null;
    try {
      json = JSON.parse(text);
    } catch {}
    return { ok: res.ok, status: res.status, text, json, error: null };
  } catch (err: any) {
    // Detect CORS errors
    if (err instanceof TypeError && err.message.includes("Failed to fetch")) {
      return {
        ok: false,
        status: 0,
        text: "",
        json: null,
        error: "CORS_ERROR",
        message: "CORS blocked. Ensure FastAPI has CORSMiddleware with allow_origins=['http://localhost:3000']"
      };
    }
    return {
      ok: false,
      status: 0,
      text: "",
      json: null,
      error: "NETWORK_ERROR",
      message: err.message || String(err)
    };
  }
}

function nowTs() {
  return new Date().toISOString();
}

export default function AgentOpsDebugPage() {
  const [baseUrl, setBaseUrl] = useState("http://localhost:8000");

  // Demo payload (跟你现在项目兼容的字段风格)
  const [payloadText, setPayloadText] = useState(
    pretty({
      run_id: "demo-run-001",
      agent_name: "order-agent",
      agent_version: "1.0.0",
      model: "gpt-4",
      environment: "staging",
      started_at: "2026-01-12T02:20:00Z",
      ended_at: "2026-01-12T02:20:30Z",
      status: "failure",
      error_message: "Tool call validation error",
      error_type: "ToolCallFailed",
      correlation_ids: ["req-123"],
      steps: [
        {
          step_id: "11111111-1111-1111-1111-111111111111",
          name: "Plan",
          status: "success",
          started_at: "2026-01-12T02:20:00Z",
          ended_at: "2026-01-12T02:20:03Z",
          input_summary: "User asks for order status",
          output_summary: "Need to call order_lookup_api",
          retries: 0,
          latency_ms: 3000
        },
        {
          step_id: "22222222-2222-2222-2222-222222222222",
          name: "Call tool",
          status: "failure",
          started_at: "2026-01-12T02:20:03Z",
          ended_at: "2026-01-12T02:20:06Z",
          input_summary: "Call order_lookup_api with order_id",
          output_summary: "ValidationError",
          retries: 1,
          latency_ms: 3000
        }
      ],
      tool_calls: [
        {
          call_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
          step_id: "22222222-2222-2222-2222-222222222222",
          tool_name: "order_lookup_api",
          status: "failure",
          args_json: { orderId: 123 },
          args_hash: "hash-order-lookup-001",
          result_summary: "Pydantic ValidationError: order_id missing",
          error_class: "ValidationError",
          error_message: "field required: order_id",
          status_code: 400,
          latency_ms: 3000,
          retries: 1
        }
      ],
      guardrail_events: [
        {
          event_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
          type: "schema_validation",
          message: "Tool args schema validation failed",
          call_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
          created_at: "2026-01-12T02:20:06Z"
        }
      ],
      cost: { tokens_prompt: 800, tokens_completion: 200, total_cost_usd: 0.01 }
    })
  );

  const [runId, setRunId] = useState("demo-run-001");
  const [rcaRunId, setRcaRunId] = useState("");
  const [activeStepId, setActiveStepId] = useState("health");

  // UI logs
  const [terminal, setTerminal] = useState<string[]>([]);
  const pushLog = (line: string) =>
    setTerminal((prev) => [...prev, `[${nowTs()}] ${line}`]);

  const [lastResponse, setLastResponse] = useState<{ status?: number; body?: string }>({});

  // SSE
  const esRef = useRef<EventSource | null>(null);
  const [sseConnected, setSseConnected] = useState(false);
  const [sseLines, setSseLines] = useState<string[]>([]);

  const steps: Step[] = useMemo(
    () => [
      {
        id: "docker",
        title: "0) Docker Compose：把 4 个服务跑起来",
        what: "docker compose up -d --build（启动 API/Worker/Postgres/Redis）",
        check: "docker compose ps + 看 health",
        saw: "api/worker/postgres/redis 都 Up，postgres/redis healthy，API 暴露 8000",
        means: "说明基础设施 OK：后面的问题不是“环境起不来”，而是业务/队列/数据"
      },
      {
        id: "health",
        title: "1) Health Check：HTTP 通路是否打通",
        what: "GET / （相当于 curl http://localhost:8000/）",
        check: "HTTP status=200 + 返回 JSON",
        saw: "看到了 {status: ok ...}",
        means: "说明：网络 → Uvicorn → FastAPI 路由 → 返回序列化 全链路 OK",
        endpoint: "/",
        method: "GET"
      },
      {
        id: "ingest",
        title: "2) Ingest：把一次 Agent Run 写进 DB",
        what: "POST /agent-runs 发送一份 run payload",
        check: "响应成功 + DB 有数据（内部通过 SQLAlchemy INSERT）",
        saw: "看到了 run_id 被存储；日志里会出现 INSERT agent_runs/steps/tool_calls",
        means: "说明：Pydantic 校验 + API 解析 + DB 持久化 OK",
        endpoint: "/agent-runs",
        method: "POST"
      },
      {
        id: "enqueue",
        title: "3) Create RCA：把 RCA 任务丢进队列",
        what: "POST /agent-runs/{run_id}/rca-runs 创建 rca_run_id",
        check: "拿到 rca_run_id + worker 监听 rca 队列并处理",
        saw: "看到了 rca_run_id；worker logs 会有 Listening on rca",
        means: "说明：HTTP 触发 → Redis 队列 enqueue → worker 消费 OK",
        endpoint: "/agent-runs/{run_id}/rca-runs",
        method: "POST"
      },
      {
        id: "poll",
        title: "4) Poll：查询 RCA 状态 + 拿结构化报告",
        what: "GET /agent-runs/rca-runs/{rca_run_id}",
        check: "status 从 queued/running → done；report 不为空",
        saw: "看到了 category/tool_schema_mismatch + evidence_index + action_items",
        means: "说明：RCAReport 是“机器可读”的结构化产物（不是一段文本）",
        endpoint: "/agent-runs/rca-runs/{rca_run_id}",
        method: "GET"
      },
      {
        id: "sse",
        title: "5) SSE：实时进度 + ping keepalive",
        what: "GET /rca-runs/{rca_run_id}/stream 建立 EventStream",
        check: "收到 data: {...} 事件 + : ping 注释行",
        saw: "看到了 done 事件；以及持续的 ping",
        means: "说明：长任务用户体验 OK（不卡死），并且连接可保持",
        endpoint: "/rca-runs/{rca_run_id}/stream",
        method: "GET"
      }
    ],
    []
  );

  const activeStep = steps.find((s) => s.id === activeStepId) ?? steps[1];

  // Actions
  async function doHealth() {
    pushLog("→ Health: GET /");
    const r = await safeFetchJSON(`${baseUrl}/`);
    if ((r as any).error === "CORS_ERROR") {
      pushLog(`✗ CORS ERROR: ${(r as any).message}`);
      setLastResponse({ status: 0, body: `⚠️ CORS BLOCKED\n\n${(r as any).message}` });
      return;
    }
    setLastResponse({ status: r.status, body: r.json ? pretty(r.json) : r.text });
    pushLog(`← Health: ${r.status} ${r.ok ? "OK" : "FAIL"}`);
  }

  async function doIngest() {
    let bodyObj: any;
    try {
      bodyObj = JSON.parse(payloadText);
    } catch (e: any) {
      pushLog(`✗ Payload JSON parse error: ${e?.message ?? String(e)}`);
      return;
    }
    const rid = bodyObj?.run_id;
    if (rid) setRunId(rid);

    pushLog("→ Ingest: POST /agent-runs");
    const r = await safeFetchJSON(`${baseUrl}/agent-runs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(bodyObj)
    });
    if ((r as any).error === "CORS_ERROR") {
      pushLog(`✗ CORS ERROR: ${(r as any).message}`);
      setLastResponse({ status: 0, body: `⚠️ CORS BLOCKED\n\n${(r as any).message}` });
      return;
    }
    setLastResponse({ status: r.status, body: r.json ? pretty(r.json) : r.text });
    pushLog(`← Ingest: ${r.status} ${r.ok ? "OK" : "FAIL"}`);
  }

  async function doCreateRCA() {
    if (!runId) {
      pushLog("✗ runId is empty. Ingest first or set runId.");
      return;
    }
    pushLog(`→ Create RCA: POST /agent-runs/${runId}/rca-runs`);
    const r = await safeFetchJSON(`${baseUrl}/agent-runs/${encodeURIComponent(runId)}/rca-runs`, {
      method: "POST"
    });
    if ((r as any).error === "CORS_ERROR") {
      pushLog(`✗ CORS ERROR: ${(r as any).message}`);
      setLastResponse({ status: 0, body: `⚠️ CORS BLOCKED\n\n${(r as any).message}` });
      return;
    }
    setLastResponse({ status: r.status, body: r.json ? pretty(r.json) : r.text });
    const id = r.json?.rca_run_id;
    if (id) {
      setRcaRunId(id);
      pushLog(`✓ rca_run_id = ${id}`);
    }
    pushLog(`← Create RCA: ${r.status} ${r.ok ? "OK" : "FAIL"}`);
  }

  async function doGetRCA() {
    if (!rcaRunId) {
      pushLog("✗ rcaRunId is empty. Create RCA first.");
      return;
    }
    pushLog(`→ Get RCA: GET /agent-runs/rca-runs/${rcaRunId}`);
    const r = await safeFetchJSON(`${baseUrl}/agent-runs/rca-runs/${encodeURIComponent(rcaRunId)}`);
    if ((r as any).error === "CORS_ERROR") {
      pushLog(`✗ CORS ERROR: ${(r as any).message}`);
      setLastResponse({ status: 0, body: `⚠️ CORS BLOCKED\n\n${(r as any).message}` });
      return;
    }
    setLastResponse({ status: r.status, body: r.json ? pretty(r.json) : r.text });
    pushLog(`← Get RCA: ${r.status} ${r.ok ? "OK" : "FAIL"}`);

    // Show compact summary if report is ready
    if (r.json?.report) {
      const rep = r.json.report;
      pushLog(`  → Category: ${rep.category || "unknown"}`);
      pushLog(`  → Insufficient Evidence: ${rep.insufficient_evidence || false}`);
      pushLog(`  → Hypotheses: ${rep.hypotheses?.length || 0}`);
      pushLog(`  → Action Items: ${rep.action_items?.length || 0}`);
    }
  }

  async function doPollUntilDone(maxMs = 15000, intervalMs = 700) {
    if (!rcaRunId) {
      pushLog("✗ rcaRunId is empty. Create RCA first.");
      return;
    }
    const start = Date.now();
    pushLog(`↻ Polling until done (<= ${maxMs}ms) ...`);
    while (Date.now() - start < maxMs) {
      const r = await safeFetchJSON(`${baseUrl}/agent-runs/rca-runs/${encodeURIComponent(rcaRunId)}`);
      if ((r as any).error === "CORS_ERROR") {
        pushLog(`✗ CORS ERROR during polling: ${(r as any).message}`);
        setLastResponse({ status: 0, body: `⚠️ CORS BLOCKED\n\n${(r as any).message}` });
        return;
      }
      const status = r.json?.status ?? "(unknown)";
      pushLog(`… status = ${status}`);
      setLastResponse({ status: r.status, body: r.json ? pretty(r.json) : r.text });
      if (status === "done" || status === "error") {
        pushLog(`✓ Poll finished: ${status}`);
        // Show summary if done and has report
        if (status === "done" && r.json?.report) {
          const rep = r.json.report;
          pushLog(`  → Category: ${rep.category || "unknown"}`);
          pushLog(`  → Insufficient Evidence: ${rep.insufficient_evidence || false}`);
          pushLog(`  → Evidence Count: ${rep.evidence_index?.length || 0}`);
        }
        return;
      }
      await new Promise((res) => setTimeout(res, intervalMs));
    }
    pushLog("⚠ Poll timeout (still not done). Check worker logs.");
  }

  function connectSSE() {
    if (!rcaRunId) {
      pushLog("✗ rcaRunId is empty. Create RCA first.");
      return;
    }
    disconnectSSE();
    const url = `${baseUrl}/rca-runs/${encodeURIComponent(rcaRunId)}/stream`;
    pushLog(`↔ SSE connect: ${url}`);

    try {
      const es = new EventSource(url);
      esRef.current = es;
      setSseConnected(true);

      es.onopen = () => {
        pushLog(`✓ SSE connection opened`);
        setSseLines((prev) => [...prev, `[${nowTs()}] SSE connected`]);
      };

      es.onmessage = (ev: MessageEvent) => {
        // Parse the JSON data and show progress
        try {
          const data = JSON.parse(ev.data);
          const line = `[${nowTs()}] ${data.status || "?"} | ${data.step || "?"} | ${data.pct || 0}% | ${data.message || ""}`;
          setSseLines((prev: string[]) => [...prev, line]);
          pushLog(line);

          // Close connection if done or error
          if (data.status === "done" || data.status === "error") {
            pushLog(`✓ SSE stream complete: ${data.status}`);
            setTimeout(() => disconnectSSE(), 1000);
          }
        } catch {
          // If not JSON, just show raw data
          setSseLines((prev: string[]) => [...prev, `[${nowTs()}] data: ${ev.data}`]);
        }
      };

      es.onerror = () => {
        const msg = `(!) SSE error / disconnected. This may be due to CORS if running cross-origin.`;
        setSseLines((prev: string[]) => [...prev, `[${nowTs()}] ${msg}`]);
        pushLog(`✗ ${msg}`);
        setSseConnected(false);
        // Close the connection
        if (esRef.current) {
          esRef.current.close();
          esRef.current = null;
        }
      };
    } catch (e: any) {
      pushLog(`✗ SSE failed to connect: ${e?.message ?? String(e)}`);
      pushLog(`  Hint: EventSource may not work cross-origin without proper CORS headers`);
      setSseConnected(false);
    }
  }

  function disconnectSSE() {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    setSseConnected(false);
  }

  async function runWholeJourney() {
    setTerminal([]);
    setSseLines([]);
    disconnectSSE();
    pushLog("▶ Run Journey: health → ingest → create rca → poll → sse");

    await doHealth();
    await doIngest();
    await doCreateRCA();
    await doPollUntilDone();
    connectSSE();

    pushLog("✅ Journey complete (SSE connected if no CORS issues).");
  }

  useEffect(() => {
    return () => disconnectSSE();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen w-full bg-neutral-950 text-neutral-100">
      <div className="mx-auto max-w-6xl px-4 py-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-2xl font-semibold">AgentOps Debug UI (Live)</div>
            <div className="text-sm text-neutral-300 mt-1">
              把 “curl 做了什么” 变成可点击、可复盘、可面试表达的可视化证据链。
            </div>
          </div>

          <button
            onClick={runWholeJourney}
            className="rounded-xl bg-emerald-600 hover:bg-emerald-500 px-4 py-2 text-sm font-medium"
          >
            ▶ 一键跑完整流程
          </button>
        </div>

        <div className="grid grid-cols-12 gap-4 mt-6">
          {/* Left: Steps */}
          <div className="col-span-12 md:col-span-5">
            <div className="rounded-2xl border border-neutral-800 bg-neutral-900/50 p-4">
              <div className="text-sm font-semibold text-neutral-200 mb-3">流程步骤</div>
              <div className="space-y-2">
                {steps.map((s: Step) => {
                  const active = s.id === activeStepId;
                  return (
                    <button
                      key={s.id}
                      onClick={() => setActiveStepId(s.id)}
                      className={`w-full text-left rounded-xl border px-3 py-2 transition ${
                        active
                          ? "border-emerald-500 bg-emerald-500/10"
                          : "border-neutral-800 hover:border-neutral-700 bg-neutral-950/30"
                      }`}
                    >
                      <div className="text-sm font-medium">{s.title}</div>
                      <div className="text-xs text-neutral-400 mt-1">
                        {s.endpoint ? `${s.method} ${s.endpoint}` : "（终端命令：docker compose ...）"}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="rounded-2xl border border-neutral-800 bg-neutral-900/50 p-4 mt-4">
              <div className="text-sm font-semibold text-neutral-200 mb-3">连接配置</div>

              <div className="text-xs text-neutral-400 mb-1">Base URL</div>
              <input
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                className="w-full rounded-xl bg-neutral-950 border border-neutral-800 px-3 py-2 text-sm"
                placeholder="http://localhost:8000"
              />

              <div className="grid grid-cols-2 gap-3 mt-3">
                <div>
                  <div className="text-xs text-neutral-400 mb-1">run_id</div>
                  <input
                    value={runId}
                    onChange={(e) => setRunId(e.target.value)}
                    className="w-full rounded-xl bg-neutral-950 border border-neutral-800 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <div className="text-xs text-neutral-400 mb-1">rca_run_id</div>
                  <input
                    value={rcaRunId}
                    onChange={(e) => setRcaRunId(e.target.value)}
                    className="w-full rounded-xl bg-neutral-950 border border-neutral-800 px-3 py-2 text-sm"
                  />
                </div>
              </div>

              <div className="flex flex-wrap gap-2 mt-4">
                <button
                  onClick={doHealth}
                  className="rounded-xl border border-neutral-700 bg-neutral-950/40 hover:bg-neutral-950 px-3 py-2 text-sm"
                >
                  Health
                </button>
                <button
                  onClick={doIngest}
                  className="rounded-xl border border-neutral-700 bg-neutral-950/40 hover:bg-neutral-950 px-3 py-2 text-sm"
                >
                  Ingest
                </button>
                <button
                  onClick={doCreateRCA}
                  className="rounded-xl border border-neutral-700 bg-neutral-950/40 hover:bg-neutral-950 px-3 py-2 text-sm"
                >
                  Create RCA
                </button>
                <button
                  onClick={doGetRCA}
                  className="rounded-xl border border-neutral-700 bg-neutral-950/40 hover:bg-neutral-950 px-3 py-2 text-sm"
                >
                  Get RCA
                </button>
                <button
                  onClick={() => doPollUntilDone()}
                  className="rounded-xl border border-neutral-700 bg-neutral-950/40 hover:bg-neutral-950 px-3 py-2 text-sm"
                >
                  Poll Until Done
                </button>
              </div>

              <div className="flex flex-wrap items-center gap-2 mt-3">
                <button
                  onClick={connectSSE}
                  className="rounded-xl bg-sky-600 hover:bg-sky-500 px-3 py-2 text-sm font-medium"
                >
                  SSE Connect
                </button>
                <button
                  onClick={disconnectSSE}
                  className="rounded-xl border border-neutral-700 bg-neutral-950/40 hover:bg-neutral-950 px-3 py-2 text-sm"
                >
                  SSE Disconnect
                </button>
                <span
                  className={`text-xs px-2 py-1 rounded-full border ${
                    sseConnected
                      ? "border-emerald-500 text-emerald-300 bg-emerald-500/10"
                      : "border-neutral-700 text-neutral-400 bg-neutral-950/40"
                  }`}
                >
                  {sseConnected ? "SSE: connected" : "SSE: disconnected"}
                </span>
              </div>
            </div>
          </div>

          {/* Right: Details + Outputs */}
          <div className="col-span-12 md:col-span-7 space-y-4">
            <div className="rounded-2xl border border-neutral-800 bg-neutral-900/50 p-4">
              <div className="text-sm font-semibold text-neutral-200 mb-2">当前步骤解释（面试用）</div>

              <div className="grid grid-cols-1 gap-3">
                <div className="rounded-xl border border-neutral-800 bg-neutral-950/40 p-3">
                  <div className="text-xs text-neutral-400">做了什么</div>
                  <div className="text-sm mt-1">{activeStep.what}</div>
                </div>
                <div className="rounded-xl border border-neutral-800 bg-neutral-950/40 p-3">
                  <div className="text-xs text-neutral-400">检查了什么</div>
                  <div className="text-sm mt-1">{activeStep.check}</div>
                </div>
                <div className="rounded-xl border border-neutral-800 bg-neutral-950/40 p-3">
                  <div className="text-xs text-neutral-400">看到了什么</div>
                  <div className="text-sm mt-1">{activeStep.saw}</div>
                </div>
                <div className="rounded-xl border border-neutral-800 bg-neutral-950/40 p-3">
                  <div className="text-xs text-neutral-400">说明了什么</div>
                  <div className="text-sm mt-1">{activeStep.means}</div>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-neutral-800 bg-neutral-900/50 p-4">
              <div className="text-sm font-semibold text-neutral-200 mb-2">Ingest Payload（你可以改）</div>
              <textarea
                value={payloadText}
                onChange={(e) => setPayloadText(e.target.value)}
                className="w-full min-h-[220px] rounded-xl bg-neutral-950 border border-neutral-800 px-3 py-2 text-xs font-mono"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-2xl border border-neutral-800 bg-neutral-900/50 p-4">
                <div className="text-sm font-semibold text-neutral-200 mb-2">
                  Last HTTP Response{" "}
                  <span className="text-xs text-neutral-400">
                    {lastResponse.status ? `(status ${lastResponse.status})` : ""}
                  </span>
                </div>
                <pre className="whitespace-pre-wrap break-words rounded-xl bg-neutral-950 border border-neutral-800 p-3 text-xs font-mono max-h-[240px] overflow-auto">
                  {lastResponse.body ?? "(no response yet)"}
                </pre>
              </div>

              <div className="rounded-2xl border border-neutral-800 bg-neutral-900/50 p-4">
                <div className="text-sm font-semibold text-neutral-200 mb-2">SSE Stream</div>
                <div className="rounded-xl bg-neutral-950 border border-neutral-800 p-3 text-xs font-mono max-h-[240px] overflow-auto">
                  {sseLines.length === 0 ? (
                    <div className="text-neutral-400">(no SSE events yet)</div>
                  ) : (
                    sseLines.map((l: string, i: number) => (
                      <div key={i} className="whitespace-pre-wrap break-words">
                        {l}
                      </div>
                    ))
                  )}
                  {/* 说明：curl 看到的 : ping 是 comment，不一定会进 EventSource 的 onmessage */}
                  <div className="text-neutral-500 mt-3">
                    注：你 curl 看到的 “: ping …” 属于 SSE comment keepalive，浏览器 EventSource 不一定会回调 onmessage。
                  </div>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-neutral-800 bg-neutral-900/50 p-4">
              <div className="text-sm font-semibold text-neutral-200 mb-2">Terminal / Evidence Log</div>
              <div className="rounded-xl bg-neutral-950 border border-neutral-800 p-3 text-xs font-mono max-h-[260px] overflow-auto">
                {terminal.length === 0 ? (
                  <div className="text-neutral-400">(empty)</div>
                ) : (
                  terminal.map((l: string, i: number) => (
                    <div key={i} className="whitespace-pre-wrap break-words">
                      {l}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="text-xs text-neutral-500 mt-6">
          Tip：你面试说这套系统时，按步骤讲 “HTTP 触发 → 入库 → enqueue → worker 消费 → 产出结构化报告 → SSE 反馈进度”，
          每一步都能用 UI 的请求/返回/日志当证据。
        </div>
      </div>
    </div>
  );
}