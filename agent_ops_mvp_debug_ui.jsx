import React, { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { Copy, Play, Pause, RotateCcw, StepForward, TerminalSquare, ShieldCheck, Gauge, Database, Boxes, Activity, CheckCircle2 } from "lucide-react";

/**
 * AgentOps MVP Debug Journey UI
 * A visual, interview-friendly walkthrough of:
 * docker compose build/up -> health checks -> worker listening -> ingest -> create RCA -> poll RCA -> SSE stream.
 *
 * Drop into a Next.js page:
 *   export default function Page(){ return <AgentOpsDebugJourney /> }
 */

type StepTag = "Infra" | "Queue" | "API" | "DB" | "Streaming" | "Observability";

type Step = {
  id: string;
  title: string;
  tags: StepTag[];
  whyItMatters: string;
  command?: string;
  expectedSignals: string[];
  terminalOutput: string[];
  interpretation: string;
};

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

function useClipboard() {
  const [copied, setCopied] = useState(false);
  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 900);
    } catch {
      // noop
    }
  }
  return { copied, copy };
}

function Terminal({ lines, active }: { lines: string[]; active: boolean }) {
  return (
    <div className="rounded-2xl border bg-muted/30 overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2 border-b bg-background/60">
        <TerminalSquare className="h-4 w-4" />
        <div className="text-sm font-medium">Terminal</div>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs text-muted-foreground">{active ? "streaming" : "snapshot"}</span>
          <span className={`h-2 w-2 rounded-full ${active ? "bg-emerald-500" : "bg-muted-foreground/40"}`} />
        </div>
      </div>
      <div className="p-3 font-mono text-xs leading-relaxed">
        {lines.map((l, i) => (
          <div key={i} className="whitespace-pre-wrap break-words">
            {l}
          </div>
        ))}
      </div>
    </div>
  );
}

function TagPill({ tag }: { tag: StepTag }) {
  const icon =
    tag === "Infra" ? <Boxes className="h-3.5 w-3.5" /> :
    tag === "Queue" ? <Activity className="h-3.5 w-3.5" /> :
    tag === "API" ? <ShieldCheck className="h-3.5 w-3.5" /> :
    tag === "DB" ? <Database className="h-3.5 w-3.5" /> :
    tag === "Streaming" ? <Gauge className="h-3.5 w-3.5" /> :
    <CheckCircle2 className="h-3.5 w-3.5" />;

  return (
    <Badge variant="secondary" className="gap-1">
      {icon}
      {tag}
    </Badge>
  );
}

