/**
 * Network error notice (Table 5.3 system pages), shown while the API cannot be reached.
 */

import { useEffect, useState } from "react";
import { NETWORK_FAILED_EVENT, NETWORK_RESTORED_EVENT } from "../api/client";

export function NetworkBanner() {
  const [isUnreachable, setIsUnreachable] = useState(false);

  useEffect(() => {
    const showBanner = () => setIsUnreachable(true);
    const hideBanner = () => setIsUnreachable(false);
    window.addEventListener(NETWORK_FAILED_EVENT, showBanner);
    window.addEventListener(NETWORK_RESTORED_EVENT, hideBanner);
    return () => {
      window.removeEventListener(NETWORK_FAILED_EVENT, showBanner);
      window.removeEventListener(NETWORK_RESTORED_EVENT, hideBanner);
    };
  }, []);

  if (!isUnreachable) return null;

  return (
    <div className="alert alert-warning network-banner" role="alert">
      <strong>Network error:</strong> the server cannot be reached. Your last action may not have been saved.
    </div>
  );
}
