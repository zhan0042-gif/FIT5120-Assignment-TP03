// Mirrors Basic Scenario / Basic Test Result contracts (Epic 3, US3.1-US3.3)

export interface Scenario {
  scenario_id: string
  title: string
  description: string
}

export type CheckStatus = 'pass' | 'fail' | 'not_checked'

export interface TestCheck {
  check: string
  status: CheckStatus
  message: string
}

export interface FirstProblem {
  section: string
  message: string
}

export type TestOverallStatus = 'ok' | 'needs_attention'

export interface TestResult {
  test_run_id: string
  scenario_id: string
  overall_status: TestOverallStatus
  checks: TestCheck[]
  first_problem: FirstProblem | null
  tested_at: string
}
