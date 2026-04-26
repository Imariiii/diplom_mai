"use client"

import { useEffect, useMemo, useState } from "react"
import {
  AlertTriangle,
  ChevronDown,
  Database,
  FileCode2,
  Layers,
  Loader2,
  MoreHorizontal,
  Pencil,
  Plus,
  Save,
  Search,
  SlidersHorizontal,
  Sparkles,
  Trash2,
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
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

const TEMPLATE_ACCENTS = [
  "from-emerald-500/20 to-cyan-500/10 text-emerald-500",
  "from-blue-500/20 to-indigo-500/10 text-blue-500",
  "from-violet-500/20 to-fuchsia-500/10 text-violet-500",
  "from-amber-500/20 to-orange-500/10 text-amber-500",
  "from-rose-500/20 to-pink-500/10 text-rose-500",
]

function shortText(value: string | null | undefined, fallback = "Описание не задано") {
  const text = value?.trim()
  return text ? text : fallback
}

function statusLabel(value: string | null | undefined) {
  const labels: Record<string, string> = {
    draft: "черновик",
    confirmed: "подтверждён",
    needs_review: "нужна проверка",
    incompatible: "несовместим",
    unknown: "неизвестно",
    valid: "валидна",
    valid_with_warnings: "с предупреждениями",
    invalid: "ошибка",
  }
  return value ? labels[value] || value : "не задан"
}

function statusTone(value: string | null | undefined) {
  if (value === "valid" || value === "confirmed") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
  if (value === "valid_with_warnings" || value === "needs_review" || value === "draft") return "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400"
  if (value === "invalid" || value === "incompatible") return "border-destructive/30 bg-destructive/10 text-destructive"
  return "border-border bg-muted text-muted-foreground"
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
  const [templateSearch, setTemplateSearch] = useState("")

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

  const filteredTemplates = useMemo(() => {
    const query = templateSearch.trim().toLowerCase()
    if (!query) return templates
    return templates.filter((template) =>
      `${template.name} ${template.description || ""}`.toLowerCase().includes(query)
    )
  }, [templates, templateSearch])

  const totalQueries = draftBundle?.queries.length ?? 0
  const totalIndexes = draftBundle?.indexes.length ?? 0
  const totalParams = draftBundle?.queries.reduce((sum, query) => sum + (query.params?.length || 0), 0) ?? 0

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
      setDraftBundle(null)
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

  const handleSaveBundle = async () => {
    if (!draftBundle || !selectedProfileId || !selectedBundle) return
    if (draftBundle.queries.length === 0) {
      toast.error("Добавьте хотя бы один SQL-запрос")
      return
    }
    setSaving(true)
    try {
      const saved = await apiClient.updateBundleVariant(selectedProfileId, selectedBundle.id, draftBundle)
      toast.success("Изменения bundle сохранены")
      await loadProfile(selectedProfileId, selectedTemplateId, saved.id)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Не удалось сохранить bundle")
    } finally {
      setSaving(false)
    }
  }

  // ==================== Render ====================

  if (loading) {
    return (
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-4 w-96 max-w-full" />
          </div>
          <Skeleton className="h-9 w-36" />
        </div>
        <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
          <Skeleton className="h-[560px] rounded-xl" />
          <Skeleton className="h-[720px] rounded-xl" />
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-[1500px] p-4 space-y-5 md:p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 rounded-full border bg-muted/40 px-3 py-1 text-xs font-medium text-muted-foreground">
              <Sparkles className="h-3.5 w-3.5 text-primary" />
              Библиотека сценариев нагрузочного тестирования
            </div>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">Сценарии тестирования</h1>
              <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
                Выберите шаблон, привяжите его к logical database или профилю данных и настройте активный bundle.
              </p>
            </div>
          </div>
          <Button onClick={handleCreateTemplate} className="md:self-center">
            <Plus className="h-4 w-4" />
            Новый шаблон
          </Button>
        </div>

        <div className="grid gap-5 lg:grid-cols-[320px_minmax(0,1fr)]">
          <Card className="overflow-hidden lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)]">
            <CardHeader className="space-y-4 pb-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Layers className="h-4 w-4 text-primary" />
                    Шаблоны
                  </CardTitle>
                  <CardDescription>{templates.length} доступно</CardDescription>
                </div>
                <Badge variant="outline" className="rounded-full">
                  {filteredTemplates.length}
                </Badge>
              </div>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={templateSearch}
                  onChange={(e) => setTemplateSearch(e.target.value)}
                  placeholder="Поиск шаблона..."
                  className="pl-9"
                />
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <ScrollArea className="h-[calc(100vh-230px)] min-h-[360px]">
                <div className="space-y-2 p-3 pt-0">
                  {filteredTemplates.map((template, index) => {
                    const isSelected = selectedTemplateId === template.id
                    const accent = TEMPLATE_ACCENTS[index % TEMPLATE_ACCENTS.length]
                    return (
                      <button
                        key={template.id}
                        onClick={() => void handleTemplateChange(template.id)}
                        className={cn(
                          "group w-full rounded-xl border p-3 text-left transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:bg-muted/40",
                          isSelected
                            ? "border-primary/50 bg-primary/10 shadow-sm"
                            : "border-border bg-card"
                        )}
                      >
                        <div className="flex items-start gap-3">
                          <div className={cn("rounded-lg bg-gradient-to-br p-2", accent)}>
                            <Layers className="h-4 w-4" />
                          </div>
                          <div className="min-w-0 flex-1 space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="truncate text-sm font-medium">{template.name}</span>
                              {template.is_builtin && (
                                <Badge variant="secondary" className="h-5 shrink-0 px-1.5 text-[10px]">
                                  builtin
                                </Badge>
                              )}
                            </div>
                            <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                              {shortText(template.description, "Пользовательский шаблон без описания")}
                            </p>
                          </div>
                        </div>
                      </button>
                    )
                  })}
                  {filteredTemplates.length === 0 && (
                    <Empty className="border p-6">
                      <EmptyHeader>
                        <EmptyMedia variant="icon">
                          <Search className="h-5 w-5" />
                        </EmptyMedia>
                        <EmptyTitle className="text-base">Ничего не найдено</EmptyTitle>
                        <EmptyDescription>Попробуйте изменить поисковый запрос или создайте новый шаблон.</EmptyDescription>
                      </EmptyHeader>
                    </Empty>
                  )}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>

          {!selectedTemplate ? (
            <Card>
              <CardContent className="p-6">
                <Empty className="min-h-[520px] border">
                  <EmptyHeader>
                    <EmptyMedia variant="icon">
                      <FileCode2 className="h-6 w-6" />
                    </EmptyMedia>
                    <EmptyTitle>Выберите шаблон сценария</EmptyTitle>
                    <EmptyDescription>
                      После выбора откроются контекст logical database, варианты bundle, SQL-запросы и индексы.
                    </EmptyDescription>
                  </EmptyHeader>
                </Empty>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-5">
              <Card className="overflow-hidden border-primary/10 bg-gradient-to-br from-primary/10 via-card to-card">
                <CardHeader className="pb-4">
                  <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                    <div className="flex min-w-0 gap-4">
                      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-primary/15 text-primary">
                        <Layers className="h-6 w-6" />
                      </div>
                      <div className="min-w-0 space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <CardTitle className="break-words text-xl md:text-2xl">{selectedTemplate.name}</CardTitle>
                          {selectedTemplate.is_builtin && <Badge variant="secondary">builtin</Badge>}
                        </div>
                        <CardDescription className="max-w-3xl text-sm leading-relaxed">
                          {shortText(
                            selectedTemplate.description,
                            "Описание шаблона не задано. Используйте bundle ниже, чтобы зафиксировать назначение запросов и индексов."
                          )}
                        </CardDescription>
                      </div>
                    </div>

                    {!selectedTemplate.is_builtin && (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="outline" size="icon-sm" aria-label="Действия с шаблоном">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuLabel>Шаблон</DropdownMenuLabel>
                          <DropdownMenuItem onSelect={handleUpdateTemplate}>
                            <Pencil className="h-4 w-4" />
                            Редактировать
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem variant="destructive" onSelect={handleDeleteTemplate}>
                            <Trash2 className="h-4 w-4" />
                            Удалить
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <div className="rounded-xl border bg-background/70 p-3">
                    <p className="text-xs text-muted-foreground">Варианты bundle</p>
                    <p className="mt-1 text-2xl font-semibold">{variants.length}</p>
                  </div>
                  <div className="rounded-xl border bg-background/70 p-3">
                    <p className="text-xs text-muted-foreground">SQL-запросы</p>
                    <p className="mt-1 text-2xl font-semibold">{totalQueries}</p>
                  </div>
                  <div className="rounded-xl border bg-background/70 p-3">
                    <p className="text-xs text-muted-foreground">Параметры</p>
                    <p className="mt-1 text-2xl font-semibold">{totalParams}</p>
                  </div>
                  <div className="rounded-xl border bg-background/70 p-3">
                    <p className="text-xs text-muted-foreground">Индексы</p>
                    <p className="mt-1 text-2xl font-semibold">{totalIndexes}</p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <SlidersHorizontal className="h-4 w-4 text-primary" />
                    Контекст выполнения
                  </CardTitle>
                  <CardDescription>
                    Logical database фиксирует профиль и reference-подключение; без неё можно выбрать профиль вручную.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-4 xl:grid-cols-2">
                    <div className="space-y-2">
                      <Label>Logical database</Label>
                      <Select
                        value={selectedLogicalDbId || "none"}
                        onValueChange={(v) => void handleLogicalDatabaseChange(v)}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Выберите logical database" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">Без контекста logical database</SelectItem>
                          {logicalDatabases.map((db) => (
                            <SelectItem key={db.id} value={db.id}>{db.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
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
                    </div>
                  </div>

                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-xl border bg-muted/20 p-3">
                      <p className="text-xs text-muted-foreground">Профиль</p>
                      <p className="mt-1 truncate text-sm font-medium">
                        {selectedLogicalDatabase?.schema_profile_name || selectedProfileDetail?.name || "не выбран"}
                      </p>
                      {selectedLogicalDatabase?.schema_profile_id && (
                        <p className="mt-1 text-xs text-muted-foreground">Зафиксирован logical database</p>
                      )}
                    </div>
                    <div className="rounded-xl border bg-muted/20 p-3">
                      <p className="text-xs text-muted-foreground">Reference</p>
                      <p className="mt-1 truncate text-sm font-medium">
                        {selectedLogicalDatabase?.reference_connection_name || selectedProfileDetail?.reference_connection_id || "не выбран"}
                      </p>
                    </div>
                    <div className="rounded-xl border bg-muted/20 p-3">
                      <p className="text-xs text-muted-foreground">Статусы</p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        <Badge variant="outline" className={cn("rounded-full", statusTone(selectedLogicalDatabase?.profile_status))}>
                          {statusLabel(selectedLogicalDatabase?.profile_status)}
                        </Badge>
                        <Badge variant="outline" className={cn("rounded-full", statusTone(selectedLogicalDatabase?.compatibility_status))}>
                          {statusLabel(selectedLogicalDatabase?.compatibility_status)}
                        </Badge>
                      </div>
                    </div>
                  </div>

                  {selectedProfileDetail?.description && (
                    <p className="rounded-xl border bg-muted/20 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
                      {selectedProfileDetail.description}
                    </p>
                  )}

                  {selectedLogicalDbBlocksBundles && (
                    <Alert variant="destructive">
                      <AlertTriangle className="h-4 w-4" />
                      <AlertDescription>
                        Генерация и активация bundle заблокированы: logical database требует подтверждения профиля или несовместима.
                      </AlertDescription>
                    </Alert>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-3">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2 text-base">
                        <FileCode2 className="h-4 w-4 text-primary" />
                        Bundle
                      </CardTitle>
                      <CardDescription>
                        Метаданные доступны для просмотра, SQL-запросы и индексы можно изменять.
                      </CardDescription>
                    </div>
                    {draftBundle && (
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="rounded-xl border bg-muted/20 px-3 py-2 text-sm">
                          <p className="text-xs text-muted-foreground">Текущий bundle</p>
                          <p className="mt-1 font-medium">{draftBundle.name}</p>
                        </div>
                        <Button disabled={saving || !selectedBundle} onClick={handleSaveBundle}>
                          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                          Сохранить
                        </Button>
                      </div>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="space-y-5">
                  {loadingProfile ? (
                    <div className="flex min-h-[260px] items-center justify-center rounded-xl border bg-muted/20 text-sm text-muted-foreground">
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Загружаем варианты...
                    </div>
                  ) : !selectedProfileId ? (
                    <Empty className="border">
                      <EmptyHeader>
                        <EmptyMedia variant="icon">
                          <Database className="h-5 w-5" />
                        </EmptyMedia>
                        <EmptyTitle>Нужен профиль данных</EmptyTitle>
                        <EmptyDescription>
                          Выберите logical database или профиль модели данных, чтобы открыть варианты bundle.
                        </EmptyDescription>
                      </EmptyHeader>
                    </Empty>
                  ) : !draftBundle ? (
                    <Empty className="border">
                      <EmptyHeader>
                        <EmptyMedia variant="icon">
                          <AlertCircle className="h-5 w-5" />
                        </EmptyMedia>
                        <EmptyTitle>Вариантов пока нет</EmptyTitle>
                        <EmptyDescription>
                          Для выбранной пары профиль / шаблон ещё не создан bundle.
                        </EmptyDescription>
                      </EmptyHeader>
                    </Empty>
                  ) : (
                    <>
                      <div className="flex flex-wrap gap-2">
                        {selectedBundle?.is_active && <Badge className="rounded-full">активный</Badge>}
                        {selectedBundle?.is_builtin && <Badge variant="secondary" className="rounded-full">builtin</Badge>}
                        <Badge variant="outline" className="rounded-full">запросов: {draftBundle.queries.length}</Badge>
                        <Badge variant="outline" className="rounded-full">индексов: {draftBundle.indexes.length}</Badge>
                        <Badge variant="outline" className="rounded-full">источник: {draftBundle.generation_source || "manual_variant"}</Badge>
                      </div>

                      <div className="rounded-2xl border bg-muted/20 p-4 space-y-4">
                        <div className="grid gap-4 md:grid-cols-2">
                          <div className="space-y-2">
                            <Label>Название варианта</Label>
                            <Input
                              value={draftBundle.name}
                              readOnly
                              className="cursor-default"
                            />
                          </div>
                          <div className="space-y-2">
                            <Label>Источник генерации</Label>
                            <Input
                              value={draftBundle.generation_source || "manual_variant"}
                              readOnly
                              className="cursor-default"
                            />
                          </div>
                        </div>
                        <div className="space-y-2">
                          <Label>Описание варианта</Label>
                          <Textarea
                            value={draftBundle.description || ""}
                            rows={2}
                            placeholder="Коротко опишите назначение этого bundle"
                            readOnly
                            className="cursor-default resize-none"
                          />
                        </div>
                      </div>

                      <Tabs defaultValue="queries" className="space-y-4">
                        <TabsList className="grid w-full grid-cols-2 md:w-fit">
                          <TabsTrigger value="queries" className="gap-2">
                            SQL-запросы
                            <Badge variant="secondary" className="h-5 px-1.5">{draftBundle.queries.length}</Badge>
                          </TabsTrigger>
                          <TabsTrigger value="indexes" className="gap-2">
                            Индексы
                            <Badge variant="secondary" className="h-5 px-1.5">{draftBundle.indexes.length}</Badge>
                          </TabsTrigger>
                        </TabsList>

                        <TabsContent value="queries" className="space-y-3">
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <h3 className="text-sm font-medium">SQL-запросы сценария</h3>
                              <p className="text-xs text-muted-foreground">Разверните запрос, чтобы изменить SQL-шаблон и параметры.</p>
                            </div>
                            <Button variant="outline" size="sm" onClick={addQuery}>
                              <Plus className="h-3.5 w-3.5" />
                              Добавить запрос
                            </Button>
                          </div>

                          {draftBundle.queries.length === 0 && (
                            <Empty className="border p-6">
                              <EmptyHeader>
                                <EmptyTitle className="text-base">Нет SQL-запросов</EmptyTitle>
                                <EmptyDescription>Добавьте хотя бы один запрос, чтобы сохранить вариант.</EmptyDescription>
                              </EmptyHeader>
                            </Empty>
                          )}

                          <div className="space-y-2">
                            {draftBundle.queries.map((query, qi) => {
                              const isExpanded = expandedQueries.has(qi)
                              const preview = query.description || (query.sql_template ? query.sql_template.slice(0, 90) : "")
                              return (
                                <div key={`q-${qi}`} className="overflow-hidden rounded-xl border bg-card">
                                  <button
                                    className="w-full p-4 text-left transition-colors hover:bg-muted/35"
                                    onClick={() => toggleQueryExpanded(qi)}
                                  >
                                    <div className="flex items-start justify-between gap-3">
                                      <div className="flex min-w-0 gap-3">
                                        <Badge className="mt-0.5 h-6 w-6 justify-center rounded-full p-0">{qi + 1}</Badge>
                                        <div className="min-w-0">
                                          <div className="flex flex-wrap items-center gap-2">
                                            <Badge variant="outline" className="uppercase">{query.query_type || "select"}</Badge>
                                            <span className="text-xs text-muted-foreground">вес: {query.weight}</span>
                                            {(query.params || []).length > 0 && (
                                              <span className="text-xs text-muted-foreground">
                                                параметров: {(query.params || []).length}
                                              </span>
                                            )}
                                          </div>
                                          <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
                                            {preview || "Без описания"}
                                          </p>
                                        </div>
                                      </div>
                                      <ChevronDown
                                        className={cn(
                                          "mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform",
                                          isExpanded && "rotate-180"
                                        )}
                                      />
                                    </div>
                                  </button>

                                  {isExpanded && (
                                    <div className="border-t bg-muted/10 p-4 space-y-4">
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
                                          className="min-h-[140px] font-mono text-xs leading-relaxed"
                                          value={query.sql_template}
                                          onChange={(e) => updateQuery(qi, { sql_template: e.target.value })}
                                        />
                                      </div>

                                      <Separator />

                                      <div className="space-y-3">
                                        <div className="flex items-center justify-between">
                                          <span className="text-xs font-medium text-muted-foreground">
                                            Параметры ({(query.params || []).length})
                                          </span>
                                          <Button variant="outline" size="sm" onClick={() => addParam(qi)}>
                                            <Plus className="h-3 w-3" />
                                            Параметр
                                          </Button>
                                        </div>
                                        {(query.params || []).map((param, pi) => (
                                          <div key={`p-${qi}-${pi}`} className="rounded-lg border bg-background p-3 space-y-3">
                                            <div className="grid gap-3 md:grid-cols-2">
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
                                              <Button variant="outline" size="sm" onClick={() => removeParam(qi, pi)}>
                                                <Trash2 className="h-3.5 w-3.5" />
                                                Удалить параметр
                                              </Button>
                                            </div>
                                          </div>
                                        ))}
                                      </div>

                                      <div className="flex justify-end">
                                        <Button variant="outline" size="sm" onClick={() => removeQuery(qi)}>
                                          <Trash2 className="h-3.5 w-3.5" />
                                          Удалить запрос
                                        </Button>
                                      </div>
                                    </div>
                                  )}
                                </div>
                              )
                            })}
                          </div>
                        </TabsContent>

                        <TabsContent value="indexes" className="space-y-3">
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <h3 className="text-sm font-medium">Индексы сценария</h3>
                              <p className="text-xs text-muted-foreground">Индексы создаются на время теста согласно конфигурации сценария.</p>
                            </div>
                            <Button variant="outline" size="sm" onClick={addIndex}>
                              <Plus className="h-3.5 w-3.5" />
                              Добавить индекс
                            </Button>
                          </div>

                          {draftBundle.indexes.length === 0 && (
                            <Empty className="border p-6">
                              <EmptyHeader>
                                <EmptyTitle className="text-base">Индексы не заданы</EmptyTitle>
                                <EmptyDescription>Сценарий можно сохранить без индексов.</EmptyDescription>
                              </EmptyHeader>
                            </Empty>
                          )}

                          <div className="grid gap-3 xl:grid-cols-2">
                            {draftBundle.indexes.map((index, ip) => (
                              <div key={`idx-${ip}`} className="rounded-xl border bg-card p-4 space-y-4">
                                <div className="flex items-start justify-between gap-3">
                                  <div className="min-w-0">
                                    <div className="flex items-center gap-2">
                                      <Database className="h-4 w-4 text-primary" />
                                      <span className="truncate text-sm font-medium">
                                        {index.index_name || `Индекс ${ip + 1}`}
                                      </span>
                                    </div>
                                    <p className="mt-1 truncate text-xs text-muted-foreground">
                                      {index.table_name || "таблица не задана"} · {index.column_names || "колонки не заданы"}
                                    </p>
                                  </div>
                                  <Button variant="outline" size="icon-sm" onClick={() => removeIndex(ip)} aria-label="Удалить индекс">
                                    <Trash2 className="h-3.5 w-3.5" />
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
                        </TabsContent>
                      </Tabs>
                    </>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
