"use client";

import { PatientList } from "@/components/PatientList";
import { RequireRole } from "@/components/RequireRole";
import { useI18n } from "@/lib/i18n";

export default function DoctorPatientsPage() {
  const { t } = useI18n();
  return (
    <RequireRole role="doctor">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">
          {t.nav.patients}
        </h1>
        <p className="text-sm text-muted">
          Open a patient to read their snapshot.
        </p>
      </div>
      <PatientList basePath="/doctor/patients" />
    </RequireRole>
  );
}
