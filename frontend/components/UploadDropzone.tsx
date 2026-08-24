"use client";

import { FileImage, FileText, ScanLine, UploadCloud, X } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

export interface StagedFile {
  id: string;
  file: File;
  kind: "photo" | "pdf" | "scan" | "other";
}

function classify(file: File): StagedFile["kind"] {
  const name = file.name.toLowerCase();
  if (file.type.startsWith("image/")) {
    if (name.includes("xray") || name.includes("mri") || name.includes("ct")) {
      return "scan";
    }
    return "photo";
  }
  if (file.type === "application/pdf" || name.endsWith(".pdf")) return "pdf";
  if (name.endsWith(".dcm")) return "scan";
  return "other";
}

const kindMeta: Record<
  StagedFile["kind"],
  { label: string; icon: React.ReactNode }
> = {
  photo: { label: "Document photo", icon: <FileImage className="h-4 w-4" /> },
  pdf: { label: "Lab PDF", icon: <FileText className="h-4 w-4" /> },
  scan: { label: "Scan film", icon: <ScanLine className="h-4 w-4" /> },
  other: { label: "Other", icon: <FileText className="h-4 w-4" /> },
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Multi-file upload staging UI. Accepts typed-document photos, lab PDFs and
 * scan films. This is UI only for now — files are staged client-side and
 * would be POSTed to the ingestion endpoint on submit.
 */
export function UploadDropzone({
  files,
  onChange,
}: {
  files: StagedFile[];
  onChange: (files: StagedFile[]) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const addFiles = useCallback(
    (list: FileList | null) => {
      if (!list) return;
      const staged: StagedFile[] = Array.from(list).map((file) => ({
        id: `${file.name}-${file.size}-${crypto.randomUUID()}`,
        file,
        kind: classify(file),
      }));
      onChange([...files, ...staged]);
    },
    [files, onChange],
  );

  const remove = (id: string) => onChange(files.filter((f) => f.id !== id));

  return (
    <div className="flex flex-col gap-3">
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          addFiles(e.dataTransfer.files);
        }}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors",
          dragging
            ? "border-accent bg-primary/5"
            : "border-border bg-surface-muted/40 hover:border-accent/50",
        )}
      >
        <UploadCloud className="h-8 w-8 text-muted" aria-hidden />
        <p className="text-sm font-medium text-foreground">
          Drag &amp; drop files, or click to browse
        </p>
        <p className="text-xs text-muted">
          Document photos, lab PDFs, scan films (X-ray / MRI / CT), DICOM
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept="image/*,application/pdf,.dcm"
          className="hidden"
          onChange={(e) => addFiles(e.target.files)}
        />
      </div>

      {files.length > 0 && (
        <ul className="flex flex-col gap-2">
          {files.map((f) => (
            <li
              key={f.id}
              className="flex items-center justify-between gap-3 rounded-md border border-border bg-surface px-3 py-2"
            >
              <div className="flex min-w-0 items-center gap-3">
                <span className="text-muted" aria-hidden>
                  {kindMeta[f.kind].icon}
                </span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-foreground">
                    {f.file.name}
                  </p>
                  <p className="text-xs text-muted">{formatSize(f.file.size)}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone="neutral">{kindMeta[f.kind].label}</Badge>
                <button
                  type="button"
                  onClick={() => remove(f.id)}
                  aria-label={`Remove ${f.file.name}`}
                  className="rounded p-1 text-muted hover:bg-surface-muted hover:text-danger"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
