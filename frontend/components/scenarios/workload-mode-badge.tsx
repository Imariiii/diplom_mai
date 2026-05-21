"use client"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import {
  formatWorkloadModeBadge,
  getWorkloadModeBadgeVariant,
} from "@/lib/throughput-metrics"

interface WorkloadModeBadgeProps {
  workloadMode?: string | null
  className?: string
}

/** Бейдж режима исполнения bundle: одиночные SQL-запросы или транзакции. */
export function WorkloadModeBadge({ workloadMode, className }: WorkloadModeBadgeProps) {
  return (
    <Badge
      variant={getWorkloadModeBadgeVariant(workloadMode)}
      className={cn("text-[11px] font-normal", className)}
    >
      {formatWorkloadModeBadge(workloadMode)}
    </Badge>
  )
}
