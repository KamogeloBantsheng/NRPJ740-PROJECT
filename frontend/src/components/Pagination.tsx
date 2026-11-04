/**
 * Previous/next controls for server-paginated lists (page size capped at 50, Section 5.7).
 */

interface PaginationProps {
  total: number;
  limit: number;
  offset: number;
  onChange: (offset: number) => void;
}

export function Pagination({ total, limit, offset, onChange }: PaginationProps) {
  if (total <= limit) return null;

  return (
    <nav className="audit-pagination-bar" aria-label="Pagination">
      <button
        type="button"
        onClick={() => onChange(Math.max(0, offset - limit))}
        disabled={offset === 0}
        className="btn btn-sm btn-secondary"
      >
        Previous Page
      </button>
      <span className="page-indicator font-sm text-muted">
        Page {Math.floor(offset / limit) + 1} of {Math.ceil(total / limit)}
      </span>
      <button
        type="button"
        onClick={() => onChange(offset + limit)}
        disabled={offset + limit >= total}
        className="btn btn-sm btn-secondary"
      >
        Next Page
      </button>
    </nav>
  );
}
