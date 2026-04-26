"use client"

import { useEffect, useMemo, useState } from "react"
import {
  Check,
  ChevronDown,
  Copy,
  Database,
  FileCode2,
  Layers,
  Loader2,
  Pencil,
  Plus,
  Save,
  Trash2,
  WandSparkles,
  AlertCircle,
} from "lucide-react"

import { apiClient } from "@/lib/api"
import type {
  LogicalDatabase,
  ScenarioBundleSummary,
  ScenarioBundleSaveRequest,
  ScenarioIndex,
  ScenarioParam,
  ScenarioQuery,
  ScenarioTemplate,
  SchemaProfileDetail,
  SchemaProfileSummary,
} from "@/lib/types"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import { toast } from "sonner"

// ==================== Helpers ====================

function cloneParams(params: ScenarioParam[] = []): ScenarioParam[] {
  return params.map((param) => ({
    param_name: param.param_name,
    param_type: param.param_type,
    min_value: param.min_value ?? null,
    max_value: param.max_value ?? null,
    string_pattern: param.string_pattern ?? null,
    table_ref: param.table_ref ?? null,
    column_ref: param.column_ref ?? null,
    string_length: param.string_length ?? null,
    current_value: param.current_value ?? 0,
    step: param.step ?? 1,
  }))
}

function cloneQueries(queries: ScenarioQuery[] = []): ScenarioQuery[] {
  return queries.map((query, index) => ({
    sql_template: query.sql_template,
    query_type: query.query_type,
    description: query.description ?? null,
    weight: query.weight ?? 1,
    order_index: query.order_index ?? index,
    params: cloneParams(query.params || []),
  }))
}

function cloneIndexes(indexes: ScenarioIndex[] = []): ScenarioIndex[] {
  return indexes.map((index) => ({
    table_name: index.table_name,
    column_names: index.column_names,
    index_type: index.index_type || "btree",
    index_name: index.index_name ?? null,
    is_unique: Boolean(index.is_unique),
    condition: index.condition ?? null,
    description: index.description ?? null,
  }))
}

function bundleToDraft(bundle: ScenarioBundleSummary): ScenarioBundleSaveRequest {
  return {
    scenario_template_id: bundle.scenario_template_id,
    name: bundle.name,
    description: bundle.description ?? "",
    generation_source: bundle.generation_source,
    generated_from_connection_id: bundle.generated_from_connection_id ?? undefined,
    is_active: bundle.is_active,
    queries: cloneQueries(bundle.queries),
    indexes: cloneIndexes(bundle.indexes),
  }
}

// ==================== Component ====================

