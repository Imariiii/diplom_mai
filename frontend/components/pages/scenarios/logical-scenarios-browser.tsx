"use client"

import { useEffect, useMemo, useState } from "react"
import {
  Check,
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
} from "lucide-react"

import { apiClient } from "@/lib/api"
import type {
  ScenarioBundleSummary,
  ScenarioBundleSaveRequest,
  ScenarioIndex,
  ScenarioParam,
  ScenarioQuery,
  ScenarioTemplate,
  SchemaProfileDetail,
  SchemaProfileSummary,
} from "@/lib/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "sonner"

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

export function LogicalScenariosBrowser() {
  const [templates, setTemplates] = useState<ScenarioTemplate[]>([])
  const [profiles, setProfiles] = useState<SchemaProfileSummary[]>([])
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>("")
  const [selectedProfileId, setSelectedProfileId] = useState<string>("")
  const [selectedProfileDetail, setSelectedProfileDetail] = useState<SchemaProfileDetail | null>(null)
  const [selectedBundleId, setSelectedBundleId] = useState<string>("new")
  const [draftBundle, setDraftBundle] = useState<ScenarioBundleSaveRequest | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingProfile, setLoadingProfile] = useState(false)
  const [saving, setSaving] = useState(false)

  const selectedTemplate = useMemo(
    () => templates.find((template) => template.id === selectedTemplateId) || null,
    [templates, selectedTemplateId]
  )

  const variants = useMemo(() => {
    if (!selectedProfileDetail || !selectedTemplateId) return []
    return selectedProfileDetail.bundles.filter(
      (bundle) => bundle.scenario_template_id === selectedTemplateId
    )
  }, [selectedProfileDetail, selectedTemplateId])

  const activeVariant = useMemo(
    () => variants.find((bundle) => bundle.is_active) || null,
    [variants]
  )

  const selectedBundle: ScenarioBundleSummary | null = useMemo(() => {
    if (!variants.length || selectedBundleId === "new") return null
    return variants.find((bundle) => bundle.id === selectedBundleId) || null
  }, [variants, selectedBundleId])

  const buildEmptyDraft = (
    templateId: string,
    profileDetail?: SchemaProfileDetail | null,
    sourceBundle?: ScenarioBundleSummary | null
  ): ScenarioBundleSaveRequest => ({
    scenario_template_id: templateId,
    name: sourceBundle
      ? `${sourceBundle.name} (копия)`
      : `${templates.find((template) => template.id === templateId)?.name || templateId} variant`,
    description: sourceBundle?.description ?? "",
    generation_source: "manual_variant",
    generated_from_connection_id: sourceBundle?.generated_from_connection_id ?? profileDetail?.reference_connection_id ?? undefined,
    is_active: !(
      profileDetail?.bundles.some(
        (bundle) => bundle.scenario_template_id === templateId && bundle.is_active
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
      (bundle) => bundle.scenario_template_id === templateId
    )
    if (templateVariants.length === 0) {
      setSelectedBundleId("new")
      setDraftBundle(buildEmptyDraft(templateId, profileDetail))
      return
    }

    const nextBundle =
      templateVariants.find((bundle) => bundle.id === preferredBundleId) ||
      templateVariants.find((bundle) => bundle.is_active) ||
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
    } catch (error) {
      console.error("Ошибка загрузки profile bundles:", error)
      toast.error("Не удалось загрузить bundle'ы выбранного профиля")
      setSelectedProfileDetail(null)
      setDraftBundle(null)
    } finally {
      setLoadingProfile(false)
    }
  }

  const reloadAll = async (preferredTemplateId?: string, preferredProfileId?: string, preferredBundleId?: string) => {
    setLoading(true)
    try {
      const [templatesResponse, profilesResponse] = await Promise.all([
        apiClient.getScenarioTemplates(),
        apiClient.getSchemaProfiles(),
      ])
      const nextTemplates = templatesResponse.templates
      const nextProfiles = profilesResponse.profiles
      setTemplates(nextTemplates)
      setProfiles(nextProfiles)

      const nextTemplateId = preferredTemplateId || nextTemplates[0]?.id || ""
      const nextProfileId = preferredProfileId || nextProfiles[0]?.id || ""
      setSelectedTemplateId(nextTemplateId)
      setSelectedProfileId(nextProfileId)
      if (nextProfileId) {
        await loadProfile(nextProfileId, nextTemplateId, preferredBundleId)
      }
    } catch (error) {
      console.error("Ошибка загрузки logical templates:", error)
      toast.error("Не удалось загрузить шаблоны сценариев и профили данных")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void reloadAll()
  }, [])

  const handleTemplateChange = async (templateId: string) => {
    setSelectedTemplateId(templateId)
    syncEditorState(selectedProfileDetail, templateId)
  }

  const handleProfileChange = async (profileId: string) => {
    setSelectedProfileId(profileId)
    await loadProfile(profileId, selectedTemplateId)
  }

  const handleVariantChange = (bundleId: string) => {
    if (bundleId === "new") {
      setSelectedBundleId("new")
      setDraftBundle(buildEmptyDraft(selectedTemplateId, selectedProfileDetail, activeVariant))
      return
    }
    const bundle = variants.find((item) => item.id === bundleId)
    if (!bundle) return
    setSelectedBundleId(bundle.id)
    setDraftBundle(bundleToDraft(bundle))
  }

  const updateDraftBundle = (updater: (current: ScenarioBundleSaveRequest) => ScenarioBundleSaveRequest) => {
    setDraftBundle((current) => (current ? updater(current) : current))
  }

  const updateQuery = (queryIndex: number, patch: Partial<ScenarioQuery>) => {
    updateDraftBundle((current) => ({
      ...current,
      queries: current.queries.map((query, index) => (
        index === queryIndex ? { ...query, ...patch } : query
      )),
    }))
  }

  const addQuery = () => {
    updateDraftBundle((current) => ({
      ...current,
      queries: [
        ...current.queries,
        {
          sql_template: "",
          query_type: "select",
          description: "",
          weight: 1,
          order_index: current.queries.length,
          params: [],
        },
      ],
    }))
  }

  const removeQuery = (queryIndex: number) => {
    updateDraftBundle((current) => ({
      ...current,
      queries: current.queries
        .filter((_, index) => index !== queryIndex)
        .map((query, index) => ({ ...query, order_index: index })),
    }))
  }

  const addParam = (queryIndex: number) => {
    updateDraftBundle((current) => ({
      ...current,
      queries: current.queries.map((query, index) => (
        index === queryIndex
          ? {
              ...query,
              params: [
                ...(query.params || []),
                {
                  param_name: "",
                  param_type: "random_int",
                  min_value: 1,
                  max_value: 1000,
                  table_ref: null,
                  column_ref: null,
                  string_length: 16,
                  current_value: 0,
                  step: 1,
                },
              ],
            }
          : query
      )),
    }))
  }

  const updateParam = (queryIndex: number, paramIndex: number, patch: Partial<ScenarioParam>) => {
    updateDraftBundle((current) => ({
      ...current,
      queries: current.queries.map((query, index) => (
        index === queryIndex
          ? {
              ...query,
              params: (query.params || []).map((param, idx) => (
                idx === paramIndex ? { ...param, ...patch } : param
              )),
            }
          : query
      )),
    }))
  }

  const removeParam = (queryIndex: number, paramIndex: number) => {
    updateDraftBundle((current) => ({
      ...current,
      queries: current.queries.map((query, index) => (
        index === queryIndex
          ? {
              ...query,
              params: (query.params || []).filter((_, idx) => idx !== paramIndex),
            }
          : query
      )),
    }))
  }

  const addIndex = () => {
    updateDraftBundle((current) => ({
      ...current,
      indexes: [
        ...current.indexes,
        {
          table_name: "",
          column_names: "",
          index_type: "btree",
          index_name: null,
          is_unique: false,
          condition: null,
          description: "",
        },
      ],
    }))
  }

  const updateIndex = (indexPosition: number, patch: Partial<ScenarioIndex>) => {
    updateDraftBundle((current) => ({
      ...current,
      indexes: current.indexes.map((item, idx) => (
        idx === indexPosition ? { ...item, ...patch } : item
      )),
    }))
  }

  const removeIndex = (indexPosition: number) => {
    updateDraftBundle((current) => ({
      ...current,
      indexes: current.indexes.filter((_, idx) => idx !== indexPosition),
    }))
  }

  const handleCreateTemplate = async () => {
    const name = window.prompt("Название нового logical template")
    if (!name?.trim()) return
    const description = window.prompt("Описание logical template", "") || ""
    try {
      const template = await apiClient.createScenarioTemplate({
        name: name.trim(),
        description,
      }) as ScenarioTemplate
      toast.success("Шаблон создан")
      await reloadAll(template.id, selectedProfileId)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Не удалось создать шаблон")
    }
  }

  const handleUpdateTemplate = async () => {
    if (!selectedTemplate || selectedTemplate.is_builtin) return
    const name = window.prompt("Новое название logical template", selectedTemplate.name)
    if (!name?.trim()) return
    const description = window.prompt("Описание logical template", selectedTemplate.description || "") || ""
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
    if (!window.confirm(`Удалить custom template "${selectedTemplate.name}" и все его variants?`)) return
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
    try {
      await apiClient.generateProfileBundles(selectedProfileId, {
        scenario_template_ids: [selectedTemplateId],
      })
      toast.success("Канонический bundle обновлён")
      await loadProfile(selectedProfileId, selectedTemplateId)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Не удалось сгенерировать bundle")
    }
  }

  const handleSaveBundle = async () => {
    if (!draftBundle || !selectedProfileId) return
    if (draftBundle.queries.length === 0) {
      toast.error("Добавьте хотя бы один SQL-запрос в bundle")
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
    const name = window.prompt("Название нового variant bundle", `${selectedBundle.name} (копия)`)
    if (!name?.trim()) return
    try {
      const cloned = await apiClient.cloneBundleVariant(selectedProfileId, selectedBundle.id, { name: name.trim() })
      toast.success("Variant склонирован")
      await loadProfile(selectedProfileId, selectedTemplateId, cloned.id)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Не удалось клонировать bundle")
    }
  }

  const handleActivateBundle = async () => {
    if (!selectedBundle || !selectedProfileId || selectedBundle.is_active) return
    try {
      await apiClient.activateBundleVariant(selectedProfileId, selectedBundle.id)
      toast.success("Variant активирован")
      await loadProfile(selectedProfileId, selectedTemplateId, selectedBundle.id)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Не удалось активировать bundle")
    }
  }

  const handleDeleteBundle = async () => {
    if (!selectedBundle || !selectedProfileId) return
    if (!window.confirm(`Удалить variant "${selectedBundle.name}"?`)) return
    try {
      await apiClient.deleteBundleVariant(selectedProfileId, selectedBundle.id)
      toast.success("Variant удалён")
      await loadProfile(selectedProfileId, selectedTemplateId)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Не удалось удалить bundle")
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Сценарии тестирования</h1>
        <p className="text-muted-foreground">
          Управление logical templates и bundle variants по профилям модели данных
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Layers className="h-5 w-5" />
            Выбор шаблона и профиля
          </CardTitle>
          <CardDescription>
            Выберите logical template и профиль модели данных, затем редактируйте active variant или создавайте новый
          </CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="space-y-2">
            <Label>Шаблон сценария</Label>
            <Select value={selectedTemplateId} onValueChange={(value) => void handleTemplateChange(value)}>
              <SelectTrigger>
                <SelectValue placeholder="Выберите шаблон сценария" />
              </SelectTrigger>
              <SelectContent>
                {templates.map((template) => (
                  <SelectItem key={template.id} value={template.id}>
                    {template.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {selectedTemplate?.description && (
              <p className="text-sm text-muted-foreground">{selectedTemplate.description}</p>
            )}
            <div className="flex flex-wrap gap-2 pt-2">
              <Button variant="outline" size="sm" onClick={handleCreateTemplate}>
                <Plus className="mr-2 h-4 w-4" />
                Новый template
              </Button>
              {!selectedTemplate?.is_builtin && (
                <>
                  <Button variant="outline" size="sm" onClick={handleUpdateTemplate}>
                    <Pencil className="mr-2 h-4 w-4" />
                    Редактировать template
                  </Button>
                  <Button variant="outline" size="sm" onClick={handleDeleteTemplate}>
                    <Trash2 className="mr-2 h-4 w-4" />
                    Удалить template
                  </Button>
                </>
              )}
            </div>
          </div>

          <div className="space-y-2">
            <Label>Профиль модели данных</Label>
            <Select value={selectedProfileId} onValueChange={(value) => void handleProfileChange(value)}>
              <SelectTrigger>
                <SelectValue placeholder="Выберите профиль данных" />
              </SelectTrigger>
              <SelectContent>
                {profiles.map((profile) => (
                  <SelectItem key={profile.id} value={profile.id}>
                    {profile.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {selectedProfileDetail?.description && (
              <p className="text-sm text-muted-foreground">{selectedProfileDetail.description}</p>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileCode2 className="h-5 w-5" />
            Bundle variants
          </CardTitle>
          <CardDescription>
            {selectedProfileDetail?.name || "—"} / {selectedTemplate?.id || "—"} / variants: {variants.length}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loadingProfile ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Загружаем bundle...
            </div>
          ) : !draftBundle ? (
            <div className="space-y-4">
              <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
                Для выбранной пары профиль/шаблон variants пока нет. Создайте новый variant вручную или сгенерируйте канонический bundle.
              </div>
            </div>
          ) : draftBundle ? (
            <div className="space-y-4">
              <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>Variant bundle</Label>
                    <Select value={selectedBundleId} onValueChange={handleVariantChange}>
                      <SelectTrigger>
                        <SelectValue placeholder="Выберите variant" />
                      </SelectTrigger>
                      <SelectContent>
                        {variants.map((bundle) => (
                          <SelectItem key={bundle.id} value={bundle.id}>
                            {bundle.name}{bundle.is_active ? " (active)" : ""}
                          </SelectItem>
                        ))}
                        <SelectItem value="new">Новый variant</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {selectedBundle && <Badge variant="secondary">{selectedBundle.name}</Badge>}
                    {selectedBundle?.is_active && <Badge variant="outline">active</Badge>}
                    {selectedBundle?.is_builtin && <Badge variant="outline">builtin</Badge>}
                    <Badge variant="outline">queries: {draftBundle.queries.length}</Badge>
                    <Badge variant="outline">indexes: {draftBundle.indexes.length}</Badge>
                    <Badge variant="outline">source: {draftBundle.generation_source || "manual_variant"}</Badge>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" size="sm" onClick={() => handleVariantChange("new")}>
                      <Plus className="mr-2 h-4 w-4" />
                      Новый variant
                    </Button>
                    <Button variant="outline" size="sm" disabled={!selectedBundle} onClick={handleCloneBundle}>
                      <Copy className="mr-2 h-4 w-4" />
                      Клонировать
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!selectedBundle || selectedBundle.is_active}
                      onClick={handleActivateBundle}
                    >
                      <Check className="mr-2 h-4 w-4" />
                      Сделать active
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!selectedTemplate?.is_builtin}
                      onClick={handleGenerateCanonical}
                    >
                      <WandSparkles className="mr-2 h-4 w-4" />
                      Generate canonical
                    </Button>
                    <Button size="sm" disabled={saving} onClick={handleSaveBundle}>
                      {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                      Сохранить
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!selectedBundle || selectedBundle.is_builtin || selectedBundle.is_active}
                      onClick={handleDeleteBundle}
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Удалить
                    </Button>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label>Название variant</Label>
                      <Input
                        value={draftBundle.name}
                        onChange={(event) => updateDraftBundle((current) => ({
                          ...current,
                          name: event.target.value,
                        }))}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Generation source</Label>
                      <Input
                        value={draftBundle.generation_source || "manual_variant"}
                        onChange={(event) => updateDraftBundle((current) => ({
                          ...current,
                          generation_source: event.target.value,
                        }))}
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>Описание variant</Label>
                    <Textarea
                      value={draftBundle.description || ""}
                      onChange={(event) => updateDraftBundle((current) => ({
                        ...current,
                        description: event.target.value,
                      }))}
                    />
                  </div>
                </div>
              </div>

              <ScrollArea className="h-[520px] rounded-lg border">
                <div className="space-y-3 p-4">
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-medium">SQL-запросы</div>
                    <Button variant="outline" size="sm" onClick={addQuery}>
                      <Plus className="mr-2 h-4 w-4" />
                      Добавить query
                    </Button>
                  </div>

                  {draftBundle.queries.map((query, queryIndex) => (
                    <div key={`query-${queryIndex}`} className="rounded-lg border p-3 space-y-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge>{queryIndex + 1}</Badge>
                          <Badge variant="outline">{query.query_type}</Badge>
                        </div>
                        <Button variant="outline" size="sm" onClick={() => removeQuery(queryIndex)}>
                          <Trash2 className="mr-2 h-4 w-4" />
                          Удалить query
                        </Button>
                      </div>

                      <div className="grid gap-3 md:grid-cols-3">
                        <div className="space-y-2">
                          <Label>Тип</Label>
                          <Input
                            value={query.query_type}
                            onChange={(event) => updateQuery(queryIndex, { query_type: event.target.value })}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>Вес</Label>
                          <Input
                            type="number"
                            min={1}
                            value={query.weight}
                            onChange={(event) => updateQuery(queryIndex, { weight: Number(event.target.value) || 1 })}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>Порядок</Label>
                          <Input
                            type="number"
                            min={0}
                            value={query.order_index}
                            onChange={(event) => updateQuery(queryIndex, { order_index: Number(event.target.value) || 0 })}
                          />
                        </div>
                      </div>

                      <div className="space-y-2">
                        <Label>Описание query</Label>
                        <Input
                          value={query.description || ""}
                          onChange={(event) => updateQuery(queryIndex, { description: event.target.value })}
                        />
                      </div>

                      <div className="space-y-2">
                        <Label>SQL</Label>
                        <Textarea
                          className="min-h-[140px] font-mono text-xs"
                          value={query.sql_template}
                          onChange={(event) => updateQuery(queryIndex, { sql_template: event.target.value })}
                        />
                      </div>

                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="text-xs font-medium text-muted-foreground">Параметры</div>
                          <Button variant="outline" size="sm" onClick={() => addParam(queryIndex)}>
                            <Plus className="mr-2 h-4 w-4" />
                            Добавить param
                          </Button>
                        </div>
                        {(query.params || []).map((param, paramIndex) => (
                          <div key={`param-${queryIndex}-${paramIndex}`} className="rounded-md border p-3 space-y-3">
                            <div className="flex justify-end">
                              <Button variant="outline" size="sm" onClick={() => removeParam(queryIndex, paramIndex)}>
                                <Trash2 className="mr-2 h-4 w-4" />
                                Удалить param
                              </Button>
                            </div>
                            <div className="grid gap-3 md:grid-cols-2">
                              <div className="space-y-2">
                                <Label>Имя</Label>
                                <Input
                                  value={param.param_name}
                                  onChange={(event) => updateParam(queryIndex, paramIndex, { param_name: event.target.value })}
                                />
                              </div>
                              <div className="space-y-2">
                                <Label>Тип</Label>
                                <Input
                                  value={param.param_type}
                                  onChange={(event) => updateParam(queryIndex, paramIndex, { param_type: event.target.value })}
                                />
                              </div>
                              <div className="space-y-2">
                                <Label>Min</Label>
                                <Input
                                  type="number"
                                  value={param.min_value ?? ""}
                                  onChange={(event) => updateParam(queryIndex, paramIndex, {
                                    min_value: event.target.value === "" ? null : Number(event.target.value),
                                  })}
                                />
                              </div>
                              <div className="space-y-2">
                                <Label>Max</Label>
                                <Input
                                  type="number"
                                  value={param.max_value ?? ""}
                                  onChange={(event) => updateParam(queryIndex, paramIndex, {
                                    max_value: event.target.value === "" ? null : Number(event.target.value),
                                  })}
                                />
                              </div>
                              <div className="space-y-2">
                                <Label>Table ref</Label>
                                <Input
                                  value={param.table_ref ?? ""}
                                  onChange={(event) => updateParam(queryIndex, paramIndex, { table_ref: event.target.value || null })}
                                />
                              </div>
                              <div className="space-y-2">
                                <Label>Column ref</Label>
                                <Input
                                  value={param.column_ref ?? ""}
                                  onChange={(event) => updateParam(queryIndex, paramIndex, { column_ref: event.target.value || null })}
                                />
                              </div>
                              <div className="space-y-2">
                                <Label>String pattern</Label>
                                <Input
                                  value={param.string_pattern ?? ""}
                                  onChange={(event) => updateParam(queryIndex, paramIndex, { string_pattern: event.target.value || null })}
                                />
                              </div>
                              <div className="space-y-2">
                                <Label>String length</Label>
                                <Input
                                  type="number"
                                  value={param.string_length ?? ""}
                                  onChange={(event) => updateParam(queryIndex, paramIndex, {
                                    string_length: event.target.value === "" ? null : Number(event.target.value),
                                  })}
                                />
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <Database className="h-4 w-4" />
                    Индексы bundle
                  </div>
                  <Button variant="outline" size="sm" onClick={addIndex}>
                    <Plus className="mr-2 h-4 w-4" />
                    Добавить index
                  </Button>
                </div>
                <div className="space-y-3">
                  {draftBundle.indexes.map((index, indexPosition) => (
                    <div key={`index-${indexPosition}`} className="rounded-lg border p-3 space-y-3">
                      <div className="flex justify-end">
                        <Button variant="outline" size="sm" onClick={() => removeIndex(indexPosition)}>
                          <Trash2 className="mr-2 h-4 w-4" />
                          Удалить index
                        </Button>
                      </div>
                      <div className="grid gap-3 md:grid-cols-2">
                        <div className="space-y-2">
                          <Label>Таблица</Label>
                          <Input
                            value={index.table_name}
                            onChange={(event) => updateIndex(indexPosition, { table_name: event.target.value })}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>Колонки</Label>
                          <Input
                            value={index.column_names}
                            onChange={(event) => updateIndex(indexPosition, { column_names: event.target.value })}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>Тип</Label>
                          <Input
                            value={index.index_type}
                            onChange={(event) => updateIndex(indexPosition, { index_type: event.target.value })}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>Index name</Label>
                          <Input
                            value={index.index_name ?? ""}
                            onChange={(event) => updateIndex(indexPosition, { index_name: event.target.value || null })}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>Condition</Label>
                          <Input
                            value={index.condition ?? ""}
                            onChange={(event) => updateIndex(indexPosition, { condition: event.target.value || null })}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>Unique</Label>
                          <Select
                            value={index.is_unique ? "true" : "false"}
                            onValueChange={(value) => updateIndex(indexPosition, { is_unique: value === "true" })}
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
                      <div className="space-y-2">
                        <Label>Описание</Label>
                        <Input
                          value={index.description ?? ""}
                          onChange={(event) => updateIndex(indexPosition, { description: event.target.value || null })}
                        />
                      </div>
                    </div>
                  ))}
                  {draftBundle.indexes.length === 0 && (
                    <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                      Для этого variant пока не задано ни одного индекса.
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
