"use client"

import { useEffect, useMemo, useState } from "react"
import {
  AlertTriangle,
  ChevronDown,
  Copy,
  Database,
  FileCode2,
  Layers,
  Loader2,
  MoreHorizontal,
  Pencil,
  Plus,
  Save,
  Search,
  Trash2,
  AlertCircle,
} from "lucide-react"

import { apiClient } from "@/lib/api"
import type {
  BundleWorkloadMode,
  DatabaseGroup,
  ScenarioBundleSummary,
  ScenarioBundleSaveRequest,
  ScenarioIndex,
  ScenarioParam,
  ScenarioQuery,
  ScenarioTransaction,
  ScenarioTransactionStep,
  ScenarioTemplate,
  SchemaProfileDetail,
  SchemaProfileSummary,
} from "@/lib/types"
import { formatWorkloadModeLabel } from "@/lib/throughput-metrics"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
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
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { toast } from "sonner"

// ==================== Helpers ====================

function cloneParams(params: ScenarioParam[] = []): ScenarioParam[] {
  return params.map((param) => ({
    param_name: param.param_name,
    param_type: param.param_type,
    min_value: param.min_value ?? null,
    max_value: param.max_value ?? null,
    fixed_value: param.fixed_value ?? null,
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

function cloneTransactions(transactions: ScenarioTransaction[] = []): ScenarioTransaction[] {
  return transactions.map((transaction, index) => ({
    name: transaction.name,
    weight: transaction.weight ?? 1,
    order_index: transaction.order_index ?? index,
    description: transaction.description ?? null,
    steps: (transaction.steps || []).map((step, stepIndex) => ({
      sql_template: step.sql_template,
      query_type: step.query_type,
      order_index: step.order_index ?? stepIndex,
      description: step.description ?? null,
    })),
    params: cloneParams(transaction.params || []),
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
    workload_mode: bundle.workload_mode || "query",
    queries: cloneQueries(bundle.queries),
    transactions: cloneTransactions(bundle.transactions || []),
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

function Hint({ text }: { text: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          className="ml-1 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-muted text-[10px] font-medium text-muted-foreground transition-colors hover:bg-primary/15 hover:text-primary"
          tabIndex={-1}
        >
          ?
        </button>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-64 text-xs leading-relaxed">
        {text}
      </TooltipContent>
    </Tooltip>
  )
}

// ==================== Component ====================

export function LogicalScenariosBrowser() {
  const [templates, setTemplates] = useState<ScenarioTemplate[]>([])
  const [profiles, setProfiles] = useState<SchemaProfileSummary[]>([])
  const [databaseGroups, setDatabaseGroups] = useState<DatabaseGroup[]>([])
  const [selectedDatabaseGroupId, setSelectedDatabaseGroupId] = useState<string>("")
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>("")
  const [selectedProfileId, setSelectedProfileId] = useState<string>("")
  const [selectedProfileDetail, setSelectedProfileDetail] = useState<SchemaProfileDetail | null>(null)
  const [selectedBundleId, setSelectedBundleId] = useState<string>("new")
  const [draftBundle, setDraftBundle] = useState<ScenarioBundleSaveRequest | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingProfile, setLoadingProfile] = useState(false)
  const [saving, setSaving] = useState(false)
  const [expandedQueries, setExpandedQueries] = useState<Set<number>>(new Set())
  const [expandedTransactions, setExpandedTransactions] = useState<Set<number>>(new Set())
  const [templateSearch, setTemplateSearch] = useState("")
  const [creatingBundle, setCreatingBundle] = useState(false)
  const [templateDialog, setTemplateDialog] = useState<{
    open: boolean
    mode: "create" | "copy" | "edit"
    name: string
    description: string
    submitting: boolean
  }>({ open: false, mode: "create", name: "", description: "", submitting: false })

  const selectedTemplate = useMemo(
    () => templates.find((t) => t.id === selectedTemplateId) || null,
    [templates, selectedTemplateId]
  )

  const selectedDatabaseGroup = useMemo(
    () => databaseGroups.find((db) => db.id === selectedDatabaseGroupId) || null,
    [databaseGroups, selectedDatabaseGroupId]
  )

  const variants = useMemo(() => {
    if (!selectedProfileDetail || !selectedTemplateId) return []
    return selectedProfileDetail.bundles.filter((b) => b.scenario_template_id === selectedTemplateId)
  }, [selectedProfileDetail, selectedTemplateId])

  const selectedLogicalDbBlocksBundles = Boolean(
    selectedDatabaseGroup &&
    (
      ["draft", "needs_review", "incompatible"].includes(selectedDatabaseGroup.profile_status || "") ||
      selectedDatabaseGroup.compatibility_status === "invalid"
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
      const [templatesResp, profilesResp, databaseGroupResp] = await Promise.all([
        apiClient.getScenarioTemplates(),
        apiClient.getSchemaProfiles(),
        apiClient.getDatabaseGroups(),
      ])
      const nextTemplates = templatesResp.templates
      const nextProfiles = profilesResp.profiles
      const nextDatabaseGroups = databaseGroupResp.groups
      setTemplates(nextTemplates)
      setProfiles(nextProfiles)
      setDatabaseGroups(nextDatabaseGroups)

      const nextTemplateId = preferredTemplateId || nextTemplates[0]?.id || ""
      // Prefer explicit arg → current selection → first available logical DB → empty
      const nextLogicalDbId =
        preferredLogicalDbId !== undefined
          ? preferredLogicalDbId
          : selectedDatabaseGroupId || nextDatabaseGroups[0]?.id || ""
      const logicalDbProfileId = nextDatabaseGroups.find((db) => db.id === nextLogicalDbId)?.schema_profile_id
      // Profile comes from logical DB if bound; otherwise fall back to explicit arg or first profile
      const nextProfileId = logicalDbProfileId || preferredProfileId || nextProfiles[0]?.id || ""
      setSelectedTemplateId(nextTemplateId)
      setSelectedDatabaseGroupId(nextLogicalDbId)
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
    setExpandedTransactions(new Set())
    syncEditorState(selectedProfileDetail, templateId)
  }

  const handleProfileChange = async (profileId: string) => {
    setSelectedProfileId(profileId)
    await loadProfile(profileId, selectedTemplateId)
  }

  const handleDatabaseGroupChange = async (databaseGroupId: string) => {
    const nextId = databaseGroupId
    setSelectedDatabaseGroupId(nextId)
    const db = databaseGroups.find((d) => d.id === nextId)
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

  const updateTransaction = (ti: number, patch: Partial<ScenarioTransaction>) => {
    updateDraftBundle((cur) => ({
      ...cur,
      transactions: (cur.transactions || []).map((tx, i) => (i === ti ? { ...tx, ...patch } : tx)),
    }))
  }

  const addTransaction = () => {
    updateDraftBundle((cur) => ({
      ...cur,
      transactions: [
        ...(cur.transactions || []),
        {
          name: `Транзакция ${(cur.transactions?.length || 0) + 1}`,
          weight: 1,
          order_index: cur.transactions?.length || 0,
          description: "",
          steps: [{ sql_template: "", query_type: "select", order_index: 0, description: "" }],
          params: [],
        },
      ],
    }))
    setExpandedTransactions((prev) => {
      const next = new Set(prev)
      next.add(draftBundle?.transactions?.length ?? 0)
      return next
    })
  }

  const removeTransaction = (ti: number) => {
    updateDraftBundle((cur) => ({
      ...cur,
      transactions: (cur.transactions || [])
        .filter((_, i) => i !== ti)
        .map((tx, i) => ({ ...tx, order_index: i })),
    }))
    setExpandedTransactions((prev) => {
      const next = new Set<number>()
      prev.forEach((idx) => {
        if (idx < ti) next.add(idx)
        else if (idx > ti) next.add(idx - 1)
      })
      return next
    })
  }

  const updateTransactionStep = (ti: number, si: number, patch: Partial<ScenarioTransactionStep>) => {
    updateDraftBundle((cur) => ({
      ...cur,
      transactions: (cur.transactions || []).map((tx, i) =>
        i === ti
          ? {
              ...tx,
              steps: tx.steps.map((step, j) => (j === si ? { ...step, ...patch } : step)),
            }
          : tx,
      ),
    }))
  }

  const addTransactionStep = (ti: number) => {
    updateDraftBundle((cur) => ({
      ...cur,
      transactions: (cur.transactions || []).map((tx, i) =>
        i === ti
          ? {
              ...tx,
              steps: [
                ...tx.steps,
                {
                  sql_template: "",
                  query_type: "select",
                  order_index: tx.steps.length,
                  description: "",
                },
              ],
            }
          : tx,
      ),
    }))
  }

  const removeTransactionStep = (ti: number, si: number) => {
    updateDraftBundle((cur) => ({
      ...cur,
      transactions: (cur.transactions || []).map((tx, i) =>
        i === ti
          ? {
              ...tx,
              steps: tx.steps
                .filter((_, j) => j !== si)
                .map((step, j) => ({ ...step, order_index: j })),
            }
          : tx,
      ),
    }))
  }

  const addTransactionParam = (ti: number) => {
    updateDraftBundle((cur) => ({
      ...cur,
      transactions: (cur.transactions || []).map((tx, i) =>
        i === ti
          ? {
              ...tx,
              params: [
                ...tx.params,
                {
                  param_name: "",
                  param_type: "random_int",
                  min_value: 1,
                  max_value: 1000,
                  fixed_value: null,
                  table_ref: null,
                  column_ref: null,
                  string_length: null,
                  current_value: 0,
                  step: 1,
                },
              ],
            }
          : tx,
      ),
    }))
  }

  const updateTransactionParam = (ti: number, pi: number, patch: Partial<ScenarioParam>) => {
    updateDraftBundle((cur) => ({
      ...cur,
      transactions: (cur.transactions || []).map((tx, i) =>
        i === ti
          ? {
              ...tx,
              params: tx.params.map((param, j) => (j === pi ? { ...param, ...patch } : param)),
            }
          : tx,
      ),
    }))
  }

  const removeTransactionParam = (ti: number, pi: number) => {
    updateDraftBundle((cur) => ({
      ...cur,
      transactions: (cur.transactions || []).map((tx, i) =>
        i === ti
          ? {
              ...tx,
              params: tx.params.filter((_, j) => j !== pi),
            }
          : tx,
      ),
    }))
  }

  const toggleTransactionExpanded = (ti: number) => {
    setExpandedTransactions((prev) => {
      const next = new Set(prev)
      if (next.has(ti)) next.delete(ti)
      else next.add(ti)
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
                { param_name: "", param_type: "random_int", min_value: 1, max_value: 1000, fixed_value: null, table_ref: null, column_ref: null, string_length: null, current_value: 0, step: 1 },
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

  const openTemplateDialog = (mode: "create" | "copy" | "edit") => {
    setTemplateDialog({
      open: true,
      mode,
      name:
        mode === "create" ? "" :
        mode === "copy" ? `Копия: ${selectedTemplate?.name ?? ""}` :
        selectedTemplate?.name ?? "",
      description:
        mode === "create" ? "" :
        selectedTemplate?.description ?? "",
      submitting: false,
    })
  }

  const closeTemplateDialog = () =>
    setTemplateDialog((s) => ({ ...s, open: false, submitting: false }))

  const handleSubmitTemplateDialog = async () => {
    const { mode, name, description } = templateDialog
    if (!name.trim()) return
    setTemplateDialog((s) => ({ ...s, submitting: true }))
    try {
      if (mode === "create") {
        const template = await apiClient.createScenarioTemplate({
          name: name.trim(),
          description: description.trim(),
        }) as ScenarioTemplate
        toast.success("Шаблон создан")
        closeTemplateDialog()
        await reloadAll(template.id, selectedProfileId)
      } else if (mode === "copy") {
        const template = await apiClient.createScenarioTemplate({
          name: name.trim(),
          description: description.trim(),
        }) as ScenarioTemplate

        // Если в текущем профиле есть активный bundle — копируем его содержимое
        if (selectedBundle && selectedProfileId) {
          const bundleData = bundleToDraft(selectedBundle)
          await apiClient.createBundleVariant(selectedProfileId, {
            ...bundleData,
            scenario_template_id: template.id,
            name: bundleData.name,
            is_active: true,
          })
          toast.success("Шаблон и bundle скопированы")
        } else {
          toast.success("Шаблон скопирован")
        }

        closeTemplateDialog()
        await reloadAll(template.id, selectedProfileId)
      } else {
        if (!selectedTemplate) return
        await apiClient.updateScenarioTemplate(selectedTemplate.id, {
          name: name.trim(),
          description: description.trim(),
        })
        toast.success("Шаблон обновлён")
        closeTemplateDialog()
        await reloadAll(
          selectedTemplate.id,
          selectedProfileId,
          selectedBundleId === "new" ? undefined : selectedBundleId
        )
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Не удалось сохранить шаблон")
      setTemplateDialog((s) => ({ ...s, submitting: false }))
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
    const isTransactionBundle = draftBundle.workload_mode === "transaction"
    if (isTransactionBundle) {
      if (!draftBundle.transactions?.length) {
        toast.error("Добавьте хотя бы одну транзакцию")
        return
      }
      for (const tx of draftBundle.transactions) {
        if (!tx.steps.length) {
          toast.error(`Транзакция «${tx.name}» должна содержать хотя бы один шаг SQL`)
          return
        }
        const names = tx.params.map((param) => param.param_name).filter(Boolean)
        if (names.length !== new Set(names).size) {
          toast.error(`Транзакция «${tx.name}»: дублирующиеся param_name`)
          return
        }
        for (const param of tx.params) {
          if (param.param_type === "fixed") {
            if (!param.fixed_value?.trim()) {
              toast.error(
                `Транзакция «${tx.name}»: для параметра «${param.param_name || "?"}» укажите фиксированное значение`,
              )
              return
            }
            continue
          }
          if (param.param_type !== "random_from_table") continue
          if (!param.table_ref?.trim() || !param.column_ref?.trim()) {
            toast.error(
              `Транзакция «${tx.name}»: для параметра «${param.param_name || "?"}» укажите таблицу и колонку`,
            )
            return
          }
        }
      }
    } else if (draftBundle.queries.length === 0) {
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

  const handleCreateBundle = async (workloadMode: BundleWorkloadMode = "query") => {
    if (!selectedProfileId || !selectedTemplateId) return
    setCreatingBundle(true)
    try {
      const isTransaction = workloadMode === "transaction"
      const created = await apiClient.createBundleVariant(selectedProfileId, {
        scenario_template_id: selectedTemplateId,
        name: isTransaction ? "Transaction bundle 1" : "Bundle 1",
        description: "",
        generation_source: "manual_variant",
        is_active: true,
        workload_mode: workloadMode,
        queries: isTransaction ? [] : [],
        transactions: isTransaction
          ? [{
              name: "Транзакция 1",
              weight: 1,
              order_index: 0,
              description: "",
              steps: [],
              params: [],
            }]
          : [],
        indexes: [],
      })
      toast.success(
        isTransaction
          ? "Транзакционный bundle создан — настройте шаги и сохраните"
          : "SQL bundle создан — добавьте запросы и сохраните",
      )
      await loadProfile(selectedProfileId, selectedTemplateId, created.id)
      if (isTransaction) {
        setExpandedTransactions(new Set([0]))
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Не удалось создать bundle")
    } finally {
      setCreatingBundle(false)
    }
  }

  // ==================== Render ====================

  const profileName = selectedDatabaseGroup?.schema_profile_name || selectedProfileDetail?.name || null
  const bundleSubtitle = draftBundle
    ? `${draftBundle.name} · ${formatWorkloadModeLabel(draftBundle.workload_mode)} · ${draftBundle.generation_source || "manual"}`
    : null

  if (loading) {
    return (
      <div className="flex h-[calc(100vh-3.5rem)] items-center justify-center p-6">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin" />
          <p className="text-sm">Загружаем сценарии...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-background">
      {/* ===== Sticky header (comparison-page style) ===== */}
      <header className="sticky top-0 z-30 border-b border-border bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto flex max-w-[1400px] flex-col gap-3 px-4 py-3 md:flex-row md:items-center md:justify-between md:px-6">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Layers className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-base font-semibold leading-none tracking-tight md:text-lg">
                  Сценарии тестирования
                </h1>
                {selectedTemplate && (
                  <Badge variant="secondary" className="text-[10px] uppercase tracking-wider">
                    {selectedTemplate.is_builtin ? "builtin" : "custom"}
                  </Badge>
                )}
              </div>
              <p className="mt-0.5 truncate text-xs text-muted-foreground">
                {selectedTemplate
                  ? `${selectedTemplate.name}${bundleSubtitle ? ` — ${bundleSubtitle}` : ""}`
                  : "Выберите шаблон из списка слева"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {selectedTemplate && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm">
                    <MoreHorizontal className="mr-2 h-3.5 w-3.5" />
                    Шаблон
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuLabel>Управление шаблоном</DropdownMenuLabel>
                  <DropdownMenuItem onSelect={() => openTemplateDialog("copy")}>
                    <Copy className="h-4 w-4" />
                    Скопировать шаблон
                  </DropdownMenuItem>
                  {!selectedTemplate.is_builtin && (
                    <>
                      <DropdownMenuItem onSelect={() => openTemplateDialog("edit")}>
                        <Pencil className="h-4 w-4" />
                        Переименовать
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem variant="destructive" onSelect={handleDeleteTemplate}>
                        <Trash2 className="h-4 w-4" />
                        Удалить
                      </DropdownMenuItem>
                    </>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            )}

            {draftBundle && selectedBundle && (
              <Button size="sm" disabled={saving} onClick={handleSaveBundle}>
                {saving ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : <Save className="mr-2 h-3.5 w-3.5" />}
                Сохранить
              </Button>
            )}

            <Button size="sm" onClick={() => openTemplateDialog("create")}>
              <Plus className="mr-2 h-3.5 w-3.5" />
              Новый шаблон
            </Button>
          </div>
        </div>
      </header>

      {/* ===== Main grid ===== */}
      <div className="mx-auto max-w-[1400px] px-4 py-5 md:px-6">
        <div className="grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)]">
          {/* --- Left sidebar: template list --- */}
          <Card className="overflow-hidden lg:sticky lg:top-16 lg:max-h-[calc(100vh-5rem)]">
            <CardHeader className="space-y-3 pb-3">
              <CardTitle className="text-sm font-medium">Шаблоны сценариев</CardTitle>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={templateSearch}
                  onChange={(e) => setTemplateSearch(e.target.value)}
                  placeholder="Поиск..."
                  className="h-8 pl-9 text-xs"
                />
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <ScrollArea className="h-[calc(100vh-200px)] min-h-[320px]">
                <div className="space-y-1 px-2 pb-2">
                  {filteredTemplates.map((template, index) => {
                    const isSelected = selectedTemplateId === template.id
                    const accent = TEMPLATE_ACCENTS[index % TEMPLATE_ACCENTS.length]
                    return (
                      <button
                        key={template.id}
                        onClick={() => void handleTemplateChange(template.id)}
                        className={cn(
                          "group w-full rounded-lg border p-2.5 text-left transition-all",
                          isSelected
                            ? "border-primary/50 bg-primary/10 shadow-sm"
                            : "border-transparent hover:border-border hover:bg-muted/40"
                        )}
                      >
                        <div className="flex items-start gap-2.5">
                          <div className={cn("mt-0.5 rounded-md bg-gradient-to-br p-1.5", accent)}>
                            <Layers className="h-3.5 w-3.5" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-1.5">
                              <span className="truncate text-sm font-medium">{template.name}</span>
                              {template.is_builtin && (
                                <Badge variant="secondary" className="h-4 shrink-0 px-1 text-[9px]">
                                  builtin
                                </Badge>
                              )}
                            </div>
                            <p className="mt-0.5 line-clamp-1 text-[11px] leading-relaxed text-muted-foreground">
                              {shortText(template.description, "Без описания")}
                            </p>
                          </div>
                        </div>
                      </button>
                    )
                  })}
                  {filteredTemplates.length === 0 && (
                    <div className="px-2 py-8 text-center text-xs text-muted-foreground">
                      Ничего не найдено
                    </div>
                  )}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>

          {/* --- Right panel: detail --- */}
          {!selectedTemplate ? (
            <Empty className="min-h-[520px] rounded-xl border">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <FileCode2 className="h-6 w-6" />
                </EmptyMedia>
                <EmptyTitle>Выберите шаблон сценария</EmptyTitle>
                <EmptyDescription>
                  Выбор шаблона покажет контекст выполнения, SQL-запросы и индексы.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <div className="space-y-5">
              {/* -- Template hero -- */}
              <div className="flex items-start gap-4 rounded-xl border border-primary/15 bg-gradient-to-br from-primary/8 via-card to-card p-5">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-primary">
                  <Layers className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline gap-2">
                    <h2 className="text-lg font-semibold leading-tight tracking-tight">
                      {selectedTemplate.name}
                    </h2>
                    <Badge
                      variant={selectedTemplate.is_builtin ? "secondary" : "outline"}
                      className="text-[11px]"
                    >
                      {selectedTemplate.is_builtin ? "Встроенный" : "Пользовательский"}
                    </Badge>
                  </div>
                  {selectedTemplate.description ? (
                    <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                      {selectedTemplate.description}
                    </p>
                  ) : (
                    <p className="mt-1.5 text-sm italic text-muted-foreground/60">
                      Описание не задано
                    </p>
                  )}
                </div>
              </div>

              {/* -- Context bar (compact) -- */}
              <div className="rounded-xl border bg-card px-4 py-3 space-y-3">
                <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  Контекст выполнения
                </p>

                <Select
                  value={selectedDatabaseGroupId || ""}
                  onValueChange={(v) => void handleDatabaseGroupChange(v)}
                >
                  <SelectTrigger className="h-10 w-full">
                    <div className="flex items-center gap-2 min-w-0">
                      <Database className="h-4 w-4 shrink-0 text-muted-foreground" />
                      <SelectValue placeholder="Выберите database group..." />
                    </div>
                  </SelectTrigger>
                  <SelectContent>
                    {databaseGroups.length === 0 ? (
                      <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                        Нет доступных database groups
                      </div>
                    ) : (
                      databaseGroups.map((db) => (
                        <SelectItem key={db.id} value={db.id}>{db.name}</SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>

                {selectedDatabaseGroup && (
                  <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs">
                    {profileName && (
                      <span className="text-muted-foreground">
                        Профиль:&nbsp;<span className="font-medium text-foreground">{profileName}</span>
                      </span>
                    )}
                    {selectedDatabaseGroup.reference_connection_name && (
                      <span className="text-muted-foreground">
                        Reference:&nbsp;<span className="font-medium text-foreground">{selectedDatabaseGroup.reference_connection_name}</span>
                      </span>
                    )}
                    <div className="ml-auto flex gap-1.5">
                      <Badge variant="outline" className={cn("text-[10px]", statusTone(selectedDatabaseGroup.profile_status))}>
                        {statusLabel(selectedDatabaseGroup.profile_status)}
                      </Badge>
                      <Badge variant="outline" className={cn("text-[10px]", statusTone(selectedDatabaseGroup.compatibility_status))}>
                        {statusLabel(selectedDatabaseGroup.compatibility_status)}
                      </Badge>
                    </div>
                  </div>
                )}

                {selectedLogicalDbBlocksBundles && (
                  <Alert variant="destructive">
                    <AlertTriangle className="h-4 w-4" />
                    <AlertDescription>
                      Database group требует подтверждения профиля или несовместима.
                    </AlertDescription>
                  </Alert>
                )}
              </div>

              {/* -- Bundle content -- */}
              {loadingProfile ? (
                <div className="flex min-h-[260px] items-center justify-center rounded-xl border text-sm text-muted-foreground">
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Загружаем...
                </div>
              ) : !selectedProfileId ? (
                <Empty className="rounded-xl border">
                  <EmptyHeader>
                    <EmptyMedia variant="icon">
                      <Database className="h-5 w-5" />
                    </EmptyMedia>
                    <EmptyTitle>Нужен профиль данных</EmptyTitle>
                    <EmptyDescription>
                      Выберите database group или профиль модели данных.
                    </EmptyDescription>
                  </EmptyHeader>
                </Empty>
              ) : !draftBundle ? (
                <div className="rounded-xl border bg-card p-8 text-center space-y-4">
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-muted">
                    <FileCode2 className="h-6 w-6 text-muted-foreground" />
                  </div>
                  <div className="space-y-1">
                    <p className="text-sm font-medium">Bundle не создан</p>
                    <p className="text-sm text-muted-foreground max-w-xs mx-auto">
                      Для шаблона <span className="font-medium text-foreground">{selectedTemplate.name}</span> в этом профиле ещё нет bundle с SQL-запросами и индексами.
                    </p>
                  </div>
                  <div className="flex flex-wrap justify-center gap-2">
                    <Button
                      onClick={() => handleCreateBundle("query")}
                      disabled={creatingBundle || !selectedProfileId}
                    >
                      {creatingBundle
                        ? <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        : <Plus className="mr-2 h-4 w-4" />}
                      SQL bundle
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => handleCreateBundle("transaction")}
                      disabled={creatingBundle || !selectedProfileId}
                    >
                      {creatingBundle
                        ? <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        : <Plus className="mr-2 h-4 w-4" />}
                      Транзакционный bundle
                    </Button>
                  </div>
                </div>
              ) : (
                <Tabs
                  defaultValue={draftBundle.workload_mode === "transaction" ? "transactions" : "queries"}
                  className="space-y-4"
                >
                  <TabsList className="h-auto w-full justify-start overflow-x-auto rounded-lg border border-border bg-card p-1">
                    {draftBundle.workload_mode !== "transaction" && (
                    <TabsTrigger
                      value="queries"
                      className="gap-2 px-3 py-1.5 text-sm data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm"
                    >
                      <FileCode2 className="h-3.5 w-3.5" />
                      SQL-запросы
                      <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-[10px] data-[state=active]:bg-primary-foreground/20">{draftBundle.queries.length}</Badge>
                    </TabsTrigger>
                    )}
                    {draftBundle.workload_mode === "transaction" && (
                    <TabsTrigger
                      value="transactions"
                      className="gap-2 px-3 py-1.5 text-sm data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm"
                    >
                      <Layers className="h-3.5 w-3.5" />
                      Транзакции
                      <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-[10px] data-[state=active]:bg-primary-foreground/20">{draftBundle.transactions?.length ?? 0}</Badge>
                    </TabsTrigger>
                    )}
                    <TabsTrigger
                      value="indexes"
                      className="gap-2 px-3 py-1.5 text-sm data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm"
                    >
                      <Database className="h-3.5 w-3.5" />
                      Индексы
                      <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-[10px]">{draftBundle.indexes.length}</Badge>
                    </TabsTrigger>
                    <TabsTrigger
                      value="info"
                      className="gap-2 px-3 py-1.5 text-sm data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm"
                    >
                      Описание
                    </TabsTrigger>
                  </TabsList>

                  {draftBundle.workload_mode === "transaction" && (
                  <TabsContent value="transactions" className="space-y-3 focus-visible:outline-none">
                    <div className="flex items-center justify-between">
                      <p className="text-xs text-muted-foreground">
                        Параметры общие для всех шагов одного выполнения транзакции
                      </p>
                      <Button variant="outline" size="sm" onClick={addTransaction}>
                        <Plus className="h-3.5 w-3.5" />
                        Добавить транзакцию
                      </Button>
                    </div>
                    {(draftBundle.transactions || []).length === 0 && (
                      <Empty className="border p-6">
                        <EmptyHeader>
                          <EmptyTitle className="text-base">Нет транзакций</EmptyTitle>
                          <EmptyDescription>Добавьте хотя бы одну транзакцию с шагами SQL.</EmptyDescription>
                        </EmptyHeader>
                      </Empty>
                    )}
                    <div className="space-y-3">
                      {(draftBundle.transactions || []).map((transaction, ti) => {
                        const isExpanded = expandedTransactions.has(ti)
                        return (
                          <div key={`tx-${ti}`} className="overflow-hidden rounded-xl border bg-card">
                            <button
                              type="button"
                              className="w-full px-4 py-3 text-left transition-colors hover:bg-muted/30"
                              onClick={() => toggleTransactionExpanded(ti)}
                            >
                              <div className="flex items-center justify-between gap-3">
                                <div className="min-w-0">
                                  <p className="font-medium text-foreground">{transaction.name || `Транзакция ${ti + 1}`}</p>
                                  <p className="text-xs text-muted-foreground">
                                    {transaction.steps.length} шаг(ов) · вес {transaction.weight ?? 1}
                                  </p>
                                </div>
                                <ChevronDown className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform", isExpanded && "rotate-180")} />
                              </div>
                            </button>
                            {isExpanded && (
                              <div className="space-y-4 border-t px-4 py-4">
                                <div className="grid gap-3 sm:grid-cols-2">
                                  <div className="space-y-1">
                                    <Label>Название</Label>
                                    <Input value={transaction.name} onChange={(e) => updateTransaction(ti, { name: e.target.value })} />
                                  </div>
                                  <div className="space-y-1">
                                    <Label>Вес</Label>
                                    <Input type="number" min={1} value={transaction.weight ?? 1} onChange={(e) => updateTransaction(ti, { weight: Number(e.target.value) || 1 })} />
                                  </div>
                                </div>
                                <div className="space-y-2">
                                  <div className="flex items-center justify-between">
                                    <Label>Шаги SQL</Label>
                                    <Button variant="outline" size="sm" onClick={() => addTransactionStep(ti)}>
                                      <Plus className="h-3.5 w-3.5" />
                                      Шаг
                                    </Button>
                                  </div>
                                  {transaction.steps.map((step, si) => (
                                    <div key={`tx-${ti}-step-${si}`} className="space-y-2 rounded-lg border p-3">
                                      <div className="flex flex-wrap gap-2">
                                        <Select value={step.query_type} onValueChange={(value) => updateTransactionStep(ti, si, { query_type: value })}>
                                          <SelectTrigger className="h-8 w-28"><SelectValue /></SelectTrigger>
                                          <SelectContent>
                                            <SelectItem value="select">select</SelectItem>
                                            <SelectItem value="insert">insert</SelectItem>
                                            <SelectItem value="update">update</SelectItem>
                                            <SelectItem value="delete">delete</SelectItem>
                                          </SelectContent>
                                        </Select>
                                        <Button variant="ghost" size="sm" className="text-destructive" onClick={() => removeTransactionStep(ti, si)}>
                                          <Trash2 className="h-3.5 w-3.5" />
                                        </Button>
                                      </div>
                                      <Textarea
                                        className="font-mono text-xs min-h-[80px]"
                                        value={step.sql_template}
                                        onChange={(e) => updateTransactionStep(ti, si, { sql_template: e.target.value })}
                                        placeholder="SQL шага; плейсхолдеры {param}"
                                      />
                                    </div>
                                  ))}
                                </div>
                                <div className="space-y-2">
                                  <div className="flex items-center justify-between">
                                    <Label>Параметры (transaction-scoped)</Label>
                                    <Button variant="outline" size="sm" onClick={() => addTransactionParam(ti)}>
                                      <Plus className="h-3.5 w-3.5" />
                                      Параметр
                                    </Button>
                                  </div>
                                  {transaction.params.map((param, pi) => (
                                    <div key={`tx-${ti}-param-${pi}`} className="flex items-start gap-3 rounded-lg border bg-background px-3 py-2.5">
                                      <span className="mt-1.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted text-[10px] font-medium text-muted-foreground">
                                        {pi + 1}
                                      </span>
                                      <div className="min-w-0 flex-1 space-y-2">
                                        <div className="grid grid-cols-[1fr_9rem] gap-2">
                                          <div className="space-y-1">
                                            <Label className="text-[11px] text-muted-foreground leading-none">Имя</Label>
                                            <Input
                                              className="h-7 text-xs font-mono"
                                              placeholder="customer_id"
                                              value={param.param_name}
                                              onChange={(e) => updateTransactionParam(ti, pi, { param_name: e.target.value })}
                                            />
                                          </div>
                                          <div className="space-y-1">
                                            <Label className="text-[11px] text-muted-foreground leading-none">Тип</Label>
                                            <Select
                                              value={param.param_type}
                                              onValueChange={(value) => updateTransactionParam(ti, pi, { param_type: value })}
                                            >
                                              <SelectTrigger className="h-7 text-xs"><SelectValue /></SelectTrigger>
                                              <SelectContent>
                                                <SelectItem value="random_int">random_int</SelectItem>
                                                <SelectItem value="random_string">random_string</SelectItem>
                                                <SelectItem value="random_from_table">random_from_table</SelectItem>
                                                <SelectItem value="random_date">random_date</SelectItem>
                                                <SelectItem value="sequential_int">sequential_int</SelectItem>
                                                <SelectItem value="uuid">uuid</SelectItem>
                                                <SelectItem value="fixed">fixed</SelectItem>
                                              </SelectContent>
                                            </Select>
                                          </div>
                                        </div>
                                        {param.param_type === "random_int" && (
                                          <div className="grid grid-cols-2 gap-2">
                                            <div className="space-y-1">
                                              <Label className="text-[11px] text-muted-foreground leading-none">Min</Label>
                                              <Input
                                                className="h-7 text-xs"
                                                type="number"
                                                placeholder="1"
                                                value={param.min_value ?? ""}
                                                onChange={(e) =>
                                                  updateTransactionParam(ti, pi, {
                                                    min_value: e.target.value === "" ? null : Number(e.target.value),
                                                  })
                                                }
                                              />
                                            </div>
                                            <div className="space-y-1">
                                              <Label className="text-[11px] text-muted-foreground leading-none">Max</Label>
                                              <Input
                                                className="h-7 text-xs"
                                                type="number"
                                                placeholder="1000"
                                                value={param.max_value ?? ""}
                                                onChange={(e) =>
                                                  updateTransactionParam(ti, pi, {
                                                    max_value: e.target.value === "" ? null : Number(e.target.value),
                                                  })
                                                }
                                              />
                                            </div>
                                          </div>
                                        )}
                                        {param.param_type === "random_string" && (
                                          <div className="w-32 space-y-1">
                                            <Label className="text-[11px] text-muted-foreground leading-none">Длина</Label>
                                            <Input
                                              className="h-7 text-xs"
                                              type="number"
                                              placeholder="10"
                                              value={param.string_length ?? ""}
                                              onChange={(e) =>
                                                updateTransactionParam(ti, pi, {
                                                  string_length: e.target.value === "" ? null : Number(e.target.value),
                                                })
                                              }
                                            />
                                          </div>
                                        )}
                                        {param.param_type === "random_from_table" && (
                                          <div className="grid grid-cols-2 gap-2">
                                            <div className="space-y-1">
                                              <Label className="text-[11px] text-muted-foreground leading-none">Таблица</Label>
                                              <Input
                                                className="h-7 text-xs font-mono"
                                                placeholder="customer"
                                                value={param.table_ref ?? ""}
                                                onChange={(e) =>
                                                  updateTransactionParam(ti, pi, { table_ref: e.target.value || null })
                                                }
                                              />
                                            </div>
                                            <div className="space-y-1">
                                              <Label className="text-[11px] text-muted-foreground leading-none">Колонка</Label>
                                              <Input
                                                className="h-7 text-xs font-mono"
                                                placeholder="customer_id"
                                                value={param.column_ref ?? ""}
                                                onChange={(e) =>
                                                  updateTransactionParam(ti, pi, { column_ref: e.target.value || null })
                                                }
                                              />
                                            </div>
                                          </div>
                                        )}
                                        {param.param_type === "fixed" && (
                                          <div className="space-y-1">
                                            <Label className="text-[11px] text-muted-foreground leading-none">Значение</Label>
                                            <Input
                                              className="h-7 text-xs"
                                              placeholder="42"
                                              value={param.fixed_value ?? ""}
                                              onChange={(e) =>
                                                updateTransactionParam(ti, pi, { fixed_value: e.target.value || null })
                                              }
                                            />
                                          </div>
                                        )}
                                        {["sequential_int", "uuid", "random_date"].includes(param.param_type) && (
                                          <p className="text-[11px] italic text-muted-foreground/70">
                                            Значение генерируется автоматически при каждом выполнении транзакции.
                                          </p>
                                        )}
                                      </div>
                                      <Button
                                        variant="ghost"
                                        size="icon-sm"
                                        className="shrink-0 self-center text-muted-foreground hover:text-destructive"
                                        onClick={() => removeTransactionParam(ti, pi)}
                                      >
                                        <Trash2 className="h-3.5 w-3.5" />
                                      </Button>
                                    </div>
                                  ))}
                                </div>
                                <Button variant="ghost" size="sm" className="text-destructive" onClick={() => removeTransaction(ti)}>
                                  <Trash2 className="mr-1 h-3 w-3" />
                                  Удалить транзакцию
                                </Button>
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </TabsContent>
                  )}

                  {/* === Queries tab === */}
                  {draftBundle.workload_mode !== "transaction" && (
                  <TabsContent value="queries" className="space-y-3 focus-visible:outline-none">
                    <div className="flex items-center justify-between">
                      <p className="text-xs text-muted-foreground">Разверните запрос для редактирования SQL-шаблона и параметров</p>
                      <Button variant="outline" size="sm" onClick={addQuery}>
                        <Plus className="h-3.5 w-3.5" />
                        Добавить
                      </Button>
                    </div>

                    {draftBundle.queries.length === 0 && (
                      <Empty className="border p-6">
                        <EmptyHeader>
                          <EmptyTitle className="text-base">Нет SQL-запросов</EmptyTitle>
                          <EmptyDescription>Добавьте хотя бы один запрос.</EmptyDescription>
                        </EmptyHeader>
                      </Empty>
                    )}

                    <div className="space-y-2">
                      {draftBundle.queries.map((query, qi) => {
                        const isExpanded = expandedQueries.has(qi)
                        const preview = query.description || (query.sql_template ? query.sql_template.slice(0, 100) : "")
                        return (
                          <div key={`q-${qi}`} className="overflow-hidden rounded-xl border bg-card">
                            <button
                              className="w-full px-4 py-3 text-left transition-colors hover:bg-muted/30"
                              onClick={() => toggleQueryExpanded(qi)}
                            >
                              <div className="flex items-center justify-between gap-3">
                                <div className="flex items-center gap-3 min-w-0">
                                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-[11px] font-medium text-primary-foreground">{qi + 1}</span>
                                  <Badge variant="outline" className="shrink-0 uppercase text-[10px]">{query.query_type || "select"}</Badge>
                                  <span className="truncate text-sm text-muted-foreground">
                                    {preview || "Без описания"}
                                  </span>
                                </div>
                                <div className="flex items-center gap-2 shrink-0">
                                  <span className="hidden text-[11px] text-muted-foreground sm:inline">вес {query.weight}</span>
                                  <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition-transform", isExpanded && "rotate-180")} />
                                </div>
                              </div>
                            </button>

                            {isExpanded && (
                              <div className="border-t bg-muted/5 p-4 space-y-4">
                                <div className="space-y-1.5">
                                  <Label className="text-xs flex items-center">
                                    SQL-шаблон
                                    <Hint text="SQL-запрос, исполняемый при тестировании. Параметры задаются через {param_name} и подставляются автоматически." />
                                  </Label>
                                  <Textarea
                                    className="min-h-[120px] font-mono text-xs leading-relaxed"
                                    placeholder="SELECT * FROM orders WHERE id = {order_id}"
                                    value={query.sql_template}
                                    onChange={(e) => updateQuery(qi, { sql_template: e.target.value })}
                                  />
                                </div>

                                <div className="grid gap-3 sm:grid-cols-3">
                                  <div className="space-y-1.5">
                                    <Label className="text-xs flex items-center">
                                      Тип
                                      <Hint text="Категория запроса: select, insert, update, delete. Используется валидатором для проверки write-запросов и в отчётах." />
                                    </Label>
                                    <Input value={query.query_type} onChange={(e) => updateQuery(qi, { query_type: e.target.value })} />
                                  </div>
                                  <div className="space-y-1.5">
                                    <Label className="text-xs flex items-center">
                                      Вес
                                      <Hint text="Чем больше вес, тем чаще запрос попадает в нагрузочный микс. Вес 3 = запрос выпадает в 3 раза чаще, чем с весом 1." />
                                    </Label>
                                    <Input type="number" min={1} value={query.weight} onChange={(e) => updateQuery(qi, { weight: Number(e.target.value) || 1 })} />
                                  </div>
                                  <div className="space-y-1.5">
                                    <Label className="text-xs flex items-center">
                                      Порядок
                                      <Hint text="Порядок отображения запроса в списке. На выполнение не влияет — при тестировании запросы выбираются случайно по весу." />
                                    </Label>
                                    <Input type="number" min={0} value={query.order_index} onChange={(e) => updateQuery(qi, { order_index: Number(e.target.value) || 0 })} />
                                  </div>
                                </div>

                                <div className="space-y-1.5">
                                  <Label className="text-xs flex items-center">
                                    Описание
                                    <Hint text="Пояснение к запросу для удобства чтения. Отображается в списке и в отчётах сравнения." />
                                  </Label>
                                  <Input placeholder="Выборка заказов по дате с агрегацией..." value={query.description || ""} onChange={(e) => updateQuery(qi, { description: e.target.value })} />
                                </div>

                                <Separator />

                                <div className="space-y-3">
                                  <div className="flex items-center justify-between">
                                    <span className="text-xs font-medium text-muted-foreground flex items-center">
                                      Параметры ({(query.params || []).length})
                                      <Hint text="Параметры подставляются в {плейсхолдеры} SQL-шаблона. Каждый параметр генерируется автоматически по заданному типу." />
                                    </span>
                                    <Button variant="outline" size="sm" onClick={() => addParam(qi)}>
                                      <Plus className="h-3 w-3" />
                                      Параметр
                                    </Button>
                                  </div>
                                  {(query.params || []).map((param, pi) => (
                                        <div key={`p-${qi}-${pi}`} className="flex items-start gap-3 rounded-lg border bg-background px-3 py-2.5">
                                          {/* Порядковый номер */}
                                          <span className="mt-1.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted text-[10px] font-medium text-muted-foreground">
                                            {pi + 1}
                                          </span>

                                          {/* Основная часть */}
                                          <div className="min-w-0 flex-1 space-y-2">
                                            {/* Строка 1: Имя (flex-1) + Тип (фикс 9rem) */}
                                            <div className="grid grid-cols-[1fr_9rem] gap-2">
                                              <div className="space-y-1">
                                                <Label className="text-[11px] flex items-center text-muted-foreground leading-none">
                                                  Имя <Hint text="Совпадает с {плейсхолдером} в SQL. Например WHERE id = {order_id} → имя: order_id." />
                                                </Label>
                                                <Input
                                                  className="h-7 text-xs font-mono"
                                                  placeholder="param_name"
                                                  value={param.param_name}
                                                  onChange={(e) => updateParam(qi, pi, { param_name: e.target.value })}
                                                />
                                              </div>
                                              <div className="space-y-1">
                                                <Label className="text-[11px] flex items-center text-muted-foreground leading-none">
                                                  Тип <Hint text="Способ генерации значения при каждом запросе." />
                                                </Label>
                                                <Select value={param.param_type} onValueChange={(v) => updateParam(qi, pi, { param_type: v })}>
                                                  <SelectTrigger className="h-7 text-xs"><SelectValue /></SelectTrigger>
                                                  <SelectContent>
                                                    <SelectItem value="random_int">random_int</SelectItem>
                                                    <SelectItem value="random_string">random_string</SelectItem>
                                                    <SelectItem value="random_from_table">random_from_table</SelectItem>
                                                    <SelectItem value="random_date">random_date</SelectItem>
                                                    <SelectItem value="sequential_int">sequential_int</SelectItem>
                                                    <SelectItem value="uuid">uuid</SelectItem>
                                                    <SelectItem value="fixed">fixed</SelectItem>
                                                  </SelectContent>
                                                </Select>
                                              </div>
                                            </div>

                                            {/* Строка 2: доп. поля для выбранного типа */}
                                            {param.param_type === "random_int" && (
                                              <div className="grid grid-cols-2 gap-2">
                                                <div className="space-y-1">
                                                  <Label className="text-[11px] flex items-center text-muted-foreground leading-none">Min <Hint text="Нижняя граница случайного числа. По умолчанию 1." /></Label>
                                                  <Input className="h-7 text-xs" type="number" placeholder="1" value={param.min_value ?? ""} onChange={(e) => updateParam(qi, pi, { min_value: e.target.value === "" ? null : Number(e.target.value) })} />
                                                </div>
                                                <div className="space-y-1">
                                                  <Label className="text-[11px] flex items-center text-muted-foreground leading-none">Max <Hint text="Верхняя граница случайного числа. По умолчанию 1000." /></Label>
                                                  <Input className="h-7 text-xs" type="number" placeholder="1000" value={param.max_value ?? ""} onChange={(e) => updateParam(qi, pi, { max_value: e.target.value === "" ? null : Number(e.target.value) })} />
                                                </div>
                                              </div>
                                            )}
                                            {param.param_type === "random_string" && (
                                              <div className="w-32 space-y-1">
                                                <Label className="text-[11px] flex items-center text-muted-foreground leading-none">Длина <Hint text="Кол-во символов (латиница + цифры). По умолчанию 10." /></Label>
                                                <Input className="h-7 text-xs" type="number" placeholder="10" value={param.string_length ?? ""} onChange={(e) => updateParam(qi, pi, { string_length: e.target.value === "" ? null : Number(e.target.value) })} />
                                              </div>
                                            )}
                                            {param.param_type === "random_from_table" && (
                                              <div className="grid grid-cols-2 gap-2">
                                                <div className="space-y-1">
                                                  <Label className="text-[11px] flex items-center text-muted-foreground leading-none">Таблица <Hint text="Значения кэшируются перед тестом: SELECT column FROM table LIMIT N." /></Label>
                                                  <Input className="h-7 text-xs font-mono" placeholder="orders" value={param.table_ref ?? ""} onChange={(e) => updateParam(qi, pi, { table_ref: e.target.value || null })} />
                                                </div>
                                                <div className="space-y-1">
                                                  <Label className="text-[11px] flex items-center text-muted-foreground leading-none">Колонка <Hint text="Случайное значение из этой колонки при каждом запросе." /></Label>
                                                  <Input className="h-7 text-xs font-mono" placeholder="id" value={param.column_ref ?? ""} onChange={(e) => updateParam(qi, pi, { column_ref: e.target.value || null })} />
                                                </div>
                                              </div>
                                            )}
                                            {param.param_type === "fixed" && (
                                              <div className="space-y-1">
                                                <Label className="text-[11px] flex items-center text-muted-foreground leading-none">Значение <Hint text="Постоянное значение, подставляется в каждый запрос без изменений." /></Label>
                                                <Input className="h-7 text-xs" placeholder="42" value={param.fixed_value ?? ""} onChange={(e) => updateParam(qi, pi, { fixed_value: e.target.value || null })} />
                                              </div>
                                            )}
                                            {["sequential_int", "uuid", "random_date"].includes(param.param_type) && (
                                              <p className="text-[11px] italic text-muted-foreground/70">
                                                {param.param_type === "sequential_int" && "Автогенерация: timestamp % 100000, дополнительные поля не нужны."}
                                                {param.param_type === "uuid" && "Автогенерация: UUID v4 при каждом запросе."}
                                                {param.param_type === "random_date" && "Автогенерация: случайная дата 2000–2030 в формате YYYY-MM-DD."}
                                              </p>
                                            )}
                                          </div>

                                          {/* Кнопка удаления */}
                                          <Button variant="ghost" size="icon-sm" className="shrink-0 self-center text-muted-foreground hover:text-destructive" onClick={() => removeParam(qi, pi)}>
                                            <Trash2 className="h-3.5 w-3.5" />
                                          </Button>
                                        </div>
                                      ))}
                                  {(query.params || []).length === 0 && (
                                    <p className="text-xs text-muted-foreground py-2">
                                      Параметров нет. Если SQL содержит плейсхолдеры вида &#123;name&#125;, добавьте соответствующие параметры.
                                    </p>
                                  )}
                                </div>

                                <div className="flex justify-end border-t pt-3">
                                  <Button variant="ghost" size="sm" className="h-7 text-xs text-destructive hover:text-destructive" onClick={() => removeQuery(qi)}>
                                    <Trash2 className="mr-1 h-3 w-3" />
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
                  )}

                  {/* === Indexes tab === */}
                  <TabsContent value="indexes" className="space-y-3 focus-visible:outline-none">
                    <div className="flex items-center justify-between">
                      <p className="text-xs text-muted-foreground">Индексы создаются перед тестом и удаляются после</p>
                      <Button variant="outline" size="sm" onClick={addIndex}>
                        <Plus className="h-3.5 w-3.5" />
                        Добавить
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
                        <div key={`idx-${ip}`} className="rounded-xl border bg-card p-4 space-y-3">
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium">{index.index_name || `Индекс ${ip + 1}`}</p>
                              <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
                                {index.table_name || "таблица?"} · {index.column_names || "колонки?"} · {index.index_type}
                              </p>
                            </div>
                            <Button variant="ghost" size="icon-sm" className="text-muted-foreground hover:text-destructive" onClick={() => removeIndex(ip)}>
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                          <div className="grid gap-2 sm:grid-cols-2">
                            <div className="space-y-1">
                              <Label className="text-[11px] flex items-center">
                                Таблица
                                <Hint text="Имя таблицы, на которой создаётся индекс. Обязательное поле." />
                              </Label>
                              <Input className="h-8 text-xs" placeholder="orders" value={index.table_name} onChange={(e) => updateIndex(ip, { table_name: e.target.value })} />
                            </div>
                            <div className="space-y-1">
                              <Label className="text-[11px] flex items-center">
                                Колонки
                                <Hint text="Колонки индекса через запятую. Порядок важен для составных индексов." />
                              </Label>
                              <Input className="h-8 text-xs" placeholder="customer_id, order_date" value={index.column_names} onChange={(e) => updateIndex(ip, { column_names: e.target.value })} />
                            </div>
                            <div className="space-y-1">
                              <Label className="text-[11px] flex items-center">
                                Тип
                                <Hint text="Тип индекса: btree (по умолчанию), hash, gin, gist. Поддержка зависит от СУБД." />
                              </Label>
                              <Input className="h-8 text-xs" placeholder="btree" value={index.index_type} onChange={(e) => updateIndex(ip, { index_type: e.target.value })} />
                            </div>
                            <div className="space-y-1">
                              <Label className="text-[11px] flex items-center">
                                Имя индекса
                                <Hint text="Произвольное имя. Если пусто — генерируется автоматически: idx_loadtest_{таблица}_{колонки}." />
                              </Label>
                              <Input className="h-8 text-xs" placeholder="авто" value={index.index_name ?? ""} onChange={(e) => updateIndex(ip, { index_name: e.target.value || null })} />
                            </div>
                            <div className="space-y-1">
                              <Label className="text-[11px] flex items-center">
                                Условие
                                <Hint text="WHERE-выражение для частичного индекса. Работает только в PostgreSQL, MySQL игнорирует." />
                              </Label>
                              <Input className="h-8 text-xs" placeholder="status = 'active'" value={index.condition ?? ""} onChange={(e) => updateIndex(ip, { condition: e.target.value || null })} />
                            </div>
                            <div className="space-y-1">
                              <Label className="text-[11px] flex items-center">
                                Уникальный
                                <Hint text="Добавляет UNIQUE при создании индекса. Гарантирует уникальность значений в указанных колонках." />
                              </Label>
                              <Select value={index.is_unique ? "true" : "false"} onValueChange={(v) => updateIndex(ip, { is_unique: v === "true" })}>
                                <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="false">Нет</SelectItem>
                                  <SelectItem value="true">Да</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </TabsContent>

                  {/* === Info tab (bundle metadata) === */}
                  <TabsContent value="info" className="space-y-4 focus-visible:outline-none">
                    <div className="rounded-xl border bg-card p-4 space-y-3">
                      <h3 className="text-sm font-medium">Активный bundle</h3>
                      <div className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
                        <div>
                          <span className="text-xs text-muted-foreground">Название</span>
                          <p className="font-medium">{draftBundle.name}</p>
                        </div>
                        <div>
                          <span className="text-xs text-muted-foreground">Тип нагрузки</span>
                          <p className="font-medium">{formatWorkloadModeLabel(draftBundle.workload_mode)}</p>
                        </div>
                        <div>
                          <span className="text-xs text-muted-foreground">Источник генерации</span>
                          <p className="font-medium">{draftBundle.generation_source || "manual_variant"}</p>
                        </div>
                        <div>
                          <span className="text-xs text-muted-foreground">Статус</span>
                          <p className="font-medium">{selectedBundle?.is_active ? "Активный" : "Неактивный"}</p>
                        </div>
                        <div>
                          <span className="text-xs text-muted-foreground">Вариантов для шаблона</span>
                          <p className="font-medium">{variants.length}</p>
                        </div>
                        {draftBundle.description && (
                          <div className="sm:col-span-2">
                            <span className="text-xs text-muted-foreground">Описание</span>
                            <p className="leading-relaxed">{draftBundle.description}</p>
                          </div>
                        )}
                      </div>
                    </div>

                    {selectedProfileDetail?.description && (
                      <div className="rounded-xl border bg-card p-4 space-y-2">
                        <h3 className="text-sm font-medium">Профиль модели данных</h3>
                        <p className="text-sm leading-relaxed text-muted-foreground">{selectedProfileDetail.description}</p>
                      </div>
                    )}
                  </TabsContent>
                </Tabs>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ===== Template create / copy / edit dialog ===== */}
      <Dialog
        open={templateDialog.open}
        onOpenChange={(open) => { if (!open) closeTemplateDialog() }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>
              {templateDialog.mode === "create" && "Новый шаблон сценария"}
              {templateDialog.mode === "copy" && "Скопировать шаблон"}
              {templateDialog.mode === "edit" && "Переименовать шаблон"}
            </DialogTitle>
            <DialogDescription>
              {templateDialog.mode === "create" && "Задайте название и описание. SQL-запросы и индексы добавляются через bundle."}
              {templateDialog.mode === "copy" && "Будет создан новый шаблон с теми же метаданными. Bundles копируются отдельно через профиль данных."}
              {templateDialog.mode === "edit" && "Изменение названия и описания не затрагивает bundles и SQL-запросы."}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="tpl-name">
                Название <span className="text-destructive">*</span>
              </Label>
              <Input
                id="tpl-name"
                placeholder="Например: OLAP нагрузка с агрегациями"
                value={templateDialog.name}
                onChange={(e) => setTemplateDialog((s) => ({ ...s, name: e.target.value }))}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) void handleSubmitTemplateDialog() }}
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="tpl-desc">Описание</Label>
              <Textarea
                id="tpl-desc"
                placeholder="Кратко опишите назначение сценария..."
                rows={3}
                className="resize-none"
                value={templateDialog.description}
                onChange={(e) => setTemplateDialog((s) => ({ ...s, description: e.target.value }))}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={closeTemplateDialog}
              disabled={templateDialog.submitting}
            >
              Отмена
            </Button>
            <Button
              onClick={handleSubmitTemplateDialog}
              disabled={!templateDialog.name.trim() || templateDialog.submitting}
            >
              {templateDialog.submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {templateDialog.mode === "create" && "Создать"}
              {templateDialog.mode === "copy" && "Скопировать"}
              {templateDialog.mode === "edit" && "Сохранить"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