export default function AgentOpsDebugJourney() {
  const steps: Step[] = useMemo(
    () => [
      {
        id: "build-up",
        title: "Build & Start: docker compose up -d --build",
        tags: ["Infra"],
        whyItMatters:
          "Proves your system's foundation boots cleanly: API + worker + Postgres + Redis are running with consistent networking.",
        command: "docker compose up -d --build",
        expectedSignals: [
          "Containers built successfully",
          "redis/postgres become healthy",
          "api/worker started",
        ],
        terminalOutput: [
          "[+] Running 7/7",
          " ✔ Container agentops-mvp-redis-1     Healthy",
          " ✔ Container agentops-mvp-postgres-1  Healthy",
          " ✔ Container agentops-mvp-worker-1    Started",
          " ✔ Container agentops-mvp-api-1       Started",
          "",
          "NAME                      IMAGE                 STATUS                   PORTS",
          "agentops-mvp-api-1        agentops-mvp-api      Up                      0.0.0.0:8000->8000/tcp",
          "agentops-mvp-postgres-1   postgres:16-alpine    Up (healthy)            0.0.0.0:5432->5432/tcp",
          "agentops-mvp-redis-1      redis:7-alpine        Up (healthy)            0.0.0.0:6379->6379/tcp",
          "agentops-mvp-worker-1     agentops-mvp-worker   Up",
        ],
        interpretation:
          "✅ Infra is ready. If anything fails later, you now know it’s not because Redis/Postgres/API never started.",
      },
      {
        id: "ps-health",
        title: "Confirm runtime state: docker compose ps",
        tags: ["Infra", "Observability"],
        whyItMatters:
          "A quick sanity check that avoids 'I'm curling the wrong project' mistakes (ports, container names, health).",
        command: "docker compose ps",
        expectedSignals: ["api is Up and bound to 8000", "redis/postgres are healthy"],
        terminalOutput: [
          "NAME                      SERVICE    STATUS                   PORTS",
          "agentops-mvp-api-1        api        Up                       0.0.0.0:8000->8000/tcp",
          "agentops-mvp-worker-1     worker     Up",
          "agentops-mvp-postgres-1   postgres   Up (healthy)            0.0.0.0:5432->5432/tcp",
          "agentops-mvp-redis-1      redis      Up (healthy)            0.0.0.0:6379->6379/tcp",
        ],
        interpretation:
          "✅ Confirms you’re pointing at the correct stack and the port is live.",
      },
      {
        id: "worker-listen",
        title: "Verify worker queue: docker compose logs worker",
        tags: ["Queue", "Observability"],
        whyItMatters:
          "RCA is async. If the worker listens on the wrong queue, jobs stay queued forever (a classic production pitfall).",
        command: "docker compose logs worker --tail 120",
        expectedSignals: ["Listening on rca", "Worker started"],
        terminalOutput: [
          "worker-1  | Starting RQ worker for queues: ['rca']",
          "worker-1  | Worker rq:worker:... started",
          "worker-1  | *** Listening on rca...",
        ],
        interpretation:
          "✅ Worker is alive and waiting on the 'rca' queue. If RCA stays queued, next suspect is: API enqueued to a different queue (e.g., default).",
      },
      {
        id: "health-check",
        title: "API reachability: curl http://localhost:8000/",
        tags: ["API"],
        whyItMatters:
          "Confirms the API is reachable from your machine and you’re hitting the right port / right compose stack.",
        command: "curl -s http://localhost:8000/",
        expectedSignals: ["status ok response"],
        terminalOutput: ['{"status":"ok","service":"agentops-smart-sre"}'],
        interpretation:
          "✅ Your HTTP entrypoint is live.",
      },
      {
        id: "ingest",
        title: "Ingest an agent run: POST /agent-runs",
        tags: ["API", "DB"],
        whyItMatters:
          "Proves your data contract works: the system can accept structured traces and persist them (agent_runs/steps/tool_calls/guardrails).",
        command:
          "curl -X POST http://localhost:8000/agent-runs -H \"Content-Type: application/json\" -d '{...}'",
        expectedSignals: ["200/201 response", "DB INSERTs", "log: Ingested agent run"],
        terminalOutput: [
          "api-1 | INSERT INTO agent_runs ...",
          "api-1 | INSERT INTO agent_steps ...",
          "api-1 | INSERT INTO tool_calls ...",
          "api-1 | INSERT INTO guardrail_events ...",
          "api-1 | Ingested agent run: demo-run-001",
        ],
        interpretation:
          "✅ You now have a trace stored. Without this, RCA has nothing to analyze.",
      },
      {
        id: "create-rca",
        title: "Create RCA job: POST /agent-runs/{run_id}/rca-runs",
        tags: ["API", "Queue"],
        whyItMatters:
          "This is the bridge from synchronous HTTP to async execution: API creates a record + enqueues a job for the worker.",
        command:
          "curl -s -X POST http://localhost:8000/agent-runs/demo-run-001/rca-runs | python3 -m json.tool",
        expectedSignals: ["Returns rca_run_id", "Status queued or running"],
        terminalOutput: [
          "{",
          '  "rca_run_id": "e051e85a-5a89-4597-a032-7e8238c10b06"',
          "}",
        ],
        interpretation:
          "✅ Job is created. Next check: did it land in the queue and did the worker consume it?",
      },
      {
        id: "poll-rca",
        title: "Poll result: GET /agent-runs/rca-runs/{rca_run_id}",
        tags: ["API", "DB"],
        whyItMatters:
          "Confirms end-to-end closure: worker ran, wrote a report to DB, API can serve the final structured RCA.",
        command:
          "curl -s http://localhost:8000/agent-runs/rca-runs/e051e85a-... | python3 -m json.tool",
        expectedSignals: [
          "status transitions: queued → running → done",
          "report contains evidence_index/hypotheses/action_items",
        ],
        terminalOutput: [
          '"status": "done",',
          '"category": "tool_schema_mismatch",',
          '"insufficient_evidence": false,',
          '"evidence_index": [ ... ],',
          '"hypotheses": [ ... evidence_ids ... ],',
          '"action_items": [ ... ],',
          '"jira_fields": { ... }',
        ],
        interpretation:
          "✅ This proves your AgentOps value: evidence-first, anti-hallucination-ready, and connector-ready outputs.",
      },
      {
        id: "sse",
        title: "Stream status: SSE GET /rca-runs/{rca_run_id}/stream",
        tags: ["Streaming", "Observability"],
        whyItMatters:
          "Instead of polling, a UI can subscribe once and receive real-time progress. Pings keep the connection alive through proxies.",
        command:
          'curl -N "http://localhost:8000/rca-runs/e051e85a-.../stream"',
        expectedSignals: ["data: {status...}", "periodic : ping keep-alives"],
        terminalOutput: [
          'data: {"status":"done","step":"RCA complete","pct":"100","message":"RCA complete"}',
          "",
          ": ping - 2026-01-12 02:44:06.774775",
          ": ping - 2026-01-12 02:44:21.779769",
          ": ping - 2026-01-12 02:44:36.783064",
          "...",
        ],
        interpretation:
          "✅ Streaming channel works. Because this run is already done, you see one final status + keep-alive pings.",
      },
      {
        id: "upgrade",
        title: "Upgrade targets (productization)",
        tags: ["Observability", "Streaming"],
        whyItMatters:
          "These turn an MVP into a sellable platform: staged progress, strategy library, connectors, regression detection.",
        expectedSignals: [
          "Multiple progress events (queued/running/classifying/drafting/done)",
          "Configurable & versioned strategy rules",
          "Webhook/Jira/Slack connectors",
          "Regression detector creates agent incidents",
        ],
        terminalOutput: [
          "1) Staged SSE progress events",
          "2) Strategy Library (versioned rules/actions)",
          "3) Connectors (Jira/Slack/Webhook out)",
          "4) Regression Detector (baseline vs last 24h) → auto incident",
        ],
        interpretation:
          "🚀 Next: make the pipeline observable & actionable at scale.",
      },
    ],
    []
  );

  const [activeIndex, setActiveIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [typing, setTyping] = useState(false);
  const [typedLines, setTypedLines] = useState<string[]>([]);
  const [tab, setTab] = useState<"journey" | "interview">("journey");

  const { copied, copy } = useClipboard();
  const timerRef = useRef<number | null>(null);
  const typeRef = useRef<number | null>(null);

  const step = steps[activeIndex];

  const progressPct = useMemo(() => {
    return Math.round(((activeIndex + 1) / steps.length) * 100);
  }, [activeIndex, steps.length]);

  function stopTimers() {
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (typeRef.current) {
      window.clearInterval(typeRef.current);
      typeRef.current = null;
    }
  }

  function startTyping(lines: string[]) {
    stopTimers();
    setTyping(true);
    setTypedLines([]);
    let i = 0;
    typeRef.current = window.setInterval(() => {
      i += 1;
      setTypedLines(lines.slice(0, i));
      if (i >= lines.length) {
        if (typeRef.current) window.clearInterval(typeRef.current);
        typeRef.current = null;
        setTyping(false);
      }
    }, 70);
  }

  function goTo(idx: number) {
    const next = clamp(idx, 0, steps.length - 1);
    setActiveIndex(next);
    startTyping(steps[next].terminalOutput);
  }

  function reset() {
    setPlaying(false);
    goTo(0);
  }

  function togglePlay() {
    setPlaying((p) => !p);
  }

  // Start typing when step changes
  useEffect(() => {
    startTyping(step.terminalOutput);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeIndex]);

  // Autoplay
  useEffect(() => {
    stopTimers();
    if (!playing) return;

    timerRef.current = window.setInterval(() => {
      setActiveIndex((i) => {
        const next = i + 1;
        if (next >= steps.length) {
          setPlaying(false);
          return i;
        }
        return next;
      });
    }, 2600);

    return () => stopTimers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing]);

  const interviewScript = useMemo(() => {
    return [
      {
        q: "Walk me through what you built end-to-end.",
        a:
          "I built an AgentOps MVP with four components: FastAPI for ingestion and query, Postgres for durable run storage, Redis+RQ for async RCA execution, and an SSE endpoint to stream RCA progress. The API ingests agent runs (steps, tool calls, guardrail events, cost), then creates an RCA run and enqueues a job. The worker performs evidence-first classification and generates a structured RCA report with evidence references and Jira-ready fields.",
      },
      {
        q: "How did you verify it works?",
        a:
          "I validated layer by layer: (1) Docker compose ps + health checks to confirm infra, (2) worker logs to confirm it listens on the correct queue, (3) curl POST /agent-runs to verify the data contract and DB persistence, (4) curl POST /agent-runs/{run_id}/rca-runs to enqueue async jobs, (5) curl GET /agent-runs/rca-runs/{id} to confirm worker completion and report persistence, and (6) curl -N to validate SSE streaming with keep-alive pings.",
      },
      {
        q: "Why use a queue/worker instead of doing RCA inline in the request?",
        a:
          "RCA can be expensive and variable-latency, especially with LLM calls or external log retrieval. An async worker prevents HTTP timeouts, improves reliability, and enables retries and rate control. It also lets the UI stream progress via SSE while the job runs.",
      },
      {
        q: "How do you avoid hallucinations in RCA?",
        a:
          "The report is evidence-first. Hypotheses must reference evidence IDs from the indexed run data. If evidence is insufficient, we set an explicit insufficient_evidence flag and return data-collection action items instead of guessing a root cause.",
      },
    ];
  }, []);

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <div className="text-2xl font-semibold tracking-tight">AgentOps Debug Journey</div>
          <div className="text-sm text-muted-foreground mt-1">
            A UI you can use to explain (and remember) the full process from Docker boot → RCA → SSE.
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={reset} className="gap-2">
            <RotateCcw className="h-4 w-4" />
            Reset
          </Button>
          <Button onClick={togglePlay} className="gap-2">
            {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            {playing ? "Pause" : "Play"}
          </Button>
          <Button
            variant="outline"
            onClick={() => goTo(activeIndex + 1)}
            disabled={activeIndex >= steps.length - 1}
            className="gap-2"
          >
            <StepForward className="h-4 w-4" />
            Next
          </Button>
        </div>
      </div>

      <Card className="rounded-2xl">
        <CardContent className="p-5">
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-medium">Journey progress</div>
            <div className="text-xs text-muted-foreground">Step {activeIndex + 1} / {steps.length}</div>
          </div>
          <div className="mt-3">
            <Progress value={progressPct} />
          </div>
        </CardContent>
      </Card>

      <Tabs value={tab} onValueChange={(v) => setTab(v as any)}>
        <TabsList>
          <TabsTrigger value="journey">Walkthrough</TabsTrigger>
          <TabsTrigger value="interview">Interview Script</TabsTrigger>
        </TabsList>

        <TabsContent value="journey" className="mt-4">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left: Timeline */}
            <Card className="rounded-2xl lg:col-span-1">
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Steps</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {steps.map((s, idx) => (
                  <button
                    key={s.id}
                    onClick={() => goTo(idx)}
                    className={`w-full text-left rounded-2xl border px-3 py-3 transition ${
                      idx === activeIndex
                        ? "bg-background shadow-sm border-foreground/20"
                        : "bg-muted/30 hover:bg-muted/50"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-sm font-medium leading-snug truncate">
                          {idx + 1}. {s.title}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-1">
                          {s.tags.map((t) => (
                            <TagPill key={t} tag={t} />
                          ))}
                        </div>
                      </div>
                      {idx < activeIndex ? (
                        <Badge className="shrink-0" variant="secondary">
                          done
                        </Badge>
                      ) : idx === activeIndex ? (
                        <Badge className="shrink-0" variant="default">
                          active
                        </Badge>
                      ) : (
                        <Badge className="shrink-0" variant="outline">
                          next
                        </Badge>
                      )}
                    </div>
                  </button>
                ))}
              </CardContent>
            </Card>

            {/* Right: Details */}
            <div className="lg:col-span-2 space-y-6">
              <AnimatePresence mode="wait">
                <motion.div
                  key={step.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.2 }}
                >
                  <Card className="rounded-2xl">
                    <CardHeader>
                      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3">
                        <div>
                          <CardTitle className="text-lg">{step.title}</CardTitle>
                          <div className="mt-2 text-sm text-muted-foreground">{step.whyItMatters}</div>
                        </div>
                        {step.command ? (
                          <Button
                            variant="outline"
                            className="gap-2"
                            onClick={() => copy(step.command!)}
                          >
                            <Copy className="h-4 w-4" />
                            {copied ? "Copied" : "Copy command"}
                          </Button>
                        ) : null}
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-5">
                      {step.command ? (
                        <div className="rounded-2xl border bg-muted/30 p-3">
                          <div className="text-xs text-muted-foreground mb-2">Command</div>
                          <div className="font-mono text-sm whitespace-pre-wrap break-words">{step.command}</div>
                        </div>
                      ) : null}

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="rounded-2xl border p-3">
                          <div className="text-xs text-muted-foreground mb-2">Expected signals</div>
                          <ul className="text-sm list-disc pl-5 space-y-1">
                            {step.expectedSignals.map((x, i) => (
                              <li key={i}>{x}</li>
                            ))}
                          </ul>
                        </div>
                        <div className="rounded-2xl border p-3">
                          <div className="text-xs text-muted-foreground mb-2">What it proves</div>
                          <div className="text-sm">{step.interpretation}</div>
                        </div>
                      </div>

                      <Terminal lines={typedLines} active={typing} />

                      <Separator />

                      <div className="rounded-2xl border p-3">
                        <div className="text-xs text-muted-foreground mb-2">How to explain (interview)</div>
                        <div className="text-sm">
                          {step.id === "sse" ? (
                            <>
                              <div className="font-medium">One-liner</div>
                              <div className="mt-1 text-muted-foreground">
                                “We use SSE to push job progress to the UI in real time; pings keep the long connection alive.”
                              </div>
                            </>
                          ) : step.id === "worker-listen" ? (
                            <>
                              <div className="font-medium">One-liner</div>
                              <div className="mt-1 text-muted-foreground">
                                “I confirm the worker listens on the correct queue; otherwise jobs remain queued forever.”
                              </div>
                            </>
                          ) : (
                            <>
                              <div className="font-medium">One-liner</div>
                              <div className="mt-1 text-muted-foreground">
                                {"I validate this layer independently so failures are easy to localize."}
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              </AnimatePresence>

              <Card className="rounded-2xl">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Mental model</CardTitle>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div className="rounded-2xl border p-3 bg-muted/20">
                      <div className="font-medium text-foreground">HTTP (curl)</div>
                      <div className="mt-1">Simulates the UI clicking buttons. Sends requests to FastAPI.</div>
                    </div>
                    <div className="rounded-2xl border p-3 bg-muted/20">
                      <div className="font-medium text-foreground">Queue (Redis+RQ)</div>
                      <div className="mt-1">Turns a short request into a long job the worker can run reliably.</div>
                    </div>
                    <div className="rounded-2xl border p-3 bg-muted/20">
                      <div className="font-medium text-foreground">DB (Postgres)</div>
                      <div className="mt-1">Source of truth: runs + reports persist beyond process restarts.</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="interview" className="mt-4">
          <Card className="rounded-2xl">
            <CardHeader>
              <CardTitle className="text-base">Interview-ready answers (based on this exact project)</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {interviewScript.map((qa, i) => (
                <div key={i} className="rounded-2xl border p-4">
                  <div className="text-sm font-medium">Q{i + 1}. {qa.q}</div>
                  <div className="mt-2 text-sm text-muted-foreground whitespace-pre-wrap">{qa.a}</div>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <div className="text-xs text-muted-foreground">
        Tip: Replace the sample terminal outputs with your real logs/commands to create a personalized demo you can screen-share in interviews.
      </div>
    </div>
  );
}
