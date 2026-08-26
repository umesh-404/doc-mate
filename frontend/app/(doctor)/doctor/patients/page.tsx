"use client";

import { useState } from "react";
import { PatientList } from "@/components/PatientList";
import { RequireRole } from "@/components/RequireRole";
import { ShortcutsHelp, ShortcutsHint } from "@/components/ShortcutsHelp";
import { useI18n } from "@/lib/i18n";
import { useShortcuts } from "@/lib/shortcuts";
import { useTheme } from "@/lib/theme";

export default function DoctorPatientsPage() {
  const { t } = useI18n();
  const { cycleTheme } = useTheme();
  const [helpOpen, setHelpOpen] = useState(false);

  useShortcuts({
    "?": () => setHelpOpen(true),
    escape: () => setHelpOpen(false),
    t: () => cycleTheme(),
  });

  return (
    <RequireRole
      role="doctor"
      headerActions={
        <ShortcutsHint
          onOpen={() => setHelpOpen(true)}
          className="hidden sm:inline-flex"
        />
      }
    >
      <div className="mb-5">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          {t.nav.patients}
        </h1>
        <p className="mt-1 text-sm text-muted">{t.patients.subtitleDoctor}</p>
      </div>
      <PatientList basePath="/doctor/patients" />

      <ShortcutsHelp
        open={helpOpen}
        onClose={() => setHelpOpen(false)}
        entries={[
          { keys: ["/"], label: t.shortcuts.search },
          { keys: ["t"], label: t.shortcuts.theme },
          { keys: ["?"], label: t.shortcuts.help },
        ]}
      />
    </RequireRole>
  );
}
