/**
 * Synthetic demo data. No real PII. Used to make the UI look complete before
 * the backend ingestion/RAG pipeline is wired in. Shapes loosely mirror the
 * FHIR-aligned model in PROJECT.md (§9) so the real API can drop in later.
 */

export type DocStatus = "uploaded" | "processing" | "extracted" | "verified" | "failed";
export type Severity = "high" | "moderate" | "low";
export type TrendDirection = "up" | "down" | "stable";

export interface Citation {
  /** Short label shown on the chip, e.g. "Rx" or "Lab". */
  kind: string;
  /** Human date shown on the chip, e.g. "12 Jun". */
  date: string;
  /** Source document id (no-op target for now). */
  documentId: string;
}

export interface PatientListItem {
  id: string;
  name: string;
  abhaId: string;
  age: number;
  sex: "M" | "F" | "O";
  lastVisit: string;
  status: DocStatus;
  docCount: number;
  reason: string;
}

export interface Allergy {
  substance: string;
  reaction: string;
  severity: Severity;
  citation: Citation;
}

export interface Medication {
  name: string;
  dose: string;
  frequency: string;
  since: string;
  needsVerification?: boolean;
  citation: Citation;
}

export interface Problem {
  label: string;
  detail: string;
  since: string;
  citation: Citation;
}

export interface LabResult {
  name: string;
  value: string;
  unit: string;
  reference: string;
  trend: TrendDirection;
  flag?: "high" | "low";
  date: string;
  citation: Citation;
}

export interface Encounter {
  date: string;
  title: string;
  summary: string;
  facility: string;
  citation: Citation;
}

export interface Flag {
  text: string;
  kind: "missing" | "unreadable" | "contradiction";
}

export interface PatientSnapshot {
  id: string;
  name: string;
  abhaId: string;
  age: number;
  sex: "M" | "F" | "O";
  bloodGroup: string;
  preferredLanguage: string;
  currentComplaint: {
    text: string;
    onset: string;
    citation: Citation;
  };
  problems: Problem[];
  allergies: Allergy[];
  medications: Medication[];
  labs: LabResult[];
  encounters: Encounter[];
  flags: Flag[];
}

export const mockPatients: PatientListItem[] = [
  {
    id: "P-10482",
    name: "Ramesh Kumar",
    abhaId: "14-2233-4455-6677",
    age: 58,
    sex: "M",
    lastVisit: "2026-08-22",
    status: "verified",
    docCount: 9,
    reason: "Chest tightness on exertion",
  },
  {
    id: "P-10488",
    name: "Lakshmi Narayanan",
    abhaId: "14-9081-2245-1123",
    age: 63,
    sex: "F",
    lastVisit: "2026-08-23",
    status: "extracted",
    docCount: 6,
    reason: "Follow-up: diabetes & BP",
  },
  {
    id: "P-10491",
    name: "Abdul Rahman",
    abhaId: "14-5566-7788-9900",
    age: 41,
    sex: "M",
    lastVisit: "2026-08-24",
    status: "processing",
    docCount: 4,
    reason: "Persistent cough, 3 weeks",
  },
  {
    id: "P-10495",
    name: "Sunita Devi",
    abhaId: "14-3344-1122-8877",
    age: 34,
    sex: "F",
    lastVisit: "2026-08-24",
    status: "uploaded",
    docCount: 2,
    reason: "Antenatal check-up",
  },
  {
    id: "P-10499",
    name: "Joseph Mathew",
    abhaId: "14-7788-9911-2233",
    age: 70,
    sex: "M",
    lastVisit: "2026-08-20",
    status: "failed",
    docCount: 5,
    reason: "Knee pain, mobility review",
  },
];

