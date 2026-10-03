import { useEffect, useRef, useState } from "react";
import type { BrandSummary } from "../types";
import { Icon } from "../components/Icon";
import { BrandSwitcher } from "./BrandSwitcher";
import type { Favorite } from "./store";

type IconName = Parameters<typeof Icon>[0]["name"];
type NavItem = { id: string; label: string; icon: IconName };

/** A1: the everyday destinations. */
const MAIN_NAV: NavItem[] = [
  { id: "home", label: "Home", icon: "home" },
  { id: "work", label: "My work", icon: "folder" },
  { id: "live", label: "Live simulation", icon: "zap" },
  { id: "brands", label: "Campaigns & Journeys", icon: "layers" },
  { id: "chat", label: "Chat", icon: "message" },
];

/** A2 / BR6: brand knowledge, always for the active brand. */
const BRAND_IQ: NavItem[] = [
  { id: "iq/kits", label: "Brand Kits", icon: "document" },
  { id: "iq/personas", label: "Personas", icon: "persona" },
  { id: "iq/guardrails", label: "Compliance Guardrails", icon: "shield" },
  { id: "iq/intel", label: "Market Intelligence", icon: "radar" },
];

/** "+ New" quick starts. Flow and brief open the current working agents until their
 *  workspace versions land (Phases 3–6); the engagement plan waits on M2 (deferred). */
const NEW_ITEMS: { label: string; href?: string; note?: string }[] = [
  { label: "Start an engagement plan", href: "#/v3/agent/engagement-planner" },
  { label: "Plan a campaign", href: "#/v3/agent/campaign-planner" },
  { label: "Create a segment", href: "#/v3/agent/segmentation-planner" },
  { label: "Build a flow", href: "#/v3/agent/flow-planner" },
  { label: "Compile a brief", href: "#/v3/agent/brief-compiler" },
  { label: "Brief to Salesforce journey", href: "#/v3/agent/briefing-agent" },
];

export function Rail({ current, brands, activeBrand, recentBrands, onSelectBrand, favorites, isFavorite, toggleFavorite, pinned, setPinned }: {
  current: string;
  brands: BrandSummary[];
  activeBrand: string | null;
  recentBrands: string[];
  onSelectBrand: (brand: string | null) => void;
  favorites: Favorite[];
  isFavorite: (type: Favorite["type"], id: string) => boolean;
  toggleFavorite: (fav: Favorite) => void;
  pinned: boolean;
  setPinned: (v: boolean) => void;
}) {
  const [hover, setHover] = useState(false);
  const [newOpen, setNewOpen] = useState(false);
  const newRef = useRef<HTMLDivElement>(null);
  const expanded = pinned || hover;

  useEffect(() => {
    if (!newOpen) return;
    const onDown = (e: MouseEvent) => { if (!newRef.current?.contains(e.target as Node)) setNewOpen(false); };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [newOpen]);

  const link = (item: NavItem) => {
    const active = current === item.id || (item.id === "home" && current === "");
    return (
      <a key={item.id} href={`#/v3/${item.id}`} className={`v3-nav-item ${active ? "active" : ""}`}
        title={expanded ? undefined : item.label} aria-current={active ? "page" : undefined}>
        <Icon name={item.icon} size={17} />
        {expanded && <span>{item.label}</span>}
      </a>
    );
  };

  return (
    <div className={`v3-rail-slot ${pinned ? "pinned" : ""}`}>
      <nav className={`v3-rail ${expanded ? "expanded" : "collapsed"}`} aria-label="Navigation"
        onMouseEnter={() => setHover(true)} onMouseLeave={() => { setHover(false); setNewOpen(false); }}>
        <div className="v3-rail-top">
          {expanded && <span className="v3-rail-brand">Omni OS</span>}
          <button type="button" className="v3-rail-pin" onClick={() => setPinned(!pinned)}
            aria-label={pinned ? "Unpin sidebar" : "Pin sidebar open"} title={pinned ? "Unpin sidebar" : "Pin sidebar open"}>
            <Icon name={pinned ? "arrowLeft" : "arrowRight"} size={13} />
          </button>
        </div>

        <BrandSwitcher brands={brands} activeBrand={activeBrand} recentBrands={recentBrands} onSelect={onSelectBrand}
          isFavorite={isFavorite} toggleFavorite={toggleFavorite} collapsed={!expanded} />

        <div className="v3-new" ref={newRef}>
          <button type="button" className="v3-new-btn" onClick={() => setNewOpen((o) => !o)} aria-expanded={newOpen}
            title={expanded ? undefined : "New"}>
            <Icon name="plus" size={16} />{expanded && <span>New</span>}
          </button>
          {newOpen && (
            <div className="v3-new-menu" role="menu">
              {NEW_ITEMS.map((n) => n.href
                ? <a key={n.label} role="menuitem" href={n.href} className="v3-new-item">{n.label}</a>
                : <span key={n.label} role="menuitem" aria-disabled="true" className="v3-new-item disabled">{n.label}<em>{n.note}</em></span>)}
            </div>
          )}
        </div>

        <div className="v3-nav-group">{MAIN_NAV.map(link)}</div>

        <div className="v3-nav-group">
          {expanded ? <div className="v3-nav-label">Brand IQ</div> : <div className="v3-nav-divider" />}
          {BRAND_IQ.map(link)}
        </div>

        <div className="v3-nav-group v3-nav-grow">
          {expanded ? <div className="v3-nav-label">Favorites</div> : <div className="v3-nav-divider" />}
          {favorites.map((f) => (
            <a key={`${f.type}:${f.id}`} href={f.href} className="v3-nav-item" title={expanded ? undefined : f.label}
              onClick={f.type === "brand" ? () => onSelectBrand(f.id) : undefined}>
              <Icon name="star" size={15} />{expanded && <span>{f.label}</span>}
            </a>
          ))}
          {favorites.length === 0 && expanded && <div className="v3-nav-empty">Star a brand, agent or campaign to pin it here.</div>}
        </div>

        <div className="v3-rail-user" title={expanded ? undefined : "Account"}>
          <span className="v3-avatar"><Icon name="user" size={15} /></span>
          {expanded && <span>Account</span>}
        </div>
      </nav>
    </div>
  );
}
