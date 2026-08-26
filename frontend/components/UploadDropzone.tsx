"use client";

import { FileImage, FileText, ScanLine, UploadCloud, X } from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { useI18n } from "@/lib/i18n";
import type { Dictionary } from "@/lib/i18n/dictionaries";
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
  { labelKey: keyof Dictionary["upload"]; icon: React.ReactNode }
> = {
  photo: { labelKey: "kindPhoto", icon: <FileImage className="h-4 w-4" /> },
  pdf: { labelKey: "kindPdf", icon: <FileText className="h-4 w-4" /> },
  scan: { labelKey: "kindScan", icon: <ScanLine className="h-4 w-4" /> },
  other: { labelKey: "kindOther", icon: <FileText className="h-4 w-4" /> },
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Multi-file upload UI. Accepts typed-document photos, lab PDFs and scan films.
 *
 * Two modes:
 *  - Staging mode (`files` + `onChange`): files are held client-side.
 *  - Immediate mode (`onUpload`): files are handed to the parent as soon as they
 *    are picked/dropped, which POSTs them to /documents. The staged list is not
 *    rendered in this mode — the parent shows the real uploaded documents.
 */
export function UploadDropzone({
  files,
  onChange,
  onUpload,
  busy,
}: {
  files?: StagedFile[];
  onChange?: (files: StagedFile[]) => void;
  onUpload?: (files: File[]) => void;
  busy?: boolean;
}) {
  const { t } = useI18n();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  // Nested dragenter/dragleave fire constantly; count them so the active
  // state doesn't flicker as the pointer crosses child elements.
  const dragDepth = useRef(0);
  const staged = useMemo(() => files ?? [], [files]);

  const addFiles = useCallback(
    (list: FileList | null) => {
      if (!list || list.length === 0) return;
      const arr = Array.from(list);
      if (onUpload) {
        onUpload(arr);
        return;
      }
      if (onChange) {
        const next: StagedFile[] = arr.map((file) => ({
          id: `${file.name}-${file.size}-${crypto.randomUUID()}`,
          file,
          kind: classify(file),
        }));
        onChange([...staged, ...next]);
      }
    },
    [staged, onChange, onUpload],
  );

  const remove = (id: string) => onChange?.(staged.filter((f) => f.id !== id));

  return (
    <div className="flex flex-col gap-3">
      <div
        role="button"
        tabIndex={0}
        aria-label={t.upload.dropTitle}
        aria-disabled={busy || undefined}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragEnter={(e) => {
          e.preventDefault();
          dragDepth.current += 1;
          setDragging(true);
        }}
        onDragOver={(e) => e.preventDefault()}
        onDragLeave={() => {
          dragDepth.current = Math.max(0, dragDepth.current - 1);
          if (dragDepth.current === 0) setDragging(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          dragDepth.current = 0;
          setDragging(false);
          addFiles(e.dataTransfer.files);
        }}
        className={cn(
          "flex cursor-pointer select-none flex-col items-center justify-center gap-2 rounded-lg",
          "border-2 border-dashed px-5 py-9 text-center",
          "transition-[border-color,background-color,transform] duration-150 ease-clinical",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
          dragging
            ? "scale-[1.01] border-accent bg-primary/10"
            : "border-control-border/70 bg-surface-muted/40 hover:border-accent/70 hover:bg-surface-muted/70",
          busy && "pointer-events-none opacity-60",
        )}
      >
        <span
          className={cn(
            "flex h-11 w-11 items-center justify-center rounded-full border transition-colors",
            dragging
              ? "border-accent/40 bg-primary/15 text-primary"
              : "border-border bg-surface text-muted",
          )}
          aria-hidden
        >
          <UploadCloud className="h-5 w-5" />
        </span>
        <p className="text-sm font-semibold text-foreground">
          {dragging ? t.upload.dropActive : t.upload.dropTitle}
        </p>
        <p className="max-w-xs text-xs leading-relaxed text-muted text-pretty">
          {t.upload.dropHint}
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          disabled={busy}
          accept="image/*,application/pdf,.dcm"
          className="sr-only"
          tabIndex={-1}
          onChange={(e) => {
            addFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </div>

      {staged.length > 0 && (
        <ul className="flex flex-col gap-2">
          {staged.map((f) => (
            <li
              key={f.id}
              className="flex animate-rise-in items-center justify-between gap-3 rounded-md border border-border bg-surface px-3 py-2 shadow-card"
            >
              <div className="flex min-w-0 items-center gap-2.5">
                <span className="shrink-0 text-muted" aria-hidden>
                  {kindMeta[f.kind].icon}
                </span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-foreground">
                    {f.file.name}
                  </p>
                  <p className="text-xs tabular-nums text-muted">
                    {formatSize(f.file.size)}
                  </p>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Badge tone="neutral" className="hidden sm:inline-flex">
                  {t.upload[kindMeta[f.kind].labelKey]}
                </Badge>
                <button
                  type="button"
                  onClick={() => remove(f.id)}
                  aria-label={`${t.upload.remove} ${f.file.name}`}
                  className="rounded p-1.5 text-muted transition-colors hover:bg-danger-surface hover:text-danger"
                >
                  <X className="h-4 w-4" aria-hidden />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
