// Mirrors Basic Scenario / Basic Test Result contracts (Epic 3, US3.1-US3.3)

import type { CompletionSectionName } from './household'

export type ScenarioId =
  | 'vehicle_unavailable'
  | 'person_unavailable'
  | 'destination_unavailable'

export interface Scenario {
  scenario_id: ScenarioId
  title: string
  description: string
  enabled: boolean
  disabled_reason: string | null
}

export type CheckStatus = 'pass' | 'fail' | 'not_checked'

export interface TestCheck {
  check: string
  status: CheckStatus
  message: string
}

export interface FirstProblem {
  section: CompletionSectionName
  message: string
}

export type TestOverallStatus = 'pass' | 'needs_attention'

export interface TestResult {
  test_run_id: string
  scenario_id: ScenarioId
  overall_status: TestOverallStatus
  checks: TestCheck[]
  first_problem: FirstProblem | null
  result_reason: string
  tested_at: string
}
