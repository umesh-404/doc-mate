"use client";

import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  FileCheck2,
  Loader2,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { useI18n } from "@/lib/i18n";
import type { Dictionary } from "@/lib/i18n/dictionaries";
import type { DocStatus } from "@/lib/mock-data";

type Tone = "neutral" | "primary" | "warning" | "success" | "danger";

const map: Record<
  DocStatus,
  { key: keyof Dictionary["docStatus"]; tone: Tone; icon: React.ReactNode }
> = {
  uploaded: {
    key: "uploaded",
    tone: "neutral",
    icon: <CircleDashed className="h-3 w-3" />,
  },
  processing: {
    key: "processing",
    tone: "primary",
    icon: <Loader2 className="h-3 w-3 animate-spin" />,
  },
  extracted: {
    key: "extracted",
    tone: "warning",
    icon: <FileCheck2 className="h-3 w-3" />,
  },
  verified: {
    key: "verified",
    tone: "success",
    icon: <CheckCircle2 className="h-3 w-3" />,
  },
  failed: {
    key: "failed",
    tone: "danger",
    icon: <AlertTriangle className="h-3 w-3" />,
  },
};

export function StatusBadge({ status }: { status: DocStatus }) {
  const { t } = useI18n();
  const meta = map[status];
  return (
    <Badge tone={meta.tone}>
      <span aria-hidden>{meta.icon}</span>
      {t.docStatus[meta.key]}
    </Badge>
  );
}
