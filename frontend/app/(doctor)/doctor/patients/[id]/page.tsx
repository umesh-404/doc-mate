"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { RequireRole } from "@/components/RequireRole";
import { PatientSnapshotView } from "@/components/snapshot/PatientSnapshotView";
import { useI18n } from "@/lib/i18n";
import { getMockSnapshot } from "@/lib/mock-data";

export default function PatientSnapshotPage({
  params,
}: {
  params: { id: string };
}) {
  const { t } = useI18n();
  // Mock snapshot for the demo. Real flow: useQuery -> GET /patients/{id}/summary.
  const data = getMockSnapshot(params.id);

  return (
    <RequireRole role="doctor">
      <div className="mb-5 flex items-center justify-between gap-3">
        <Link
          href="/doctor/patients"
          className="inline-flex items-center gap-1 text-sm text-muted hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          {t.nav.patients}
        </Link>
        <span className="text-sm font-medium text-muted">
          {t.snapshot.title}
        </span>
      </div>
      <PatientSnapshotView data={data} />
    </RequireRole>
  );
}