export function LogicalScenariosBrowser() {
  const [templates, setTemplates] = useState<ScenarioTemplate[]>([])
  const [profiles, setProfiles] = useState<SchemaProfileSummary[]>([])
  const [logicalDatabases, setLogicalDatabases] = useState<LogicalDatabase[]>([])
  const [selectedLogicalDbId, setSelectedLogicalDbId] = useState<string>("")
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>("")
  const [selectedProfileId, setSelectedProfileId] = useState<string>("")
  const [selectedProfileDetail, setSelectedProfileDetail] = useState<SchemaProfileDetail | null>(null)
  const [selectedBundleId, setSelectedBundleId] = useState<string>("new")
  const [draftBundle, setDraftBundle] = useState<ScenarioBundleSaveRequest | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingProfile, setLoadingProfile] = useState(false)
  const [saving, setSaving] = useState(false)
  const [expandedQueries, setExpandedQueries] = useState<Set<number>>(new Set())

  const selectedTemplate = useMemo(
    () => templates.find((t) => t.id === selectedTemplateId) || null,
    [templates, selectedTemplateId]
  )

  const selectedLogicalDatabase = useMemo(
    () => logicalDatabases.find((db) => db.id === selectedLogicalDbId) || null,
    [logicalDatabases, selectedLogicalDbId]
  )

  const variants = useMemo(() => {
    if (!selectedProfileDetail || !selectedTemplateId) return []
    return selectedProfileDetail.bundles.filter((b) => b.scenario_template_id === selectedTemplateId)
  }, [selectedProfileDetail, selectedTemplateId])

  const activeVariant = useMemo(() => variants.find((b) => b.is_active) || null, [variants])
  const selectedLogicalDbBlocksBundles = Boolean(
    selectedLogicalDatabase &&
    (
      ["draft", "needs_review", "incompatible"].includes(selectedLogicalDatabase.profile_status || "") ||
      selectedLogicalDatabase.compatibility_status === "invalid"
    )
  )

  const selectedBundle: ScenarioBundleSummary | null = useMemo(() => {
    if (!variants.length || selectedBundleId === "new") return null
    return variants.find((b) => b.id === selectedBundleId) || null
  }, [variants, selectedBundleId])

  const buildEmptyDraft = (
    templateId: string,
    profileDetail?: SchemaProfileDetail | null,
    sourceBundle?: ScenarioBundleSummary | null
  ): ScenarioBundleSaveRequest => ({
    scenario_template_id: templateId,
    name: sourceBundle
      ? `${sourceBundle.name} (копия)`
      : `${templates.find((t) => t.id === templateId)?.name || templateId} variant`,
    description: sourceBundle?.description ?? "",
    generation_source: "manual_variant",
    generated_from_connection_id:
      sourceBundle?.generated_from_connection_id ??
      profileDetail?.reference_connection_id ??
      undefined,
    is_active: !(
      profileDetail?.bundles.some(
        (b) => b.scenario_template_id === templateId && b.is_active
      ) ?? false
    ),
    queries: cloneQueries(sourceBundle?.queries || []),
    indexes: cloneIndexes(sourceBundle?.indexes || []),
  })

  const syncEditorState = (
    profileDetail: SchemaProfileDetail | null,
    templateId: string,
    preferredBundleId?: string
  ) => {
    if (!profileDetail || !templateId) {
      setSelectedBundleId("new")
      setDraftBundle(null)
      return
    }
    const templateVariants = profileDetail.bundles.filter(
      (b) => b.scenario_template_id === templateId
    )
    if (templateVariants.length === 0) {
      setSelectedBundleId("new")
      setDraftBundle(buildEmptyDraft(templateId, profileDetail))
      return
    }
    const nextBundle =
      templateVariants.find((b) => b.id === preferredBundleId) ||
      templateVariants.find((b) => b.is_active) ||
      templateVariants[0]
    setSelectedBundleId(nextBundle.id)
    setDraftBundle(bundleToDraft(nextBundle))
  }

  const loadProfile = async (profileId: string, templateId: string, preferredBundleId?: string) => {
    if (!profileId) {
      setSelectedProfileDetail(null)
      return
    }
    setLoadingProfile(true)
    try {
      const profile = await apiClient.getSchemaProfile(profileId)
      setSelectedProfileDetail(profile)
      syncEditorState(profile, templateId, preferredBundleId)
    } catch {
      toast.error("Не удалось загрузить bundle'ы выбранного профиля")
      setSelectedProfileDetail(null)
      setDraftBundle(null)
    } finally {
      setLoadingProfile(false)
    }
  }

  const reloadAll = async (
    preferredTemplateId?: string,
    preferredProfileId?: string,
    preferredBundleId?: string,
    preferredLogicalDbId?: string
  ) => {
    setLoading(true)
    try {
      const [templatesResp, profilesResp, logicalDbResp] = await Promise.all([
        apiClient.getScenarioTemplates(),
        apiClient.getSchemaProfiles(),
        apiClient.getLogicalDatabases(),
      ])
      const nextTemplates = templatesResp.templates
      const nextProfiles = profilesResp.profiles
      const nextLogicalDbs = logicalDbResp.databases
      setTemplates(nextTemplates)
      setProfiles(nextProfiles)
      setLogicalDatabases(nextLogicalDbs)

      const nextTemplateId = preferredTemplateId || nextTemplates[0]?.id || ""
      const nextLogicalDbId = preferredLogicalDbId ?? selectedLogicalDbId
      const logicalDbProfileId = nextLogicalDbs.find((db) => db.id === nextLogicalDbId)?.schema_profile_id
      const nextProfileId = logicalDbProfileId || preferredProfileId || nextProfiles[0]?.id || ""
      setSelectedTemplateId(nextTemplateId)
      setSelectedLogicalDbId(nextLogicalDbId)
      setSelectedProfileId(nextProfileId)
      if (nextProfileId) {
        await loadProfile(nextProfileId, nextTemplateId, preferredBundleId)
      } else {
        setSelectedProfileDetail(null)
        setDraftBundle(null)
      }
    } catch {
      toast.error("Не удалось загрузить шаблоны сценариев и профили данных")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void reloadAll()
  }, [])

  // ==================== Handlers ====================

  const handleTemplateChange = async (templateId: string) => {
    setSelectedTemplateId(templateId)
    setExpandedQueries(new Set())
    syncEditorState(selectedProfileDetail, templateId)
  }

  const handleProfileChange = async (profileId: string) => {
    setSelectedProfileId(profileId)
    await loadProfile(profileId, selectedTemplateId)
  }

  const handleLogicalDatabaseChange = async (logicalDbId: string) => {
    const nextId = logicalDbId === "none" ? "" : logicalDbId
    setSelectedLogicalDbId(nextId)
    const db = logicalDatabases.find((d) => d.id === nextId)
    const nextProfileId = db?.schema_profile_id || ""
    setSelectedProfileId(nextProfileId)
    if (nextProfileId) {
      await loadProfile(nextProfileId, selectedTemplateId)
    } else {
      setSelectedProfileDetail(null)
      setDraftBundle(null)
    }
  }

  const handleVariantChange = (bundleId: string) => {
    setExpandedQueries(new Set())
    if (bundleId === "new") {
      setSelectedBundleId("new")
      setDraftBundle(buildEmptyDraft(selectedTemplateId, selectedProfileDetail, activeVariant))
      return
    }
    const bundle = variants.find((b) => b.id === bundleId)
    if (!bundle) return
    setSelectedBundleId(bundle.id)
    setDraftBundle(bundleToDraft(bundle))
  }

  const updateDraftBundle = (updater: (cur: ScenarioBundleSaveRequest) => ScenarioBundleSaveRequest) => {
    setDraftBundle((cur) => (cur ? updater(cur) : cur))
  }

  const updateQuery = (qi: number, patch: Partial<ScenarioQuery>) => {
    updateDraftBundle((cur) => ({
      ...cur,
      queries: cur.queries.map((q, i) => (i === qi ? { ...q, ...patch } : q)),
    }))
  }

  const addQuery = () => {
    updateDraftBundle((cur) => ({
      ...cur,
      queries: [
        ...cur.queries,
        { sql_template: "", query_type: "select", description: "", weight: 1, order_index: cur.queries.length, params: [] },
      ],
    }))
    setExpandedQueries((prev) => {
      const next = new Set(prev)
      next.add(draftBundle?.queries.length ?? 0)
      return next
    })
  }

  const removeQuery = (qi: number) => {
    updateDraftBundle((cur) => ({
      ...cur,
      queries: cur.queries
        .filter((_, i) => i !== qi)
        .map((q, i) => ({ ...q, order_index: i })),
    }))
    setExpandedQueries((prev) => {
      const next = new Set<number>()
      prev.forEach((idx) => { if (idx < qi) next.add(idx); else if (idx > qi) next.add(idx - 1) })
      return next
    })
  }

  const addParam = (qi: number) => {
    updateDraftBundle((cur) => ({
      ...cur,
      queries: cur.queries.map((q, i) =>
        i === qi
          ? {
              ...q,
              params: [
                ...(q.params || []),
                { param_name: "", param_type: "random_int", min_value: 1, max_value: 1000, table_ref: null, column_ref: null, string_length: 16, current_value: 0, step: 1 },
              ],
            }
          : q
      ),
    }))
  }

  const updateParam = (qi: number, pi: number, patch: Partial<ScenarioParam>) => {
    updateDraftBundle((cur) => ({
      ...cur,
      queries: cur.queries.map((q, i) =>
        i === qi
          ? { ...q, params: (q.params || []).map((p, j) => (j === pi ? { ...p, ...patch } : p)) }
          : q
      ),
    }))
  }

  const removeParam = (qi: number, pi: number) => {
    updateDraftBundle((cur) => ({
      ...cur,
      queries: cur.queries.map((q, i) =>
        i === qi ? { ...q, params: (q.params || []).filter((_, j) => j !== pi) } : q
      ),
    }))
  }

  const addIndex = () => {
    updateDraftBundle((cur) => ({
      ...cur,
      indexes: [
        ...cur.indexes,
        { table_name: "", column_names: "", index_type: "btree", index_name: null, is_unique: false, condition: null, description: "" },
      ],
    }))
  }

  const updateIndex = (ip: number, patch: Partial<ScenarioIndex>) => {
    updateDraftBundle((cur) => ({
      ...cur,
      indexes: cur.indexes.map((item, i) => (i === ip ? { ...item, ...patch } : item)),
    }))
  }

  const removeIndex = (ip: number) => {
    updateDraftBundle((cur) => ({
      ...cur,
      indexes: cur.indexes.filter((_, i) => i !== ip),
    }))
  }

  const toggleQueryExpanded = (qi: number) => {
    setExpandedQueries((prev) => {
      const next = new Set(prev)
      if (next.has(qi)) next.delete(qi)
      else next.add(qi)
      return next
    })
  }

  const handleCreateTemplate = async () => {
    const name = window.prompt("Название нового шаблона сценария")
    if (!name?.trim()) return
    const description = window.prompt("Описание шаблона", "") || ""
    try {
      const template = await apiClient.createScenarioTemplate({ name: name.trim(), description }) as ScenarioTemplate
      toast.success("Шаблон создан")
      await reloadAll(template.id, selectedProfileId)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Не удалось создать шаблон")
    }
  }

  const handleUpdateTemplate = async () => {
    if (!selectedTemplate || selectedTemplate.is_builtin) return
    const name = window.prompt("Новое название шаблона", selectedTemplate.name)
    if (!name?.trim()) return
    const description = window.prompt("Описание шаблона", selectedTemplate.description || "") || ""
    try {
      await apiClient.updateScenarioTemplate(selectedTemplate.id, { name: name.trim(), description })
      toast.success("Шаблон обновлён")
      await reloadAll(selectedTemplate.id, selectedProfileId, selectedBundleId === "new" ? undefined : selectedBundleId)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Не удалось обновить шаблон")
    }
  }

  const handleDeleteTemplate = async () => {
    if (!selectedTemplate || selectedTemplate.is_builtin) return
    if (!window.confirm(`Удалить шаблон "${selectedTemplate.name}" и все его варианты?`)) return
    try {
      await apiClient.deleteScenarioTemplate(selectedTemplate.id)
      toast.success("Шаблон удалён")
      await reloadAll()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Не удалось удалить шаблон")
    }
  }

  const handleGenerateCanonical = async () => {
    if (!selectedProfileId || !selectedTemplateId || !selectedTemplate?.is_builtin) return
    if (selectedLogicalDbBlocksBundles) {
      toast.error("Сначала подтвердите совместимость logical database")
      return
    }
    try {
      if (selectedLogicalDatabase) {
        await apiClient.generateLogicalDatabaseBundles(selectedLogicalDatabase.id, {
          scenario_template_ids: [selectedTemplateId],
        })
      } else {
        await apiClient.generateProfileBundles(selectedProfileId, { scenario_template_ids: [selectedTemplateId] })
      }
      toast.success("Канонический bundle обновлён")
      if (selectedLogicalDatabase) {
        await reloadAll(selectedTemplateId, selectedProfileId, undefined, selectedLogicalDatabase.id)
      } else {
        await loadProfile(selectedProfileId, selectedTemplateId)
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Не удалось сгенерировать bundle")
    }
  }

  const handleSaveBundle = async () => {
    if (!draftBundle || !selectedProfileId) return
    if (draftBundle.queries.length === 0) {
      toast.error("Добавьте хотя бы один SQL-запрос")
      return
    }
    setSaving(true)
    try {
      const saved = selectedBundle
        ? await apiClient.updateBundleVariant(selectedProfileId, selectedBundle.id, draftBundle)
        : await apiClient.createBundleVariant(selectedProfileId, draftBundle)
      toast.success("Bundle сохранён")
      await loadProfile(selectedProfileId, selectedTemplateId, saved.id)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Не удалось сохранить bundle")
    } finally {
      setSaving(false)
    }
  }

  const handleCloneBundle = async () => {
    if (!selectedBundle || !selectedProfileId) return
    const name = window.prompt("Название нового варианта", `${selectedBundle.name} (копия)`)
    if (!name?.trim()) return
    try {
      const cloned = await apiClient.cloneBundleVariant(selectedProfileId, selectedBundle.id, { name: name.trim() })
      toast.success("Вариант склонирован")
      await loadProfile(selectedProfileId, selectedTemplateId, cloned.id)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Не удалось клонировать вариант")
    }
  }

  const handleActivateBundle = async () => {
    if (!selectedBundle || !selectedProfileId || selectedBundle.is_active) return
    if (selectedLogicalDbBlocksBundles) {
      toast.error("Сначала подтвердите совместимость logical database")
      return
    }
    try {
      await apiClient.activateBundleVariant(selectedProfileId, selectedBundle.id)
      toast.success("Вариант активирован")
      await loadProfile(selectedProfileId, selectedTemplateId, selectedBundle.id)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Не удалось активировать вариант")
    }
  }

  const handleDeleteBundle = async () => {
    if (!selectedBundle || !selectedProfileId) return
    if (!window.confirm(`Удалить вариант "${selectedBundle.name}"?`)) return
    try {
      await apiClient.deleteBundleVariant(selectedProfileId, selectedBundle.id)
      toast.success("Вариант удалён")
      await loadProfile(selectedProfileId, selectedTemplateId)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Не удалось удалить вариант")
    }
  }

  // ==================== Render ====================

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Сценарии тестирования</h1>
          <p className="text-muted-foreground">
            Управление шаблонами сценариев и вариантами bundle по профилям модели данных
          </p>
        </div>
        <Button onClick={handleCreateTemplate}>
          <Plus className="mr-2 h-4 w-4" />
          Новый шаблон
        </Button>
      </div>

      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Встроенные шаблоны (отмечены значком{" "} <Badge variant="secondary" className="mx-1">builtin</Badge>) нельзя редактировать, но можно создавать собственные варианты bundle.
        </AlertDescription>
      </Alert>

      {/* Основной контент: список + детали */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">

        {/* Левая панель: список шаблонов */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Layers className="h-5 w-5" />
              Шаблоны сценариев
            </CardTitle>
            <CardDescription>{templates.length} шаблонов</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              {templates.map((template) => (
                <button
                  key={template.id}
                  onClick={() => void handleTemplateChange(template.id)}
                  className={cn(
                    "w-full text-left p-3 rounded-lg border transition-colors",
                    selectedTemplateId === template.id
                      ? "border-primary bg-primary/10"
                      : "border-border hover:border-muted-foreground"
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-medium text-sm leading-snug">{template.name}</span>
                    {template.is_builtin && (
                      <Badge variant="secondary" className="shrink-0 text-xs">builtin</Badge>
                    )}
                  </div>
                  {template.description && (
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                      {template.description}
                    </p>
                  )}
                </button>
              ))}
              {templates.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-4">
                  Нет доступных шаблонов
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Правая панель: детали шаблона */}
        <Card className="lg:col-span-2">
          {!selectedTemplate ? (
            <div className="flex flex-col items-center justify-center h-[400px] text-center p-8">
              <FileCode2 className="h-16 w-16 text-muted-foreground/40 mb-4" />
              <h3 className="text-lg font-medium text-muted-foreground">Выберите шаблон сценария</h3>
              <p className="text-sm text-muted-foreground mt-2 max-w-sm">
                Шаблоны содержат варианты bundle с SQL-запросами и индексами для нагрузочного тестирования
              </p>
            </div>
          ) : (
            <>
              <CardHeader className="pb-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <CardTitle className="flex flex-wrap items-center gap-2">
                      <span className="break-words">{selectedTemplate.name}</span>
                      {selectedTemplate.is_builtin && (
                        <Badge variant="secondary">builtin</Badge>
                      )}
                    </CardTitle>
                    {selectedTemplate.description && (
                      <CardDescription className="mt-1">{selectedTemplate.description}</CardDescription>
                    )}
                  </div>
                  {!selectedTemplate.is_builtin && (
                    <div className="flex gap-2 shrink-0">
                      <Button variant="outline" size="sm" onClick={handleUpdateTemplate}>
                        <Pencil className="mr-2 h-3.5 w-3.5" />
                        Редактировать
                      </Button>
                      <Button variant="outline" size="sm" onClick={handleDeleteTemplate}>
                        <Trash2 className="mr-2 h-3.5 w-3.5" />
                        Удалить
                      </Button>
                    </div>
                  )}
                </div>
              </CardHeader>

              <CardContent className="space-y-6">
                {/* Выбор контекста (БД / профиль) */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 rounded-lg border bg-muted/20">
                  <div className="space-y-2">
                    <Label>База данных</Label>
                    <Select
                      value={selectedLogicalDbId || "none"}
                      onValueChange={(v) => void handleLogicalDatabaseChange(v)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Выберите базу данных" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">Без контекста базы данных</SelectItem>
                        {logicalDatabases.map((db) => (
                          <SelectItem key={db.id} value={db.id}>{db.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {selectedLogicalDatabase && (
                      <div className="space-y-1 text-xs text-muted-foreground">
                        <p>Профиль: {selectedLogicalDatabase.schema_profile_name || "не назначен"}</p>
                        <p>Reference: {selectedLogicalDatabase.reference_connection_name || "не выбран"}</p>
                        <p>
                          Статус: {selectedLogicalDatabase.profile_status || "unknown"} ·{" "}
                          {selectedLogicalDatabase.compatibility_status || "unknown"}
                        </p>
                      </div>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label>Профиль модели данных</Label>
                    <Select
                      value={selectedProfileId}
                      onValueChange={(v) => void handleProfileChange(v)}
                      disabled={Boolean(selectedLogicalDatabase?.schema_profile_id)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Выберите профиль данных" />
                      </SelectTrigger>
                      <SelectContent>
                        {profiles.map((profile) => (
                          <SelectItem key={profile.id} value={profile.id}>{profile.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {selectedLogicalDatabase?.schema_profile_id && (
                      <p className="text-xs text-muted-foreground">
                        Профиль зафиксирован выбранной базой данных
                      </p>
                    )}
                    {selectedProfileDetail?.description && (
                      <p className="text-xs text-muted-foreground">{selectedProfileDetail.description}</p>
                    )}
                  </div>
                </div>

                {/* Bundle варианты */}
                {selectedLogicalDbBlocksBundles && (
                  <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>
                      Генерация и активация bundle заблокированы: logical database требует подтверждения профиля или несовместима.
                    </AlertDescription>
                  </Alert>
                )}

                {loadingProfile ? (
                  <div className="flex items-center justify-center py-12 text-muted-foreground">
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Загружаем варианты...
                  </div>
                ) : !selectedProfileId ? (
                  <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
                    Выберите профиль модели данных для просмотра и редактирования вариантов bundle
                  </div>
                ) : !draftBundle ? (
                  <div className="space-y-4">
                    <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
                      Для выбранной пары профиль / шаблон вариантов пока нет.
                    </div>
                    <div className="flex gap-2 justify-center">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleVariantChange("new")}
                      >
                        <Plus className="mr-2 h-4 w-4" />
                        Создать вариант вручную
                      </Button>
                      {selectedTemplate.is_builtin && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleGenerateCanonical}
                          disabled={selectedLogicalDbBlocksBundles}
                        >
                          <WandSparkles className="mr-2 h-4 w-4" />
                          Сгенерировать canonical
                        </Button>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {/* Выбор варианта + действия */}
                    <div className="space-y-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="flex-1 min-w-[180px]">
                          <Select value={selectedBundleId} onValueChange={handleVariantChange}>
                            <SelectTrigger>
                              <SelectValue placeholder="Выберите вариант" />
                            </SelectTrigger>
                            <SelectContent>
                              {variants.map((bundle) => (
                                <SelectItem key={bundle.id} value={bundle.id}>
                                  {bundle.name}{bundle.is_active ? " (активный)" : ""}
                                </SelectItem>
                              ))}
                              <SelectItem value="new">+ Новый вариант</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>

                        <div className="flex flex-wrap gap-2">
                          <Button variant="outline" size="sm" onClick={() => handleVariantChange("new")}>
                            <Plus className="mr-1.5 h-3.5 w-3.5" />
                            Новый
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={!selectedBundle}
                            onClick={handleCloneBundle}
                          >
                            <Copy className="mr-1.5 h-3.5 w-3.5" />
                            Клонировать
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={!selectedBundle || selectedBundle.is_active || selectedLogicalDbBlocksBundles}
                            onClick={handleActivateBundle}
                          >
                            <Check className="mr-1.5 h-3.5 w-3.5" />
                            Активировать
                          </Button>
                          {selectedTemplate.is_builtin && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={handleGenerateCanonical}
                              disabled={selectedLogicalDbBlocksBundles}
                            >
                              <WandSparkles className="mr-1.5 h-3.5 w-3.5" />
                              Canonical
                            </Button>
                          )}
                          <Button size="sm" disabled={saving} onClick={handleSaveBundle}>
                            {saving
                              ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                              : <Save className="mr-1.5 h-3.5 w-3.5" />
                            }
                            Сохранить
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={!selectedBundle || selectedBundle.is_builtin || selectedBundle.is_active}
                            onClick={handleDeleteBundle}
                          >
                            <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                            Удалить
                          </Button>
                        </div>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        {selectedBundle?.is_active && <Badge variant="outline">активный</Badge>}
                        {selectedBundle?.is_builtin && <Badge variant="outline">builtin</Badge>}
                        <Badge variant="outline">запросов: {draftBundle.queries.length}</Badge>
                        <Badge variant="outline">индексов: {draftBundle.indexes.length}</Badge>
                      </div>
                    </div>

                    {/* Мета варианта */}
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="space-y-2">
                        <Label>Название варианта</Label>
                        <Input
                          value={draftBundle.name}
                          onChange={(e) => updateDraftBundle((cur) => ({ ...cur, name: e.target.value }))}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Источник генерации</Label>
                        <Input
                          value={draftBundle.generation_source || "manual_variant"}
                          onChange={(e) => updateDraftBundle((cur) => ({ ...cur, generation_source: e.target.value }))}
                        />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label>Описание варианта</Label>
                      <Textarea
                        value={draftBundle.description || ""}
                        rows={2}
                        onChange={(e) => updateDraftBundle((cur) => ({ ...cur, description: e.target.value }))}
                      />
                    </div>

                    {/* SQL-запросы */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <h3 className="text-sm font-medium flex items-center gap-2">
                          <FileCode2 className="h-4 w-4" />
                          SQL-запросы
                          <Badge variant="outline">{draftBundle.queries.length}</Badge>
                        </h3>
                        <Button variant="outline" size="sm" onClick={addQuery}>
                          <Plus className="mr-1.5 h-3.5 w-3.5" />
                          Добавить запрос
                        </Button>
                      </div>

                      {draftBundle.queries.length === 0 && (
                        <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground text-center">
                          Нет SQL-запросов. Добавьте хотя бы один для сохранения варианта.
                        </div>
                      )}

                      <div className="space-y-2">
                        {draftBundle.queries.map((query, qi) => {
                          const isExpanded = expandedQueries.has(qi)
                          const preview = query.description || (query.sql_template ? query.sql_template.slice(0, 60) : "")
                          return (
                            <div key={`q-${qi}`} className="rounded-lg border overflow-hidden">
                              {/* Заголовок запроса (кликабельный) */}
                              <button
                                className="w-full flex items-center justify-between gap-2 p-3 hover:bg-muted/30 transition-colors text-left"
                                onClick={() => toggleQueryExpanded(qi)}
                              >
                                <div className="flex items-center gap-2 min-w-0">
                                  <Badge className="shrink-0">{qi + 1}</Badge>
                                  <Badge variant="outline" className="shrink-0">{query.query_type}</Badge>
                                  <span className="text-sm text-muted-foreground truncate">
                                    {preview || "без описания"}
                                  </span>
                                </div>
                                <div className="flex items-center gap-3 shrink-0">
                                  <span className="text-xs text-muted-foreground">вес: {query.weight}</span>
                                  <ChevronDown
                                    className={cn("h-4 w-4 text-muted-foreground transition-transform", isExpanded && "rotate-180")}
                                  />
                                </div>
                              </button>

                              {/* Раскрываемое содержимое */}
                              {isExpanded && (
                                <div className="border-t p-3 space-y-3">
                                  <div className="grid gap-3 md:grid-cols-3">
                                    <div className="space-y-1.5">
                                      <Label className="text-xs">Тип запроса</Label>
                                      <Input
                                        value={query.query_type}
                                        onChange={(e) => updateQuery(qi, { query_type: e.target.value })}
                                      />
                                    </div>
                                    <div className="space-y-1.5">
                                      <Label className="text-xs">Вес</Label>
                                      <Input
                                        type="number"
                                        min={1}
                                        value={query.weight}
                                        onChange={(e) => updateQuery(qi, { weight: Number(e.target.value) || 1 })}
                                      />
                                    </div>
                                    <div className="space-y-1.5">
                                      <Label className="text-xs">Порядок</Label>
                                      <Input
                                        type="number"
                                        min={0}
                                        value={query.order_index}
                                        onChange={(e) => updateQuery(qi, { order_index: Number(e.target.value) || 0 })}
                                      />
                                    </div>
                                  </div>

                                  <div className="space-y-1.5">
                                    <Label className="text-xs">Описание</Label>
                                    <Input
                                      value={query.description || ""}
                                      onChange={(e) => updateQuery(qi, { description: e.target.value })}
                                    />
                                  </div>

                                  <div className="space-y-1.5">
                                    <Label className="text-xs">SQL-шаблон</Label>
                                    <Textarea
                                      className="min-h-[120px] font-mono text-xs"
                                      value={query.sql_template}
                                      onChange={(e) => updateQuery(qi, { sql_template: e.target.value })}
                                    />
                                  </div>

                                  {/* Параметры запроса */}
                                  <div className="space-y-2">
                                    <div className="flex items-center justify-between">
                                      <span className="text-xs font-medium text-muted-foreground">
                                        Параметры ({(query.params || []).length})
                                      </span>
                                      <Button variant="outline" size="sm" onClick={() => addParam(qi)}>
                                        <Plus className="mr-1.5 h-3 w-3" />
                                        Параметр
                                      </Button>
                                    </div>
                                    {(query.params || []).map((param, pi) => (
                                      <div key={`p-${qi}-${pi}`} className="rounded-md border bg-muted/20 p-3 space-y-2">
                                        <div className="grid gap-2 md:grid-cols-2">
                                          <div className="space-y-1.5">
                                            <Label className="text-xs">Имя параметра</Label>
                                            <Input
                                              value={param.param_name}
                                              onChange={(e) => updateParam(qi, pi, { param_name: e.target.value })}
                                            />
                                          </div>
                                          <div className="space-y-1.5">
                                            <Label className="text-xs">Тип</Label>
                                            <Input
                                              value={param.param_type}
                                              onChange={(e) => updateParam(qi, pi, { param_type: e.target.value })}
                                            />
                                          </div>
                                          <div className="space-y-1.5">
                                            <Label className="text-xs">Min</Label>
                                            <Input
                                              type="number"
                                              value={param.min_value ?? ""}
                                              onChange={(e) => updateParam(qi, pi, { min_value: e.target.value === "" ? null : Number(e.target.value) })}
                                            />
                                          </div>
                                          <div className="space-y-1.5">
                                            <Label className="text-xs">Max</Label>
                                            <Input
                                              type="number"
                                              value={param.max_value ?? ""}
                                              onChange={(e) => updateParam(qi, pi, { max_value: e.target.value === "" ? null : Number(e.target.value) })}
                                            />
                                          </div>
                                          <div className="space-y-1.5">
                                            <Label className="text-xs">Таблица (table_ref)</Label>
                                            <Input
                                              value={param.table_ref ?? ""}
                                              onChange={(e) => updateParam(qi, pi, { table_ref: e.target.value || null })}
                                            />
                                          </div>
                                          <div className="space-y-1.5">
                                            <Label className="text-xs">Колонка (column_ref)</Label>
                                            <Input
                                              value={param.column_ref ?? ""}
                                              onChange={(e) => updateParam(qi, pi, { column_ref: e.target.value || null })}
                                            />
                                          </div>
                                          <div className="space-y-1.5">
                                            <Label className="text-xs">Паттерн (string_pattern)</Label>
                                            <Input
                                              value={param.string_pattern ?? ""}
                                              onChange={(e) => updateParam(qi, pi, { string_pattern: e.target.value || null })}
                                            />
                                          </div>
                                          <div className="space-y-1.5">
                                            <Label className="text-xs">Длина строки</Label>
                                            <Input
                                              type="number"
                                              value={param.string_length ?? ""}
                                              onChange={(e) => updateParam(qi, pi, { string_length: e.target.value === "" ? null : Number(e.target.value) })}
                                            />
                                          </div>
                                        </div>
                                        <div className="flex justify-end">
                                          <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => removeParam(qi, pi)}
                                          >
                                            <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                                            Удалить параметр
                                          </Button>
                                        </div>
                                      </div>
                                    ))}
                                  </div>

                                  <div className="flex justify-end pt-1">
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      onClick={() => removeQuery(qi)}
                                    >
                                      <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                                      Удалить запрос
                                    </Button>
                                  </div>
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    </div>

                    {/* Индексы */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <h3 className="text-sm font-medium flex items-center gap-2">
                          <Database className="h-4 w-4" />
                          Индексы
                          <Badge variant="outline">{draftBundle.indexes.length}</Badge>
                        </h3>
                        <Button variant="outline" size="sm" onClick={addIndex}>
                          <Plus className="mr-1.5 h-3.5 w-3.5" />
                          Добавить индекс
                        </Button>
                      </div>

                      {draftBundle.indexes.length === 0 && (
                        <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground text-center">
                          Индексы не заданы
                        </div>
                      )}

                      <div className="space-y-2">
                        {draftBundle.indexes.map((index, ip) => (
                          <div key={`idx-${ip}`} className="rounded-lg border p-3 space-y-3">
                            <div className="flex items-center justify-between">
                              <span className="text-sm font-medium text-muted-foreground">
                                Индекс {ip + 1}{index.table_name ? ` — ${index.table_name}` : ""}
                              </span>
                              <Button variant="outline" size="sm" onClick={() => removeIndex(ip)}>
                                <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                                Удалить
                              </Button>
                            </div>
                            <div className="grid gap-3 md:grid-cols-2">
                              <div className="space-y-1.5">
                                <Label className="text-xs">Таблица</Label>
                                <Input
                                  value={index.table_name}
                                  onChange={(e) => updateIndex(ip, { table_name: e.target.value })}
                                />
                              </div>
                              <div className="space-y-1.5">
                                <Label className="text-xs">Колонки</Label>
                                <Input
                                  value={index.column_names}
                                  onChange={(e) => updateIndex(ip, { column_names: e.target.value })}
                                />
                              </div>
                              <div className="space-y-1.5">
                                <Label className="text-xs">Тип индекса</Label>
                                <Input
                                  value={index.index_type}
                                  onChange={(e) => updateIndex(ip, { index_type: e.target.value })}
                                />
                              </div>
                              <div className="space-y-1.5">
                                <Label className="text-xs">Имя индекса (index_name)</Label>
                                <Input
                                  value={index.index_name ?? ""}
                                  onChange={(e) => updateIndex(ip, { index_name: e.target.value || null })}
                                />
                              </div>
                              <div className="space-y-1.5">
                                <Label className="text-xs">Условие (condition)</Label>
                                <Input
                                  value={index.condition ?? ""}
                                  onChange={(e) => updateIndex(ip, { condition: e.target.value || null })}
                                />
                              </div>
                              <div className="space-y-1.5">
                                <Label className="text-xs">Уникальный</Label>
                                <Select
                                  value={index.is_unique ? "true" : "false"}
                                  onValueChange={(v) => updateIndex(ip, { is_unique: v === "true" })}
                                >
                                  <SelectTrigger>
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="false">Нет</SelectItem>
                                    <SelectItem value="true">Да</SelectItem>
                                  </SelectContent>
                                </Select>
                              </div>
                            </div>
                            <div className="space-y-1.5">
                              <Label className="text-xs">Описание</Label>
                              <Input
                                value={index.description ?? ""}
                                onChange={(e) => updateIndex(ip, { description: e.target.value || null })}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </>
          )}
        </Card>
      </div>
    </div>
  )
}
