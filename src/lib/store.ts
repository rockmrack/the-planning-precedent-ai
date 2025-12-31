/**
 * Zustand store for global state management
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import {
  SearchQuery,
  SearchResult,
  AnalysisResponse,
  PlanningDecision,
  SearchFilters,
} from '@/types';

// Search store
interface SearchStore {
  // Query state
  query: string;
  filters: SearchFilters;
  results: SearchResult | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  setQuery: (query: string) => void;
  setFilters: (filters: Partial<SearchFilters>) => void;
  clearFilters: () => void;
  setResults: (results: SearchResult | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useSearchStore = create<SearchStore>((set) => ({
  query: '',
  filters: {},
  results: null,
  isLoading: false,
  error: null,

  setQuery: (query) => set({ query }),
  setFilters: (filters) =>
    set((state) => ({ filters: { ...state.filters, ...filters } })),
  clearFilters: () => set({ filters: {} }),
  setResults: (results) => set({ results }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  reset: () =>
    set({
      query: '',
      filters: {},
      results: null,
      isLoading: false,
      error: null,
    }),
}));

// Analysis store
interface AnalysisStore {
  // State
  response: AnalysisResponse | null;
  isLoading: boolean;
  error: string | null;

  // Selected precedents
  selectedPrecedents: string[];

  // Actions
  setResponse: (response: AnalysisResponse | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  togglePrecedent: (caseRef: string) => void;
  clearSelection: () => void;
  reset: () => void;
}

export const useAnalysisStore = create<AnalysisStore>((set) => ({
  response: null,
  isLoading: false,
  error: null,
  selectedPrecedents: [],

  setResponse: (response) => set({ response }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  togglePrecedent: (caseRef) =>
    set((state) => ({
      selectedPrecedents: state.selectedPrecedents.includes(caseRef)
        ? state.selectedPrecedents.filter((ref) => ref !== caseRef)
        : [...state.selectedPrecedents, caseRef],
    })),
  clearSelection: () => set({ selectedPrecedents: [] }),
  reset: () =>
    set({
      response: null,
      isLoading: false,
      error: null,
      selectedPrecedents: [],
    }),
}));

// Recent searches store (persisted)
interface RecentSearchesStore {
  searches: Array<{
    query: string;
    timestamp: number;
  }>;
  addSearch: (query: string) => void;
  clearSearches: () => void;
}

export const useRecentSearchesStore = create<RecentSearchesStore>()(
  persist(
    (set) => ({
      searches: [],
      addSearch: (query) =>
        set((state) => ({
          searches: [
            { query, timestamp: Date.now() },
            ...state.searches.filter((s) => s.query !== query),
          ].slice(0, 10), // Keep last 10
        })),
      clearSearches: () => set({ searches: [] }),
    }),
    {
      name: 'planning-recent-searches',
    }
  )
);

// Saved cases store (persisted)
interface SavedCasesStore {
  cases: PlanningDecision[];
  addCase: (decision: PlanningDecision) => void;
  removeCase: (caseRef: string) => void;
  isSaved: (caseRef: string) => boolean;
  clearCases: () => void;
}

export const useSavedCasesStore = create<SavedCasesStore>()(
  persist(
    (set, get) => ({
      cases: [],
      addCase: (decision) =>
        set((state) => {
          if (state.cases.some((c) => c.case_reference === decision.case_reference)) {
            return state;
          }
          return { cases: [...state.cases, decision] };
        }),
      removeCase: (caseRef) =>
        set((state) => ({
          cases: state.cases.filter((c) => c.case_reference !== caseRef),
        })),
      isSaved: (caseRef) =>
        get().cases.some((c) => c.case_reference === caseRef),
      clearCases: () => set({ cases: [] }),
    }),
    {
      name: 'planning-saved-cases',
    }
  )
);

// UI preferences store (persisted)
interface UIPreferencesStore {
  sidebarOpen: boolean;
  resultsView: 'list' | 'grid';
  darkMode: boolean;
  toggleSidebar: () => void;
  setResultsView: (view: 'list' | 'grid') => void;
  toggleDarkMode: () => void;
}

export const useUIPreferencesStore = create<UIPreferencesStore>()(
  persist(
    (set) => ({
      sidebarOpen: true,
      resultsView: 'list',
      darkMode: false,
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      setResultsView: (resultsView) => set({ resultsView }),
      toggleDarkMode: () => set((state) => ({ darkMode: !state.darkMode })),
    }),
    {
      name: 'planning-ui-preferences',
    }
  )
);
