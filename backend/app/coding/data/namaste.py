"""Bundled NAMASTE / AYUSH traditional-medicine code list (demo subset).

NAMASTE (National AYUSH Morbidity and Standardized Terminologies Electronic
portal) provides standardized codes for Ayurveda, Siddha and Unani disorders,
relevant to Indian EMR compliance and the ABDM story (PROJECT.md section 3).

The codes below are illustrative demo placeholders in a NAMASTE-style namespace
(``AYU-*`` Ayurveda, ``SID-*`` Siddha, ``UNA-*`` Unani). They are for the
Doc-mate prototype only and are NOT authoritative NAMASTE portal codes. They
let the demo show dual coding (biomedical ICD-11 + traditional NAMASTE) where a
condition has a well-known AYUSH correspondence.

Each entry: (code, display, [aliases]).
"""

from __future__ import annotations

# code, display, aliases (lowercase match terms)
NAMASTE_ENTRIES: list[tuple[str, str, list[str]]] = [
    ("AYU-DM-01", "Madhumeha (Ayurveda: diabetes mellitus)",
     ["diabetes", "diabetes mellitus", "type 2 diabetes", "madhumeha", "t2dm"]),
    ("AYU-HTN-01", "Rakta Gata Vata (Ayurveda: hypertension)",
     ["hypertension", "high blood pressure", "htn", "rakta gata vata"]),
    ("AYU-AMA-01", "Amlapitta (Ayurveda: hyperacidity / dyspepsia)",
     ["acidity", "hyperacidity", "dyspepsia", "gerd", "reflux", "amlapitta"]),
    ("AYU-SAN-01", "Sandhivata (Ayurveda: osteoarthritis)",
     ["osteoarthritis", "joint pain", "arthritis", "sandhivata"]),
    ("AYU-AMV-01", "Amavata (Ayurveda: rheumatoid arthritis)",
     ["rheumatoid arthritis", "amavata"]),
    ("AYU-TAM-01", "Tamaka Shwasa (Ayurveda: bronchial asthma)",
     ["asthma", "bronchial asthma", "tamaka shwasa", "wheezing"]),
    ("AYU-JVR-01", "Jwara (Ayurveda: fever)",
     ["fever", "pyrexia", "jwara"]),
    ("AYU-PAN-01", "Pandu (Ayurveda: anaemia)",
     ["anaemia", "anemia", "iron deficiency", "pandu"]),
    ("AYU-ARS-01", "Arsha (Ayurveda: haemorrhoids)",
     ["haemorrhoids", "hemorrhoids", "piles", "arsha"]),
    ("AYU-STH-01", "Sthaulya (Ayurveda: obesity)",
     ["obesity", "obese", "sthaulya"]),
    ("AYU-ATI-01", "Atisara (Ayurveda: diarrhoea)",
     ["diarrhoea", "diarrhea", "loose motions", "atisara", "gastroenteritis"]),
    ("AYU-KAS-01", "Kasa (Ayurveda: cough)",
     ["cough", "kasa"]),
    ("SID-NER-01", "Neerizhivu (Siddha: diabetes mellitus)",
     ["diabetes", "neerizhivu"]),
    ("SID-GUN-01", "Gunmam (Siddha: peptic ulcer / gastritis)",
     ["peptic ulcer", "gastritis", "gunmam"]),
    ("UNA-ZIY-01", "Ziabetus (Unani: diabetes mellitus)",
     ["diabetes", "ziabetus"]),
    ("UNA-ZGT-01", "Zaghtud-dam Qavi (Unani: hypertension)",
     ["hypertension", "zaghtud", "high blood pressure"]),
]
