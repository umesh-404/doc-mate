import { Badge } from "@/components/ui/Badge";
import type { DocStatus } from "@/lib/mock-data";

const map: Record<
  DocStatus,
  { label: string; tone: "neutral" | "primary" | "warning" | "success" | "danger" }
> = {
  uploaded: { label: "Uploaded", tone: "neutral" },
  processing: { label: "Processing", tone: "primary" },
  extracted: { label: "Extracted", tone: "warning" },
  verified: { label: "Verified", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
};

export function StatusBadge({ status }: { status: DocStatus }) {
  const meta = map[status];
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}
