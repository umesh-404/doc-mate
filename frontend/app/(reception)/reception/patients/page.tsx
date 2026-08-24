"use client";

import { UserPlus } from "lucide-react";
import Link from "next/link";
import { PatientList } from "@/components/PatientList";
import { RequireRole } from "@/components/RequireRole";
import { Button } from "@/components/ui/Button";
import { useI18n } from "@/lib/i18n";

export default function ReceptionPatientsPage() {
  const { t } = useI18n();
  return (
    <RequireRole role="reception">
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {t.nav.patients}
          </h1>
          <p className="text-sm text-muted">
            {t.patients.subtitleReception}
          </p>
        </div>
        <Link href="/reception/patients/new">
          <Button>
            <UserPlus className="h-4 w-4" aria-hidden />
            {t.nav.newPatient}
          </Button>
        </Link>
      </div>
      <PatientList basePath="/reception/patients" />
    </RequireRole>
  );
}
