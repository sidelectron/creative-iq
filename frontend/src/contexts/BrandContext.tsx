import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useAuth } from "./AuthContext";

export type BrandListItem = {
  id: string;
  name: string;
  industry: string | null;
  created_at: string;
  role: string;
};

type Paginated<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

type BrandContextValue = {
  brands: BrandListItem[];
  brandsLoading: boolean;
  brandId: string | null;
  setBrandId: (id: string | null) => void;
  refetchBrands: () => Promise<unknown>;
};

const STORAGE_KEY = "ci_selected_brand_id";

const BrandContext = createContext<BrandContextValue | null>(null);

export function BrandProvider({ children }: { children: ReactNode }): React.ReactElement {
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [brandId, setBrandIdState] = useState<string | null>(() =>
    sessionStorage.getItem(STORAGE_KEY),
  );

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["brands"],
    queryFn: async () => {
      const { data: res } = await api.get<Paginated<BrandListItem>>("/api/v1/brands", {
        params: { page: 1, page_size: 100 },
      });
      return res;
    },
    enabled: isAuthenticated,
  });

  const brands = data?.items ?? [];

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated) {
      setBrandIdState(null);
      sessionStorage.removeItem(STORAGE_KEY);
      return;
    }
    if (brands.length === 0) return;
    const stored = sessionStorage.getItem(STORAGE_KEY);
    if (stored && brands.some((b) => b.id === stored)) return;
    if (!stored || !brands.some((b) => b.id === stored)) {
      const first = brands[0].id;
      sessionStorage.setItem(STORAGE_KEY, first);
      setBrandIdState(first);
    }
  }, [authLoading, isAuthenticated, brands]);

  const setBrandId = useCallback((id: string | null) => {
    setBrandIdState(id);
    if (id) sessionStorage.setItem(STORAGE_KEY, id);
    else sessionStorage.removeItem(STORAGE_KEY);
  }, []);

  const value = useMemo(
    () => ({
      brands,
      brandsLoading: isLoading,
      brandId,
      setBrandId,
      refetchBrands: refetch,
    }),
    [brands, isLoading, brandId, setBrandId, refetch],
  );

  return <BrandContext.Provider value={value}>{children}</BrandContext.Provider>;
}

export function useBrand(): BrandContextValue {
  const ctx = useContext(BrandContext);
  if (!ctx) throw new Error("useBrand must be used within BrandProvider");
  return ctx;
}
