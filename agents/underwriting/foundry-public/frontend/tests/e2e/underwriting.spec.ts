import { expect, test, type Page } from '@playwright/test'

import { scoreRubric, type RubricResultMap } from './rubric'

async function startScenario(page: Page, scenario: 'happy' | 'retry' | 'crash-medical') {
  const previousRunText = await page.getByTestId('run-id').innerText()
  await page.getByRole('button', { name: 'New underwriting run' }).click()
  await page
    .getByTestId('field-application_id')
    .fill(`app-e2e-${scenario}-${Date.now()}-${Math.floor(Math.random() * 1000)}`)
  await page.getByTestId('scenario-select').selectOption(scenario)
  await page.getByTestId('start-run').click()
  await expect
    .poll(async () => page.getByTestId('run-id').innerText())
    .not.toBe(previousRunText)
}

test('underwriting rubric scenarios', async ({ page }) => {
  const rubric: RubricResultMap = {
    'happy-path-decision': false,
    'retry-behavior': false,
    'crash-state': false,
    'resume-from-checkpoint': false,
    'fanin-state': false,
    'checkpoint-listing': false,
    'idempotency-skip': false,
    'observability-fields': false,
  }

  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Underwriting Transactions' })).toBeVisible()
  await expect.poll(async () => (await page.request.get('/backend-health')).status()).toBe(200)

  await startScenario(page, 'happy')
  await expect(page.getByTestId('run-status')).toContainText('COMPLETED', { timeout: 30_000 })
  await expect(page.getByTestId('run-outputs')).toContainText('decision')
  rubric['happy-path-decision'] = true
  const happyRunId = (await page.getByTestId('run-id').innerText()).replace('Run ID', '').trim()
  const assistantInput = page.getByPlaceholder('Ask about this run')
  await assistantInput.fill('What is the status?')
  await assistantInput.press('Enter')
  await expect(page.getByText(`Run ${happyRunId} is COMPLETED.`)).toBeVisible({ timeout: 30_000 })

  const fanInText = await page.getByTestId('fanin-completed-checks').innerText()
  rubric['fanin-state'] =
    fanInText.includes('risk') &&
    fanInText.includes('credit') &&
    fanInText.includes('medical') &&
    fanInText.includes('driving')

  const checkpointCountText = await page.getByTestId('checkpoint-count').innerText()
  const checkpointCount = Number((checkpointCountText.match(/\d+/) || ['0'])[0])
  rubric['checkpoint-listing'] = checkpointCount > 0
  const chronologicalEvents = JSON.parse((await page.getByTestId('events-json').textContent()) ?? '[]') as Array<{
    created_at: string
  }>
  expect(chronologicalEvents.map((event) => event.created_at)).toEqual(
    [...chronologicalEvents.map((event) => event.created_at)].sort(),
  )

  await startScenario(page, 'retry')
  await expect(page.getByTestId('run-status')).toContainText('COMPLETED', { timeout: 30_000 })
  const retryText = await page.getByTestId('retry-event-count').innerText()
  const retryCount = Number((retryText.match(/\d+/) || ['0'])[0])
  rubric['retry-behavior'] = retryCount > 0

  await page.getByTestId('history-search').fill(happyRunId)
  await expect(page.getByTestId(`history-run-${happyRunId}`)).toBeVisible()
  await page.getByTestId(`history-run-${happyRunId}`).click()
  await expect(page.getByTestId('run-id')).toContainText(happyRunId)
  await page.getByTestId('history-search').fill('')

  await startScenario(page, 'crash-medical')
  await expect(page.getByTestId('run-status')).toContainText('CRASHED', { timeout: 30_000 })
  rubric['crash-state'] = true

  await page.getByTestId('resume-run').click()
  await expect
    .poll(async () => page.getByTestId('run-status').innerText(), { timeout: 30_000 })
    .toContain('COMPLETED')
  rubric['resume-from-checkpoint'] = true

  const idempotencyText = await page.getByTestId('idempotency-skip-count').innerText()
  const idempotencyCount = Number((idempotencyText.match(/\d+/) || ['0'])[0])
  rubric['idempotency-skip'] = idempotencyCount > 0

  const eventsJson = (await page.getByTestId('events-json').textContent()) ?? ''
  rubric['observability-fields'] =
    eventsJson.includes('workflow_run_id') && eventsJson.includes('executor_name')

  const score = scoreRubric(rubric)
  expect(score.failed, score.failed.join('\n')).toEqual([])
  expect(score.passed).toBe(score.total)
})

