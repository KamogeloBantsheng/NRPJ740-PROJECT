/**
 * SCR-04: Submit Maintenance Request Page (FR-05, BR-05, BR-09, SCR-04).
 * Allows a resident to report a fault in their room or common area with validation and idempotency.
 */

import { useState } from "react";
import { AppIcon } from "../components/AppIcon";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { workflowApi } from "../api/workflow";
import { AppError } from "../api/client";
import { useAuth } from "../context/useAuth";

const submitSchema = z.object({
  location_id: z.number().min(1, "Please select a room or common area location."),
  category_id: z.number().min(1, "Please select a fault category."),
  description: z
    .string()
    .trim()
    .min(10, "Description must be at least 10 characters long.")
    .max(2000, "Description cannot exceed 2,000 characters."),
});

type SubmitFormData = z.infer<typeof submitSchema>;

export function SubmitRequestPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [serverError, setServerError] = useState<string | null>(null);

  // Client token generated once per form session for idempotent submission (Table 5.7)
  const [clientToken] = useState<string>(() => crypto.randomUUID());

  const { data: locations = [], isLoading: loadingLocations } = useQuery({
    queryKey: ["locations"],
    queryFn: () => workflowApi.getLocations(),
  });

  const { data: categories = [], isLoading: loadingCategories } = useQuery({
    queryKey: ["categories"],
    queryFn: () => workflowApi.getCategories(),
  });

  const {
    register,
    handleSubmit,
    control,
    formState: { errors },
  } = useForm<SubmitFormData>({
    resolver: zodResolver(submitSchema),
    defaultValues: {
      location_id: user?.assigned_location || 0,
      category_id: 0,
      description: "",
    },
  });

  const descriptionValue = useWatch({ control, name: "description" }) || "";
  const descLength = descriptionValue.trim().length;

  const submitMutation = useMutation({
    mutationFn: (data: SubmitFormData) =>
      workflowApi.submitRequest({
        location_id: data.location_id,
        category_id: data.category_id,
        description: data.description.trim(),
        client_token: clientToken,
      }),
    onSuccess: (newRequest) => {
      queryClient.invalidateQueries({ queryKey: ["requests"] });
      navigate(`/requests/${newRequest.id}`, {
        state: { message: "Your maintenance request has been submitted successfully." },
      });
    },
    onError: (err) => {
      if (err instanceof AppError) {
        setServerError(err.message);
      } else {
        setServerError("Failed to submit request. Please verify your connection.");
      }
    },
  });

  const onSubmit = (data: SubmitFormData) => {
    setServerError(null);
    submitMutation.mutate(data);
  };

  const backLink = user?.role === "WARDEN" ? "/dashboard" : "/requests";
  const backLabel = user?.role === "WARDEN" ? "Back to Dashboard" : "Back to My Requests";

  return (
    <div className="page-container form-page-container">
      {/* Navigation Breadcrumb */}
      <div className="breadcrumb-nav">
        <Link to={backLink} className="back-link">
          {backLabel}
        </Link>
      </div>

      <div className="card form-card">
        <div className="form-header">
          <h1 className="form-title">Report a Maintenance Fault</h1>
          <p className="form-subtitle">
            Moroka Hall of Residence &bull; Fast-track maintenance dispatch (FR-05, SCR-04)
          </p>
        </div>

        {/* Room Assignment Scope Callout */}
        {user?.role === "RESIDENT" && (
          <div className="alert alert-info" style={{ marginBottom: "1.25rem", padding: "0.85rem 1rem", borderRadius: "8px", backgroundColor: "#fff1f2", border: "1px solid #fecdd3", color: "#9f1239" }}>
            {user.assigned_location_name ? (
              <div>
                <strong>Your Assigned Room:</strong> {user.assigned_location_name}.
                <div style={{ fontSize: "0.875rem", marginTop: "0.25rem", color: "#881337" }}>
                  Per university policy, students may report faults for their assigned room and shared communal facilities only.
                </div>
              </div>
            ) : (
              <div>
                <strong>Room Status:</strong> No private room currently assigned to your profile. You may report faults for communal areas.
              </div>
            )}
          </div>
        )}

        {user?.role === "WARDEN" && (
          <div className="alert alert-info" style={{ marginBottom: "1.25rem", padding: "0.85rem 1rem", borderRadius: "8px", backgroundColor: "#fffbeb", border: "1px solid #fde68a", color: "#92400e" }}>
            <strong>Residence Warden Mode:</strong> You have full residence oversight and may choose from all student rooms and common areas in {user.residence_name || "Moroka Hall"}.
          </div>
        )}

        {serverError && (
          <div className="alert alert-error" role="alert">
            <span className="alert-icon"><AppIcon name="alert" size={16} /></span>
            <span>{serverError}</span>
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="maintenance-form" noValidate>
          {/* Location Picker */}
          <div className="form-group">
            <label htmlFor="location_id" className="form-label">
              Location in Moroka Hall <span className="required">*</span>
            </label>
            <select
              id="location_id"
              {...register("location_id", { valueAsNumber: true })}
              className={`select-input ${errors.location_id ? "input-error" : ""}`}
              disabled={loadingLocations || submitMutation.isPending}
            >
              <option value="0">-- Select Room or Common Area --</option>
              {locations.map((loc) => {
                const isAssignedRoom = user?.assigned_location === loc.id;
                const prefix = isAssignedRoom
                  ? "[Assigned Room] "
                  : loc.kind === "COMMON_AREA"
                  ? "[Common Area] "
                  : "[Room] ";
                return (
                  <option key={loc.id} value={loc.id}>
                    {prefix}
                    {loc.display_name}
                  </option>
                );
              })}
            </select>
            {errors.location_id && (
              <span className="field-error">{errors.location_id.message}</span>
            )}
            <span className="field-hint">
              {user?.role === "WARDEN"
                ? "Select any student room or communal facility in the residence."
                : "Select your assigned room or the communal facility where the fault occurred."}
            </span>
          </div>

          {/* Fault Category Picker */}
          <div className="form-group">
            <label htmlFor="category_id" className="form-label">
              Fault Category <span className="required">*</span>
            </label>
            <select
              id="category_id"
              {...register("category_id", { valueAsNumber: true })}
              className={`select-input ${errors.category_id ? "input-error" : ""}`}
              disabled={loadingCategories || submitMutation.isPending}
            >
              <option value="0">-- Select Category --</option>
              {categories.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.name}
                </option>
              ))}
            </select>
            {errors.category_id && (
              <span className="field-error">{errors.category_id.message}</span>
            )}
          </div>

          {/* Fault Description */}
          <div className="form-group">
            <div className="label-row">
              <label htmlFor="description" className="form-label">
                Fault Description <span className="required">*</span>
              </label>
              <span
                className={`char-counter ${
                  descLength >= 10 && descLength <= 2000
                    ? "counter-valid"
                    : descLength > 2000
                    ? "counter-overflow"
                    : "counter-low"
                }`}
              >
                {descLength} / 2,000 chars (min 10)
              </span>
            </div>
            <textarea
              id="description"
              rows={5}
              {...register("description")}
              placeholder="Please describe the fault in detail (e.g. 'Hot water pipe under basin leaking onto floor, water tap valve is stuck')..."
              className={`textarea-input ${errors.description ? "input-error" : ""}`}
              disabled={submitMutation.isPending}
            />
            {errors.description && (
              <span className="field-error">{errors.description.message}</span>
            )}
            <span className="field-hint">
              Be specific about what is broken, leaking, or damaged to assist technician diagnosis.
            </span>
          </div>

          {/* Form Actions */}
          <div className="form-actions">
            <Link to="/requests" className="btn btn-secondary">
              Cancel
            </Link>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={submitMutation.isPending}
            >
              {submitMutation.isPending ? "Submitting Fault Report..." : "Submit Maintenance Request"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