const snapshots: Record<string, PatientSnapshot> = {
  "P-10482": {
    id: "P-10482",
    name: "Ramesh Kumar",
    abhaId: "14-2233-4455-6677",
    age: 58,
    sex: "M",
    bloodGroup: "B+",
    preferredLanguage: "Hindi",
    currentComplaint: {
      text: "Chest tightness on exertion for the past 5 days, relieved by rest. Reports mild breathlessness climbing stairs.",
      onset: "5 days ago",
      citation: { kind: "Note", date: "22 Aug", documentId: "D-3301" },
    },
    problems: [
      {
        label: "Type 2 Diabetes Mellitus",
        detail: "Diagnosed 2018, on oral agents",
        since: "2018",
        citation: { kind: "Disch", date: "04 Mar", documentId: "D-2201" },
      },
      {
        label: "Hypertension",
        detail: "Stage 2, on dual therapy",
        since: "2016",
        citation: { kind: "Rx", date: "12 Jun", documentId: "D-2140" },
      },
      {
        label: "Dyslipidaemia",
        detail: "Elevated LDL noted on last panel",
        since: "2021",
        citation: { kind: "Lab", date: "18 Aug", documentId: "D-3288" },
      },
    ],
    allergies: [
      {
        substance: "Penicillin",
        reaction: "Urticaria, facial swelling",
        severity: "high",
        citation: { kind: "Disch", date: "04 Mar", documentId: "D-2201" },
      },
      {
        substance: "Sulfa drugs",
        reaction: "Rash",
        severity: "moderate",
        citation: { kind: "Note", date: "12 Jun", documentId: "D-2140" },
      },
    ],
    medications: [
      {
        name: "Metformin",
        dose: "1000 mg",
        frequency: "Twice daily",
        since: "2018",
        citation: { kind: "Rx", date: "12 Jun", documentId: "D-2140" },
      },
      {
        name: "Telmisartan",
        dose: "40 mg",
        frequency: "Once daily",
        since: "2016",
        citation: { kind: "Rx", date: "12 Jun", documentId: "D-2140" },
      },
      {
        name: "Atorvastatin",
        dose: "20 mg",
        frequency: "Once at night",
        since: "2021",
        citation: { kind: "Rx", date: "12 Jun", documentId: "D-2140" },
      },
      {
        name: "Amlodipine",
        dose: "5 mg (?)",
        frequency: "Once daily",
        since: "2022",
        needsVerification: true,
        citation: { kind: "Photo", date: "22 Aug", documentId: "D-3300" },
      },
    ],
    labs: [
      {
        name: "HbA1c",
        value: "8.1",
        unit: "%",
        reference: "< 7.0",
        trend: "up",
        flag: "high",
        date: "18 Aug",
        citation: { kind: "Lab", date: "18 Aug", documentId: "D-3288" },
      },
      {
        name: "Fasting glucose",
        value: "156",
        unit: "mg/dL",
        reference: "70–100",
        trend: "up",
        flag: "high",
        date: "18 Aug",
        citation: { kind: "Lab", date: "18 Aug", documentId: "D-3288" },
      },
      {
        name: "LDL cholesterol",
        value: "142",
        unit: "mg/dL",
        reference: "< 100",
        trend: "down",
        flag: "high",
        date: "18 Aug",
        citation: { kind: "Lab", date: "18 Aug", documentId: "D-3288" },
      },
      {
        name: "eGFR",
        value: "78",
        unit: "mL/min",
        reference: "> 90",
        trend: "stable",
        flag: "low",
        date: "18 Aug",
        citation: { kind: "Lab", date: "18 Aug", documentId: "D-3288" },
      },
      {
        name: "Serum creatinine",
        value: "1.1",
        unit: "mg/dL",
        reference: "0.7–1.3",
        trend: "stable",
        date: "18 Aug",
        citation: { kind: "Lab", date: "18 Aug", documentId: "D-3288" },
      },
    ],
    encounters: [
      {
        date: "22 Aug 2026",
        title: "OP visit — Cardiology triage",
        summary: "Presented with exertional chest tightness. ECG ordered.",
        facility: "Govt. General Hospital, OPD-4",
        citation: { kind: "Note", date: "22 Aug", documentId: "D-3301" },
      },
      {
        date: "18 Aug 2026",
        title: "Lab panel — Metabolic + lipid",
        summary: "HbA1c and LDL trending up versus March values.",
        facility: "Central Diagnostics Lab",
        citation: { kind: "Lab", date: "18 Aug", documentId: "D-3288" },
      },
      {
        date: "04 Mar 2026",
        title: "Discharge — Short admission",
        summary: "Admitted for hyperglycaemia; stabilised on adjusted regimen.",
        facility: "Govt. General Hospital, Ward 7",
        citation: { kind: "Disch", date: "04 Mar", documentId: "D-2201" },
      },
      {
        date: "12 Jun 2025",
        title: "OP visit — Chronic care review",
        summary: "Medication reconciliation; BP and sugars reviewed.",
        facility: "Urban PHC, Sector 12",
        citation: { kind: "Rx", date: "12 Jun", documentId: "D-2140" },
      },
    ],
    flags: [
      {
        text: "Amlodipine dose read as '5 mg' from a photographed strip — confirm with patient.",
        kind: "unreadable",
      },
      {
        text: "No ECG or cardiac imaging on file despite chest complaint.",
        kind: "missing",
      },
      {
        text: "March discharge lists 'Glimepiride' but it does not appear on the current medication list.",
        kind: "contradiction",
      },
    ],
  },
};

export function getMockSnapshot(id: string): PatientSnapshot {
  const found = snapshots[id];
  if (found) return found;
  // Fallback: reuse the richest snapshot but relabel with the requested id
  // so any patient link renders a complete screen for the demo.
  const base = snapshots["P-10482"]!;
  const listItem = mockPatients.find((p) => p.id === id);
  return {
    ...base,
    id,
    name: listItem?.name ?? base.name,
    abhaId: listItem?.abhaId ?? base.abhaId,
    age: listItem?.age ?? base.age,
    sex: listItem?.sex ?? base.sex,
  };
}
