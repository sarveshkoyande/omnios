import { useEffect, useRef, useState } from "react";
import type { BrandSummary } from "../types";
import { Icon } from "../components/Icon";
import type { Favorite } from "./store";

/** BR1: the brand switcher at the top of the rail. Scales to N brands: search, then Pinned
 *  (brand favourites), Recent, and the full list, with "All brands" always first. */
export function BrandSwitcher({ brands, activeBrand, recentBrands, onSelect, isFavorite, toggleFavorite, collapsed }: {
  brands: BrandSummary[];
  activeBrand: string | null;
  recentBrands: string[];
  onSelect: (brand: string | null) => void;
  isFavorite: (type: Favorite["type"], id: string) => boolean;
  toggleFavorite: (fav: Favorite) => void;
  collapsed: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDown); document.removeEventListener("keydown", onKey); };
  }, [open]);

  const names = brands.map((b) => b.brand);
  const q = query.trim().toLowerCase();
  const matches = (name: string) => !q || name.toLowerCase().includes(q);
  const pinned = names.filter((n) => isFavorite("brand", n) && matches(n));
  const recent = recentBrands.filter((n) => names.includes(n) && !isFavorite("brand", n) && matches(n));
  const rest = names.filter((n) => !pinned.includes(n) && !recent.includes(n) && matches(n));

  const choose = (brand: string | null) => { onSelect(brand); setOpen(false); setQuery(""); };
  const label = activeBrand ?? "All brands";

  const row = (name: string) => {
    const fav = isFavorite("brand", name);
    return (
      <div key={name} className={`v3-bs-row ${activeBrand === name ? "active" : ""}`}>
        <button type="button" className="v3-bs-pick" onClick={() => choose(name)}>
          <span className="v3-bs-dot">{name.charAt(0)}</span>{name}
          {activeBrand === name && <Icon name="check" size={13} />}
        </button>
        <button type="button" className={`v3-bs-pin ${fav ? "on" : ""}`} aria-label={fav ? `Unpin ${name}` : `Pin ${name}`}
          onClick={() => toggleFavorite({ type: "brand", id: name, label: name, href: "#/v3/brands" })}>
          <Icon name="star" size={13} />
        </button>
      </div>
    );
  };

  return (
    <div className="v3-bs" ref={ref}>
      <button type="button" className="v3-bs-trigger" aria-haspopup="listbox" aria-expanded={open}
        title={collapsed ? label : undefined} onClick={() => setOpen((o) => !o)}>
        <span className="v3-bs-dot">{activeBrand ? activeBrand.charAt(0) : <Icon name="layers" size={13} />}</span>
        {!collapsed && <><span className="v3-bs-label">{label}</span><Icon name="chevronDown" size={14} /></>}
      </button>
      {open && (
        <div className="v3-bs-pop" role="listbox" aria-label="Choose a brand">
          <div className="v3-bs-search">
            <Icon name="search" size={14} />
            <input autoFocus placeholder="Search brands…" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
          {!q && (
            <div className={`v3-bs-row ${activeBrand === null ? "active" : ""}`}>
              <button type="button" className="v3-bs-pick" onClick={() => choose(null)}>
                <span className="v3-bs-dot"><Icon name="layers" size={13} /></span>All brands
                {activeBrand === null && <Icon name="check" size={13} />}
              </button>
            </div>
          )}
          {pinned.length > 0 && <><div className="v3-bs-group">Pinned</div>{pinned.map(row)}</>}
          {recent.length > 0 && <><div className="v3-bs-group">Recent</div>{recent.map(row)}</>}
          {rest.length > 0 && <><div className="v3-bs-group">{pinned.length || recent.length ? "All" : "Brands"}</div>{rest.map(row)}</>}
          {pinned.length + recent.length + rest.length === 0 && <div className="v3-bs-empty">No brand matches "{query}".</div>}
        </div>
      )}
    </div>
  );
}
