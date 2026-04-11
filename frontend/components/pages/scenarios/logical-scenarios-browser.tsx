"use client"

import { useEffect, useMemo, useState } from "react"
import { Database, FileCode2, Layers, Loader2 } from "lucide-react"

import { apiClient } from "@/lib/api"
import type {
  ScenarioBundleSummary,
  ScenarioTemplate,
  SchemaProfileDetail,
  SchemaProfileSummary,
} from "@/lib/types"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { toast } from "sonner"

export function LogicalScenariosBrowser() {
  const [templates, setTemplates] = useState<ScenarioTemplate[]>([])
  const [profiles, setProfiles] = useState<SchemaProfileSummary[]>([])
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>("")
  const [selectedProfileId, setSelectedProfileId] = useState<string>("")
  const [selectedProfileDetail, setSelectedProfileDetail] = useState<SchemaProfileDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingProfile, setLoadingProfile] = useState(false)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const [templatesResponse, profilesResponse] = await Promise.all([
          apiClient.getScenarioTemplates(),
          apiClient.getSchemaProfiles(),
        ])
        setTemplates(templatesResponse.templates)
        setProfiles(profilesResponse.profiles)

        if (templatesResponse.templates.length > 0) {
          setSelectedTemplateId(templatesResponse.templates[0].id)
        }
        if (profilesResponse.profiles.length > 0) {
          setSelectedProfileId(profilesResponse.profiles[0].id)
        }
      } catch (error) {
        console.error("Ошибка загрузки logical templates:", error)
        toast.error("Не удалось загрузить шаблоны сценариев и профили данных")
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [])

  useEffect(() => {
    if (!selectedProfileId) {
      setSelectedProfileDetail(null)
      return
    }

    const loadProfile = async () => {
      setLoadingProfile(true)
      try {
        const profile = await apiClient.getSchemaProfile(selectedProfileId)
        setSelectedProfileDetail(profile)
      } catch (error) {
        console.error("Ошибка загрузки profile bundles:", error)
        toast.error("Не удалось загрузить bundle'ы выбранного профиля")
        setSelectedProfileDetail(null)
      } finally {
        setLoadingProfile(false)
      }
    }
    void loadProfile()
  }, [selectedProfileId])

  const selectedTemplate = useMemo(
    () => templates.find((template) => template.id === selectedTemplateId) || null,
    [templates, selectedTemplateId]
  )

  const selectedBundle: ScenarioBundleSummary | null = useMemo(() => {
    if (!selectedProfileDetail || !selectedTemplateId) return null
    return selectedProfileDetail.bundles.find(
      (bundle) => bundle.scenario_template_id === selectedTemplateId
    ) || null
  }, [selectedProfileDetail, selectedTemplateId])

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
          Просмотр logical templates и канонических SQL bundle'ов по модели данных
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Layers className="h-5 w-5" />
            Выбор шаблона и профиля
          </CardTitle>
          <CardDescription>
            Сначала выберите logical template, затем профиль модели данных для просмотра SQL-набора
          </CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="space-y-2">
            <Label>Шаблон сценария</Label>
            <Select value={selectedTemplateId} onValueChange={setSelectedTemplateId}>
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
          </div>

          <div className="space-y-2">
            <Label>Профиль модели данных</Label>
            <Select value={selectedProfileId} onValueChange={setSelectedProfileId}>
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
            SQL bundle
          </CardTitle>
          <CardDescription>
            {selectedProfileDetail?.name || "—"} / {selectedTemplate?.id || "—"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loadingProfile ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Загружаем bundle...
            </div>
          ) : !selectedBundle ? (
            <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
              Для выбранной пары профиль/шаблон bundle пока не найден.
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary">{selectedBundle.name}</Badge>
                <Badge variant="outline">queries: {selectedBundle.queries.length}</Badge>
                <Badge variant="outline">indexes: {selectedBundle.indexes.length}</Badge>
                <Badge variant="outline">source: {selectedBundle.generation_source}</Badge>
              </div>

              <ScrollArea className="h-[420px] rounded-lg border">
                <div className="space-y-3 p-4">
                  {selectedBundle.queries.map((query, index) => (
                    <div key={query.id} className="rounded-lg border p-3">
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <Badge>{index + 1}</Badge>
                        <Badge variant="outline">{query.query_type}</Badge>
                        <Badge variant="outline">weight {query.weight}</Badge>
                      </div>
                      <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded bg-muted p-3 text-xs">
                        {query.sql_template}
                      </pre>
                      {query.params?.length ? (
                        <div className="mt-2 space-y-1">
                          <p className="text-xs font-medium text-muted-foreground">Параметры</p>
                          <div className="flex flex-wrap gap-2">
                            {query.params.map((param) => (
                              <Badge key={param.id} variant="outline" className="text-xs">
                                {param.param_name}: {param.param_type}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </ScrollArea>

              {selectedBundle.indexes.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <Database className="h-4 w-4" />
                    Индексы bundle
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {selectedBundle.indexes.map((index) => (
                      <Badge key={index.id} variant="outline">
                        {index.table_name}({index.column_names})
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
