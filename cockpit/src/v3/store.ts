import { useCallback, useEffect, useState } from "react";

/** Per-browser preferences for the redesigned Cockpit: which brand is active, which brands
 *  were used recently, what's pinned, and whether the rail is pinned open. These are
 *  conveniences, not records, so localStorage is the right home; every read and write
 *  tolerates storage being unavailable (private windows, blocked site data). */

export type Favorite = { type: "brand" | "app" | "campaign"; id: string; label: string; href: string };

const KEYS = {
  activeBrand: "omni-v3-active-brand",
  recentBrands: "omni-v3-recent-brands",
  favorites: "omni-v3-favorites",
  railPinned: "omni-v3-rail-pinned",
} as const;

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw === null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown): void {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage unavailable */ }
}

function usePersisted<T>(key: string, fallback: T): [T, (next: T | ((prev: T) => T)) => void] {
  const [value, setValue] = useState<T>(() => read(key, fallback));
  useEffect(() => { write(key, value); }, [key, value]);
  return [value, setValue];
}

const UNSET = "__unset__";

/** `activeBrand === null` means "All brands" (BR3). Until the user has ever chosen, the
 *  default is the most recently used brand, or the only brand when there's just one (BR2). */
export function useBrandScope(allBrands: string[]) {
  const [stored, setActive] = usePersisted<string | null>(KEYS.activeBrand, UNSET);
  const [recentBrands, setRecent] = usePersisted<string[]>(KEYS.recentBrands, []);
  const activeBrand = stored !== UNSET
    ? stored
    : recentBrands[0] ?? (allBrands.length === 1 ? allBrands[0] : null);

  const selectBrand = useCallback((brand: string | null) => {
    setActive(brand);
    if (brand) setRecent((prev) => [brand, ...prev.filter((b) => b !== brand)].slice(0, 5));
  }, [setActive, setRecent]);

  return { activeBrand, recentBrands, selectBrand };
}

export function useFavorites() {
  const [favorites, setFavorites] = usePersisted<Favorite[]>(KEYS.favorites, []);
  const isFavorite = useCallback(
    (type: Favorite["type"], id: string) => favorites.some((f) => f.type === type && f.id === id),
    [favorites],
  );
  const toggleFavorite = useCallback((fav: Favorite) => {
    setFavorites((prev) => prev.some((f) => f.type === fav.type && f.id === fav.id)
      ? prev.filter((f) => !(f.type === fav.type && f.id === fav.id))
      : [...prev, fav]);
  }, [setFavorites]);
  return { favorites, isFavorite, toggleFavorite };
}

export function useRailPinned() {
  return usePersisted<boolean>(KEYS.railPinned, false);
}
