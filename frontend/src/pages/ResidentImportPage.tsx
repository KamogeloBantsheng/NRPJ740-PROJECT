/**
 * SCR-12: Bulk user import Screen (FR-04, BR-07, NFR-03, TC-07, TC-08, TC-09, SCR-12).
 * Enables System Administrators to bulk-import student resident accounts with all-or-nothing
 * transaction guarantees, row-level error reporting, and exportable one-time temporary credentials.
 */

import { useState, useRef } from "react";
import { AppIcon } from "../components/AppIcon";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { usersApi } from "../api/users";
import { AppError } from "../api/client";
import type { CsvBadRowError, CsvImportResponse } from "../types/users";

export function ResidentImportPage() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [clientFileError, setClientFileError] = useState<string | null>(null);

  // Response state
  const [importResult, setImportResult] = useState<CsvImportResponse | null>(null);
  const [badRows, setBadRows] = useState<CsvBadRowError[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  // File size limit: 2 MB (TC-09)
  const MAX_FILE_SIZE = 2 * 1024 * 1024;

  const validateAndSelectFile = (file: File) => {
    setClientFileError(null);
    setErrorMessage(null);
    setBadRows([]);
    setImportResult(null);

    if (!file.name.toLowerCase().endsWith(".csv")) {
      setClientFileError("Invalid file type: File must be a .csv format document.");
      setSelectedFile(null);
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      setClientFileError(
        `File size exceeds 2 MB limit (${(file.size / (1024 * 1024)).toFixed(2)} MB). Please upload a smaller file.`
      );
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndSelectFile(e.target.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSelectFile(e.dataTransfer.files[0]);
    }
  };

  // Mutation: Import CSV
  const importMutation = useMutation({
    mutationFn: (file: File) => usersApi.importResidentsCsv(file),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      setImportResult(data);
      setBadRows([]);
      setErrorMessage(null);
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
    onError: (err) => {
      setImportResult(null);
      if (err instanceof AppError) {
        setErrorMessage(err.message);
        // Check for bad_rows validation errors
        if (err.fields && Array.isArray((err.fields as Record<string, unknown>).bad_rows)) {
          setBadRows((err.fields as Record<string, unknown>).bad_rows as CsvBadRowError[]);
        } else {
          setBadRows([]);
        }
      } else {
        setErrorMessage("An unexpected error occurred during import.");
        setBadRows([]);
      }
    },
  });

  const handleStartImport = () => {
    if (!selectedFile) return;
    importMutation.mutate(selectedFile);
  };

  // Generate Sample CSV Template Download
  const handleDownloadTemplate = () => {
    const templateContent =
      "email,full_name,role,residence,student_number,room\n" +
      "s2241001@spu.ac.za,Lerato Khumalo,RESIDENT,Moroka Hall of Residence,ST2241001,A.203\n" +
      "s2241002@spu.ac.za,Thabo Mokoena,RESIDENT,Moroka Hall of Residence,ST2241002,\n" +
      "warden2@spu.ac.za,Nomsa Dlamini,WARDEN,Moroka Hall of Residence,,\n" +
      "tech3@spu.ac.za,Sipho Dube,TECHNICIAN,,,\n";

    const blob = new Blob([templateContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "spu_resident_import_template.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // Export Generated Credentials as CSV
  const handleDownloadCredentials = () => {
    if (!importResult || importResult.credentials.length === 0) return;

    const cell = (value: string) => `"${value.replace(/"/g, '""')}"`;
    let csvContent = "email,full_name,role,student_number,temporary_password\n";
    for (const cred of importResult.credentials) {
      csvContent +=
        [cred.email, cred.full_name, cred.role, cred.student_number, cred.temporary_password].map(cell).join(",") +
        "\n";
    }

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `spu_resident_credentials_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleCopySinglePassword = (pwd: string, index: number) => {
    navigator.clipboard.writeText(pwd).then(() => {
      setCopiedIndex(index);
      setTimeout(() => setCopiedIndex(null), 2000);
    });
  };

  return (
    <main className="resident-import-page-container triage-page-container" id="main-content">
      {/* Header */}
      <div className="page-header">
        <div className="header-text-group">
          <div className="header-breadcrumbs">
            <Link to="/users" className="crumb-app">
              Administration
            </Link>
            <span className="crumb-sep">/</span>
            <Link to="/users" className="crumb-app">
              Users & Access
            </Link>
            <span className="crumb-sep">/</span>
            <span className="crumb-page">Import Users</span>
          </div>
          <h1 className="page-title">Bulk user import</h1>
          <p className="page-subtitle">
            Create many accounts from one file. If any row is wrong, none are created.
          </p>
        </div>

        <div className="page-header-actions">
          <Link to="/users" className="btn btn-secondary">
            Back to Users
          </Link>
          <button
            type="button"
            onClick={handleDownloadTemplate}
            className="btn btn-secondary"
            title="Download CSV header and row template"
          >
            Download Template
          </button>
        </div>
      </div>

      {/* Import Specification Callout */}
      <section className="card import-specs-card" aria-label="CSV format specifications">
        <div className="import-specs-header">
          <span className="specs-icon"><AppIcon name="file" size={20} color="var(--color-primary)" /></span>
          <h2 className="specs-title">What the file needs</h2>
        </div>
        <div className="import-specs-grid">
          <div className="spec-item">
            <span className="spec-label">Mandatory Columns</span>
            <span className="spec-value mono-code">email, full_name, role, residence, student_number, room</span>
          </div>
          <div className="spec-item">
            <span className="spec-label">Encoding & Size Limits</span>
            <span className="spec-value">UTF-8 text, Max 2 MB, Max 2,000 rows</span>
          </div>
          <div className="spec-item">
            <span className="spec-label">Atomicity Guarantee</span>
            <span className="spec-value text-primary font-weight-bold">
              All-or-Nothing: If ANY row fails, 0 accounts are created.
            </span>
          </div>
          <div className="spec-item">
            <span className="spec-label">Credentials Generated</span>
            <span className="spec-value">One-time temporary passwords (changed at first sign-in)</span>
          </div>
        </div>
      </section>

      {/* Upload Zone Card */}
      <section className="card file-upload-card" aria-label="CSV Upload Section">
        <h2 className="section-title">Select CSV File</h2>

        <div
          className={`file-dropzone ${isDragOver ? "dropzone-active" : ""}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              fileInputRef.current?.click();
            }
          }}
          aria-label="Upload CSV file by dropping here or clicking to browse"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,text/csv"
            onChange={handleFileChange}
            className="file-input-hidden"
            aria-hidden="true"
          />
          <div className="dropzone-inner">
            <div className="dropzone-icon"><AppIcon name="folder" size={40} color="var(--color-primary)" /></div>
            <p className="dropzone-prompt">
              <strong>Click to upload</strong> or drag and drop your CSV file here
            </p>
            <p className="dropzone-hint">Standard comma-separated format (.csv), up to 2 MB</p>
          </div>
        </div>

        {/* Client File Error */}
        {clientFileError && (
          <div className="alert-banner alert-danger mt-3" role="alert">
            <span className="alert-icon"><AppIcon name="alert" size={16} /></span>
            <div className="alert-text">{clientFileError}</div>
          </div>
        )}

        {/* Selected File Card */}
        {selectedFile && (
          <div className="file-selected-card">
            <div className="file-meta">
              <span className="file-icon"><AppIcon name="file" size={24} color="var(--color-primary)" /></span>
              <div className="file-details">
                <span className="file-name">{selectedFile.name}</span>
                <span className="file-size">
                  {(selectedFile.size / 1024).toFixed(1)} KB
                </span>
              </div>
            </div>

            <div className="file-actions">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedFile(null);
                  if (fileInputRef.current) fileInputRef.current.value = "";
                }}
                className="btn btn-sm btn-secondary"
                disabled={importMutation.isPending}
              >
                Remove
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  handleStartImport();
                }}
                className="btn btn-sm btn-primary"
                disabled={importMutation.isPending}
                id="start-import-btn"
              >
                {importMutation.isPending ? "Validating & Importing..." : "Start Batch Import"}
              </button>
            </div>
          </div>
        )}

        {/* In-Flight Indicator */}
        {importMutation.isPending && (
          <div className="loading-state mt-4" role="status" aria-live="polite">
            <div className="spinner" aria-hidden="true" />
            <p className="loading-text">
              Validating CSV rows, checking uniqueness, and creating resident accounts atomically...
            </p>
          </div>
        )}
      </section>

      {/* Error Presentation (HTTP 422 Bad Rows or General Error) */}
      {errorMessage && (
        <section className="card bad-rows-card" aria-label="Import validation failure details">
          <div className="alert-banner alert-danger" style={{ margin: 0 }} role="alert">
            <span className="alert-icon"><AppIcon name="alert" size={16} /></span>
            <div className="alert-text">
              <strong>Import Rejected (All-or-Nothing Rollback Applied):</strong> {errorMessage}
            </div>
          </div>

          {badRows.length > 0 && (
            <div className="bad-rows-section mt-4">
              <h3 className="bad-rows-title">
                Validation Failures ({badRows.length} {badRows.length === 1 ? "row" : "rows"} flagged)
              </h3>
              <p className="bad-rows-subtitle">
                Please correct the following errors in your CSV file and re-upload. No resident accounts were created in the database.
              </p>

              <div className="table-responsive">
                <table className="triage-table bad-rows-table" aria-label="CSV bad rows">
                  <thead>
                    <tr>
                      <th scope="col" style={{ width: "90px" }}>CSV Row #</th>
                      <th scope="col">Error Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {badRows.map((item, idx) => (
                      <tr key={idx}>
                        <td>
                          <span className="badge badge-danger-subtle font-weight-bold">
                            Row {item.row}
                          </span>
                        </td>
                        <td>
                          <ul className="bad-row-error-list">
                            {item.errors.map((errText, eIdx) => (
                              <li key={eIdx}>{errText}</li>
                            ))}
                          </ul>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      )}

      {/* Success Presentation (HTTP 201 Created) */}
      {importResult && (
        <section className="card import-success-card" aria-label="Batch import results">
          <div className="alert-banner alert-success" style={{ margin: 0 }} role="status">
            <span className="alert-icon"><AppIcon name="check" size={16} /></span>
            <div className="alert-text">
              <strong>Batch Import Successful:</strong> Created {importResult.created_count} resident accounts!
            </div>
          </div>

          <div className="credentials-action-bar">
            <div className="action-bar-text">
              <h3 className="action-bar-title">One-Time Temporary Credentials</h3>
              <p className="action-bar-subtitle">
                These generated passwords will NOT be displayed again. Download the CSV file now to distribute login credentials securely to students.
              </p>
            </div>
            <button
              type="button"
              onClick={handleDownloadCredentials}
              className="btn btn-primary"
              id="download-credentials-btn"
            >
              Download Credentials CSV
            </button>
          </div>

          <div className="table-responsive">
            <table className="triage-table" aria-label="Imported resident credentials">
              <thead>
                <tr>
                  <th scope="col">Student Name</th>
                  <th scope="col">Email</th>
                  <th scope="col">Student #</th>
                  <th scope="col">One-Time Password</th>
                  <th scope="col" className="text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {importResult.credentials.map((cred, idx) => (
                  <tr key={cred.id}>
                    <td>
                      <span className="font-weight-semibold">{cred.full_name}</span>
                    </td>
                    <td>
                      <span className="mono-code">{cred.email}</span>
                    </td>
                    <td>
                      <span className="mono-code">{cred.student_number}</span>
                    </td>
                    <td>
                      <span className="credential-password-text mono-code">
                        {cred.temporary_password}
                      </span>
                    </td>
                    <td className="text-right">
                      <button
                        type="button"
                        onClick={() => handleCopySinglePassword(cred.temporary_password, idx)}
                        className="btn btn-sm btn-secondary"
                      >
                        {copiedIndex === idx ? "Copied" : "Copy"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}
