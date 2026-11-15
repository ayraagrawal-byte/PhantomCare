"use client";

import { useState, useSyncExternalStore } from "react";

const navigation = [
  ["investigations", "Investigations", "M3 11l9-8 9 8M5 10v10h14V10M10 20v-6h4v6"],
  ["map", "Map", "m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6Zm6-3v15m6-12v15"],
  ["registrations", "Registrations", "M6 5h12v16H6zM9 3h6v4H9zM9 11h6m-6 4h6"],
  ["ownership", "Ownership", "m3 8 9-5 9 5-9 5-9-5Zm0 5 9 5 9-5M3 18l9 5 9-5"],
  ["building-evidence", "Evidence", "M6 3h8l4 4v14H6zM14 3v5h4M9 12h6m-6 4h6"],
  ["reports", "Reports", "M5 3h10l4 4v14H5zM9 11h6m-6 4h6"],
] as const;

function subscribe(listener: () => void) {
  window.addEventListener("hashchange", listener);
  return () => window.removeEventListener("hashchange", listener);
}

export default function AppHeader() {
  const [open, setOpen] = useState(false);
  const active = useSyncExternalStore(subscribe, () => window.location.hash.slice(1) || "investigations", () => "investigations");
  return (
    <>
      <header className="masthead">
        <a className="brand" href="#investigations">
          <svg aria-hidden="true" viewBox="0 0 32 30" width="36" height="34" fill="none" stroke="currentColor" strokeWidth="1.3">
            <path d="M2 27h28M4 27V15l5-2v14m0-14V8l5-2v21m0-21V3l5-1 4 3v22m0-17 5 2v15" />
          </svg>
          <span>PhantomCare</span>
        </a>
        <span className="masthead-subtitle">Hospice Registration &amp; Property Investigation Platform</span>
      </header>
      <div className="navigation-bar">
        <button type="button" className="navigation-toggle" aria-controls="workspace-navigation"
          aria-expanded={open} onClick={() => setOpen(!open)}>{open ? "Close menu" : "Menu"}</button>
        <nav id="workspace-navigation" className={open ? "is-open" : undefined} aria-label="Workspace">
          {navigation.map(([id, label, icon]) => (
            <a key={id} href={`#${id}`} aria-current={active === id ? "location" : undefined} onClick={() => setOpen(false)}>
              <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round">
                <path d={icon} />
              </svg>
              {label}
            </a>
          ))}
        </nav>
      </div>
    </>
  );
}
