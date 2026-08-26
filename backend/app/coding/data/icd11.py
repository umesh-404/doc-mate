"""Bundled ICD-11 (MMS) code list for common conditions and labs.

Offline, demo-only subset of the WHO ICD-11 Mortality and Morbidity Statistics
linearization. Codes and titles are transcribed from the public ICD-11 browser
for a handful of high-frequency outpatient conditions and observations so the
demo can attach honest, citable codes without any network call.

This is NOT the full ICD-11 classification — it is a curated lookup for the
Doc-mate prototype. Where no entry matches, callers must return nothing rather
than fabricate a code (see PROJECT.md section 4).

Each entry: (code, display, [aliases]). ``aliases`` are lowercase substrings
used for case-insensitive/substring matching against extracted item labels.
"""

from __future__ import annotations

# code, display, aliases (extra match terms beyond the display text)
ICD11_ENTRIES: list[tuple[str, str, list[str]]] = [
    # --- Endocrine / metabolic ---
    ("5A11", "Type 2 diabetes mellitus",
     ["type 2 diabetes", "t2dm", "diabetes mellitus type 2", "niddm",
      "diabetes type 2", "dm2"]),
    ("5A10", "Type 1 diabetes mellitus",
     ["type 1 diabetes", "t1dm", "iddm", "diabetes type 1"]),
    ("5A14", "Diabetes mellitus, type unspecified",
     ["diabetes mellitus", "diabetes"]),
    ("5A00", "Hypothyroidism",
     ["hypothyroid", "underactive thyroid"]),
    ("5A02", "Thyrotoxicosis",
     ["hyperthyroid", "thyrotoxicosis", "overactive thyroid"]),
    ("5B81", "Obesity",
     ["obese", "obesity"]),
    ("5C80", "Hyperlipidaemia",
     ["hyperlipidemia", "hyperlipidaemia", "dyslipidemia", "dyslipidaemia",
      "high cholesterol"]),
    ("5A61", "Hypoglycaemia",
     ["hypoglycemia", "hypoglycaemia", "low blood sugar"]),
    ("5PA00", "Hyperglycaemia",
     ["hyperglycemia", "hyperglycaemia", "high blood sugar"]),
    # --- Circulatory ---
    ("BA00", "Essential hypertension",
     ["hypertension", "high blood pressure", "htn", "essential hypertension"]),
    ("BA01", "Hypertensive heart disease",
     ["hypertensive heart"]),
    ("BA40", "Angina pectoris",
     ["angina"]),
    ("BA41", "Acute myocardial infarction",
     ["myocardial infarction", "heart attack", "mi", "stemi", "nstemi"]),
    ("BA5A", "Heart failure",
     ["heart failure", "cardiac failure", "chf", "congestive"]),
    ("BC81", "Atrial fibrillation",
     ["atrial fibrillation", "af", "afib"]),
    ("8B00", "Stroke, not known if ischaemic or haemorrhagic",
     ["stroke", "cva", "cerebrovascular accident"]),
    ("BD40", "Peripheral arterial disease",
     ["peripheral arterial", "peripheral vascular", "pad"]),
    # --- Respiratory ---
    ("CA23", "Asthma",
     ["asthma", "asthmatic"]),
    ("CA22", "Chronic obstructive pulmonary disease",
     ["copd", "chronic obstructive", "emphysema"]),
    ("CA40", "Pneumonia",
     ["pneumonia"]),
    ("CA07", "Acute upper respiratory infection",
     ["upper respiratory infection", "uri", "common cold",
      "acute respiratory infection"]),
    ("1B10", "Tuberculosis",
     ["tuberculosis", "tb", "pulmonary tb", "koch"]),
    # --- Infectious ---
    ("1D40", "Dengue",
     ["dengue"]),
    ("1F40", "Malaria",
     ["malaria"]),
    ("1A00", "Cholera",
     ["cholera"]),
    ("1A40", "Typhoid fever",
     ["typhoid", "enteric fever"]),
    ("1E50", "Viral hepatitis",
     ["hepatitis", "viral hepatitis"]),
    ("1C62", "Human immunodeficiency virus disease",
     ["hiv", "aids", "human immunodeficiency"]),
    ("1E32", "Gastroenteritis",
     ["gastroenteritis", "diarrhoea", "diarrhea", "loose motions"]),
    # --- Digestive ---
    ("DA63", "Peptic ulcer",
     ["peptic ulcer", "gastric ulcer", "duodenal ulcer"]),
    ("DA22", "Gastro-oesophageal reflux disease",
     ["gerd", "reflux", "gastro-oesophageal", "gastroesophageal", "acidity"]),
    ("DA92", "Irritable bowel syndrome",
     ["irritable bowel", "ibs"]),
    ("DB94", "Cirrhosis of liver",
     ["cirrhosis", "liver cirrhosis"]),
    # --- Genitourinary / renal ---
    ("GB61", "Chronic kidney disease",
     ["chronic kidney", "ckd", "renal failure", "kidney disease"]),
    ("GC00", "Acute kidney failure",
     ["acute kidney", "acute renal failure", "aki"]),
    ("GC08", "Urinary tract infection",
     ["urinary tract infection", "uti"]),
    ("GB70", "Calculus of kidney",
     ["kidney stone", "renal calculus", "nephrolithiasis"]),
    # --- Musculoskeletal ---
    ("FA20", "Osteoarthritis",
     ["osteoarthritis", "oa", "degenerative joint"]),
    ("FA20.0", "Rheumatoid arthritis",
     ["rheumatoid arthritis", "ra"]),
    ("FB80", "Osteoporosis",
     ["osteoporosis"]),
    ("ME84.2", "Low back pain",
     ["low back pain", "backache", "lumbago"]),
    ("FA80", "Gout",
     ["gout"]),
    # --- Mental / neuro ---
    ("6A70", "Single episode depressive disorder",
     ["depression", "depressive"]),
    ("6B00", "Generalised anxiety disorder",
     ["anxiety", "generalised anxiety", "generalized anxiety"]),
    ("8A80", "Migraine",
     ["migraine"]),
    ("8A61", "Epilepsy",
     ["epilepsy", "seizure disorder"]),
    # --- Blood ---
    ("3A00", "Iron deficiency anaemia",
     ["iron deficiency", "anaemia", "anemia", "iron deficiency anaemia"]),
    ("3A10", "Vitamin B12 deficiency anaemia",
     ["b12 deficiency", "vitamin b12 deficiency", "megaloblastic anaemia"]),
    # --- Skin ---
    ("EA80", "Atopic dermatitis",
     ["eczema", "atopic dermatitis", "dermatitis"]),
    ("EA90", "Psoriasis",
     ["psoriasis"]),
    # --- Symptoms / observations (labs & vitals) ---
    ("MG50", "Fever",
     ["fever", "pyrexia"]),
    ("MG24.0", "Elevated blood glucose level",
     ["hba1c", "glycated haemoglobin", "blood glucose", "fasting glucose",
      "random glucose", "fbs", "rbs", "ppbs"]),
    ("MC80", "Proteinuria",
     ["proteinuria", "albuminuria"]),
    ("MA15", "Abnormal blood pressure reading",
     ["blood pressure", "bp reading"]),
    ("MC70.0", "Elevated cholesterol",
     ["cholesterol", "ldl", "hdl", "triglycerides", "lipid profile"]),
    ("MG43", "Elevated creatinine",
     ["creatinine", "serum creatinine", "egfr"]),
    ("MG27", "Abnormal haemoglobin",
     ["haemoglobin", "hemoglobin", "hb", "hgb"]),
    ("MG26", "Abnormal white blood cell count",
     ["white blood cell", "wbc", "tlc", "leukocyte"]),
    ("MC90", "Abnormal liver function test",
     ["liver function", "lft", "sgot", "sgpt", "alt", "ast", "bilirubin"]),
    ("MG22", "Abnormal thyroid function test",
     ["tsh", "thyroid function", "t3", "t4", "thyroid stimulating"]),
]
