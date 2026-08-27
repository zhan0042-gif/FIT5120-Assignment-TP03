// Thin API layer matching the I1 API Contract (see "Iteration 1 总体分工与数据流", section 5).
// Every function here corresponds 1:1 to a documented endpoint. Today it delegates to the
// mock backend; swapping to real HTTP calls later should only require editing this file.

import * as mock from './mockBackend'
import type { HouseholdPlan, PlanCompletion } from '../types/household'
import type { LocalContext, PreparationSupport } from '../types/localContext'
import type { Scenario, TestResult } from '../types/scenario'

export const api = {
  // GET /api/v1/households/{id}/plan
  getHouseholdPlan: (): Promise<HouseholdPlan> => mock.fetchHouseholdPlan(),

  // PUT /api/v1/households/{id}/plan
  saveHouseholdPlan: (plan: HouseholdPlan): Promise<HouseholdPlan> => mock.saveHouseholdPlan(plan),

  // GET /api/v1/households/{id}/completion
  getCompletion: (): Promise<PlanCompletion> => mock.fetchCompletion(),

  // PUT /api/v1/households/{id}/location
  saveLocation: (address: string) => mock.saveLocation(address),

  // GET /api/v1/households/{id}/local-context
  getLocalContext: (address: string): Promise<LocalContext | null> => mock.fetchLocalContext(address),

  // GET /api/v1/households/{id}/preparation-support
  getPreparationSupport: (): Promise<PreparationSupport> => mock.fetchPreparationSupport(),

  // GET /api/v1/scenarios/basic
  getBasicScenarios: (): Promise<Scenario[]> => mock.fetchScenarios(),

  // POST /api/v1/households/{id}/tests  — body: { scenario_id }
  runBasicTest: (scenarioId: string): Promise<TestResult> => mock.runBasicTest(scenarioId),
}

export function loadSavedAddress(): string {
  return mock.loadSavedAddress()
}

export function newId(prefix: string): string {
  return mock.genId(prefix)
}