test('review UI preserves pending visibility and directs decisions to Teams', async ({ page }) => {
  const runId = 'run-review-ui'
  const checkpointId = 'checkpoint-review-ui'
  let mutationAttempts = 0

  await page.route('**/api/v1/underwriting/runs**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    if (request.method() === 'POST' && path.endsWith(`/reviews/${checkpointId}`)) {
      mutationAttempts += 1
      await route.fulfill({ status: 403, json: { detail: 'Use Microsoft Teams' } })
      return
    }
    if (path.endsWith(`/${runId}/review`)) {
      await route.fulfill({
        json: {
          workflow_run_id: runId,
          checkpoint_id: checkpointId,
          status: 'pending',
          machine_recommendation: 'REFER_TO_HUMAN_UNDERWRITER',
          reviewer_outcome: null,
          requested_at: '2026-10-21T20:00:00Z',
          resolved_at: null,
        },
      })
      return
    }
    if (path.endsWith(`/${runId}/state`)) {
      await route.fulfill({
        json: [
          {
            state_key: 'final_decision',
            state_json: {
              decision: 'REFER_TO_HUMAN_UNDERWRITER',
              machine_recommendation: 'REFER_TO_HUMAN_UNDERWRITER',
            },
          },
        ],
      })
      return
    }
    if (path.endsWith(`/${runId}/events`)) {
      await route.fulfill({ json: [] })
      return
    }
    if (path.endsWith(`/${runId}/checkpoints`)) {
      await route.fulfill({
        json: [{ checkpoint_id: checkpointId, created_at: '2026-10-21T20:00:00Z' }],
      })
      return
    }
    if (path.endsWith(`/${runId}`)) {
      await route.fulfill({
        json: {
          id: runId,
          application_id: 'redacted-application',
          applicant_name: 'Authorized view',
          status: 'PENDING_REVIEW',
          created_at: '2026-10-21T20:00:00Z',
          updated_at: '2026-10-21T20:00:00Z',
          machine_recommendation: 'REFER_TO_HUMAN_UNDERWRITER',
          reviewer_outcome: null,
          review_checkpoint_id: checkpointId,
          review_status: 'pending',
        },
      })
      return
    }
    await route.fulfill({
      json: {
        items: [
          {
            workflow_run_id: runId,
            application_id: 'redacted-application',
            applicant_name: 'Authorized view',
            status: 'PENDING_REVIEW',
            created_at: '2026-10-21T20:00:00Z',
            updated_at: '2026-10-21T20:00:00Z',
            final_decision: 'REFER_TO_HUMAN_UNDERWRITER',
            machine_recommendation: 'REFER_TO_HUMAN_UNDERWRITER',
            reviewer_outcome: null,
            review_status: 'pending',
            review_checkpoint_id: checkpointId,
            checkpoint_count: 1,
            latest_checkpoint_at: '2026-10-21T20:00:00Z',
            resumable: false,
            reviewable: true,
          },
        ],
        total: 1,
        limit: 10,
        offset: 0,
      },
    })
  })

  await page.goto('/')
  await page.getByTestId(`history-run-${runId}`).click()
  await expect(page.getByTestId('machine-recommendation')).toHaveText(
    'REFER_TO_HUMAN_UNDERWRITER',
  )
  await expect(page.getByTestId('reviewer-outcome')).toHaveText('Pending review')
  await expect(page.getByTestId('teams-review-guidance')).toContainText('Microsoft Teams')
  await expect(page.getByTestId('approve-review')).toHaveCount(0)
  await expect(page.getByTestId('decline-review')).toHaveCount(0)
  expect(mutationAttempts).toBe(0)
})
