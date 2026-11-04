/**
 * Page position for a server-paginated list. Changing the filters returns to the first page.
 */

import { useState } from "react";

export function usePageOffset(filterKey: string): [number, (offset: number) => void] {
  const [position, setPosition] = useState({ filterKey, offset: 0 });
  const offset = position.filterKey === filterKey ? position.offset : 0;
  return [offset, (next: number) => setPosition({ filterKey, offset: next })];
}
