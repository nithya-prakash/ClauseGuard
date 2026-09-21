"use client";

import { useRef, useState } from "react";

const ACCEPTED_EXTENSIONS = [".pdf", ".docx"];

interface UploadScreenProps {
  onFileSelected: (file: File) => void;
  errorMessage: string | null;
}

function hasAcceptedExtension(filename: string): boolean {
  const lower = filename.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

export default function UploadScreen({ onFileSelected, errorMessage }: UploadScreenProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function handleFiles(files: FileList | null) {
    setLocalError(null);
    const file = files?.[0];
    if (!file) return;
    if (!hasAcceptedExtension(file.name)) {
      setLocalError(`Unsupported file type. Accepted: ${ACCEPTED_EXTENSIONS.join(", ")}`);
      return;
    }
    onFileSelected(file);
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h2 className="mb-4 text-xl font-semibold text-slate-800">Upload a contract</h2>
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          handleFiles(e.dataTransfer.files);
        }}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-16 text-center transition-colors ${
          isDragging ? "border-blue-500 bg-blue-50" : "border-slate-300 bg-white"
        }`}
      >
        <p className="text-base font-medium text-slate-700">
          Drag & drop a PDF or DOCX contract here
        </p>
        <p className="mt-1 text-sm text-slate-500">or click to browse</p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS.join(",")}
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>
      {(localError || errorMessage) && (
        <p className="mt-3 text-sm text-red-600">{localError ?? errorMessage}</p>
      )}
    </div>
  );
}
