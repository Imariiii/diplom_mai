/**
 * API клиент - Сценарии тестирования
 */

import type {
  Scenario,
  ScenarioQuery,
  ScenarioParam,
  CreateScenarioRequest,
  CreateScenarioQueryRequest,
  CreateScenarioParamRequest,
  GenerateScenariosRequest,
  GenerateScenariosResponse,
} from "../types"

import { apiClient } from "./client"

// ==================== Сценарии тестирования ====================

export async function getScenarios(params?: {
  targetConnectionId?: string
  includeGlobal?: boolean
  includeBuiltin?: boolean
}): Promise<{ scenarios: Scenario[] }> {
  return apiClient.getScenarios(params)
}

export async function getScenario(id: string): Promise<Scenario> {
  return apiClient.getScenario(id)
}

export async function getEnabledScenarios(): Promise<{ scenarios: Scenario[] }> {
  return apiClient.getEnabledScenarios()
}

export async function createScenario(scenario: CreateScenarioRequest): Promise<Scenario> {
  return apiClient.createScenario(scenario)
}

export async function updateScenario(id: string, scenario: Partial<CreateScenarioRequest>): Promise<Scenario> {
  return apiClient.updateScenario(id, scenario)
}

export async function deleteScenario(id: string): Promise<{ deleted: boolean; scenario_id: string }> {
  return apiClient.deleteScenario(id)
}

export async function cloneScenario(id: string, newName?: string): Promise<Scenario> {
  return apiClient.cloneScenario(id, newName)
}

export async function generateScenarios(request: GenerateScenariosRequest): Promise<GenerateScenariosResponse> {
  return apiClient.generateScenarios(request)
}

// Запросы сценария
export async function getScenarioQueries(scenarioId: string): Promise<{ queries: ScenarioQuery[] }> {
  return apiClient.getScenarioQueries(scenarioId)
}

export async function createScenarioQuery(scenarioId: string, query: CreateScenarioQueryRequest): Promise<ScenarioQuery> {
  return apiClient.createScenarioQuery(scenarioId, query)
}

export async function updateScenarioQuery(
  scenarioId: string,
  queryId: string,
  query: Partial<CreateScenarioQueryRequest>
): Promise<ScenarioQuery> {
  return apiClient.updateScenarioQuery(scenarioId, queryId, query)
}

export async function deleteScenarioQuery(scenarioId: string, queryId: string): Promise<{ deleted: boolean; query_id: string }> {
  return apiClient.deleteScenarioQuery(scenarioId, queryId)
}

// Параметры запроса
export async function getScenarioQueryParams(scenarioId: string, queryId: string): Promise<{ params: ScenarioParam[] }> {
  return apiClient.getScenarioQueryParams(scenarioId, queryId)
}

export async function createScenarioParam(
  scenarioId: string,
  queryId: string,
  param: CreateScenarioParamRequest
): Promise<ScenarioParam> {
  return apiClient.createScenarioParam(scenarioId, queryId, param)
}

export async function updateScenarioParam(
  scenarioId: string,
  queryId: string,
  paramId: string,
  param: Partial<CreateScenarioParamRequest>
): Promise<ScenarioParam> {
  return apiClient.updateScenarioParam(scenarioId, queryId, paramId, param)
}

export async function deleteScenarioParam(
  scenarioId: string,
  queryId: string,
  paramId: string
): Promise<{ deleted: boolean; param_id: string }> {
  return apiClient.deleteScenarioParam(scenarioId, queryId, paramId)
}