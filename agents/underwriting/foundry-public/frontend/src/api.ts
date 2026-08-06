export type UnderwritingApplication = {
  application_id: string
  applicant_name: string
  age: number
  income: number
  requested_coverage: number
  health_disclosures: string
  driving_history: string
  credit_score: number
}

export type RunResponse = {
  workflow_run_id: string
  status: string
  outputs: unknown[]
}

export type RunHistoryItem = {
  workflow_run_id: string
  application_id: string
  applicant_name: string
  status: string
  created_at: string
  updated_at: string
  final_decision: string | null
  checkpoint_count: number
  latest_checkpoint_at: string | null
  resumable: boolean
}

export type RunHistoryResponse = {
  items: RunHistoryItem[]
  total: number
  limit: number
  offset: number
}

export type AGUIEvent = {
  type: string
  name?: string
  value?: unknown
}

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      'content-type': 'application/json',
      ...(init?.headers ?? {}),
    },
  })
  if (!response.ok) {
    throw new ApiError(await response.text(), response.status)
  }
  return (await response.json()) as T
}

export async function startRun(payload: {
  application: UnderwritingApplication
  fail_risk_once?: boolean
  fail_credit_randomly?: boolean
  crash_after_executor?: string
  workflow_run_id?: string
}): Promise<RunResponse> {
  return api<RunResponse>('/api/v1/underwriting/runs', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function resumeRun(runId: string): Promise<RunResponse> {
  return api<RunResponse>(`/api/v1/underwriting/runs/${runId}/resume`, {
    method: 'POST',
  })
}

export async function getRun(runId: string): Promise<Record<string, unknown>> {
  return api<Record<string, unknown>>(`/api/v1/underwriting/runs/${runId}`)
}

export async function getState(runId: string): Promise<Record<string, unknown>[]> {
  return api<Record<string, unknown>[]>(`/api/v1/underwriting/runs/${runId}/state`)
}

export async function getEvents(runId: string): Promise<Record<string, unknown>[]> {
  return api<Record<string, unknown>[]>(`/api/v1/underwriting/runs/${runId}/events`)
}

export async function getCheckpoints(runId: string): Promise<Record<string, unknown>[]> {
  return api<Record<string, unknown>[]>(`/api/v1/underwriting/runs/${runId}/checkpoints`)
}

export async function getRunHistory(params: {
  search?: string
  status?: string
  limit?: number
  offset?: number
}): Promise<RunHistoryResponse> {
  const query = new URLSearchParams()
  if (params.search) query.set('search', params.search)
  if (params.status) query.set('status', params.status)
  if (params.limit) query.set('limit', String(params.limit))
  if (params.offset) query.set('offset', String(params.offset))
  const suffix = query.size ? `?${query}` : ''
  return api<RunHistoryResponse>(`/api/v1/underwriting/runs${suffix}`)
}

export async function streamRun(
  payload: {
    workflowRunId: string
    action: 'start' | 'resume'
    application?: UnderwritingApplication
    failRiskOnce?: boolean
    failCreditRandomly?: boolean
    crashAfterExecutor?: string
  },
  onEvent: (event: AGUIEvent) => void,
): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/api/v1/underwriting/ag-ui`, {
    method: 'POST',
    headers: {
      accept: 'text/event-stream',
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      threadId: `underwriting-ui-${crypto.randomUUID()}`,
      runId: `underwriting-stream-${crypto.randomUUID()}`,
      messages: [
        {
          id: `message-${crypto.randomUUID()}`,
          role: 'user',
          content: JSON.stringify({
            action: payload.action,
            workflow_run_id: payload.workflowRunId,
            application: payload.application,
            fail_risk_once: payload.failRiskOnce,
            fail_credit_randomly: payload.failCreditRandomly,
            crash_after_executor: payload.crashAfterExecutor,
          }),
        },
      ],
    }),
  })
  if (!response.ok) {
    throw new ApiError(await response.text(), response.status)
  }
  if (!response.body) {
    throw new Error('AG-UI stream was not available')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })
    const messages = buffer.split('\n\n')
    buffer = messages.pop() ?? ''
    for (const message of messages) {
      const data = message
        .split('\n')
        .find((line) => line.startsWith('data: '))
        ?.slice('data: '.length)
      if (!data) continue
      onEvent(JSON.parse(data) as AGUIEvent)
    }
    if (done) {
      break
    }
  }
}
