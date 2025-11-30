/**
 * TypeScript types for Planning Precedent AI
 */

// Enums matching backend
export type Outcome =
  | 'Granted'
  | 'Refused'
  | 'Withdrawn'
  | 'Pending'
  | 'Appeal Allowed'
  | 'Appeal Dismissed';

export type DevelopmentType =
  | 'Rear Extension'
  | 'Side Extension'
  | 'Loft Conversion'
  | 'Dormer Window'
  | 'Basement/Subterranean'
  | 'Roof Extension'
  | 'Change of Use'
  | 'New Build'
  | 'Demolition'
  | 'Alterations'
  | 'Listed Building Consent'
  | 'Conservation Area'
  | 'Tree Works'
  | 'Advertisement'
  | 'Other';

export type ConservationAreaStatus =
  | 'Hampstead Conservation Area'
  | 'Belsize Conservation Area'
  | 'South Hampstead Conservation Area'
  | "Fitzjohn's/Netherhall Conservation Area"
  | 'Redington Frognal Conservation Area'
  | 'West Hampstead Conservation Area'
  | 'Swiss Cottage Conservation Area'
  | 'Primrose Hill Conservation Area'
  | 'Chalk Farm Conservation Area'
  | 'Camden Town Conservation Area'
  | 'Kentish Town Conservation Area'
  | 'Bloomsbury Conservation Area'
  | 'None';

// Core models
export interface PlanningDecision {
  id: number;
  case_reference: string;
  address: string;
  ward: string;
  postcode?: string;
  decision_date: string;
  outcome: Outcome;
  application_type: string;
  development_type?: DevelopmentType;
  property_type?: string;
  description: string;
  conservation_area?: ConservationAreaStatus;
  listed_building: boolean;
  article_4: boolean;
  full_text?: string;
  officer_report_url?: string;
  decision_notice_url?: string;
  created_at: string;
  updated_at: string;
}

export interface PrecedentMatch {
  decision: PlanningDecision;
  similarity_score: number;
  relevant_excerpt: string;
  matched_chunk_id: number;
  key_policies: string[];
}

// Search types
export interface SearchFilters {
  wards?: string[];
  outcome?: Outcome;
  development_types?: DevelopmentType[];
  property_types?: string[];
  conservation_areas?: ConservationAreaStatus[];
  listed_building_only?: boolean;
  date_from?: string;
  date_to?: string;
  postcode_prefix?: string;
}

export interface SearchQuery {
  query: string;
  filters?: SearchFilters;
  limit?: number;
  include_refused?: boolean;
  similarity_threshold?: number;
}

export interface SearchResult {
  query: string;
  total_matches: number;
  precedents: PrecedentMatch[];
  search_time_ms: number;
  filters_applied?: SearchFilters;
}

// Analysis types
export interface AnalysisRequest {
  query: string;
  address?: string;
  ward?: string;
  conservation_area?: ConservationAreaStatus;
  include_counter_arguments?: boolean;
  case_references?: string[];
}

export interface ArgumentSection {
  heading: string;
  content: string;
  supporting_cases: string[];
  policy_references: string[];
  officer_quotes: Array<{ case: string; quote: string }>;
}

export interface RiskAssessment {
  approval_likelihood: 'High' | 'Medium' | 'Low';
  confidence_score: number;
  key_risks: string[];
  mitigation_suggestions: string[];
  similar_refusals: string[];
}

export interface AnalysisResponse {
  summary: string;
  recommendation: string;
  arguments: ArgumentSection[];
  risk_assessment: RiskAssessment;
  precedents_used: PrecedentMatch[];
  policies_referenced: string[];
  generated_at: string;
  model_version: string;
}

// Reference data types
export interface WardInfo {
  name: string;
  case_count: number;
  approval_rate: string;
  common_developments: DevelopmentType[];
  conservation_areas: string[];
}

export interface DatabaseStats {
  total_decisions: number;
  granted_count: number;
  refused_count: number;
  date_range_start: string;
  date_range_end: string;
  wards_covered: string[];
  last_updated: string;
  total_chunks: number;
}

// UI State types
export interface SearchState {
  query: string;
  filters: SearchFilters;
  results: SearchResult | null;
  isLoading: boolean;
  error: string | null;
}

export interface AnalysisState {
  request: AnalysisRequest | null;
  response: AnalysisResponse | null;
  isLoading: boolean;
  error: string | null;
}

// API response wrapper
export interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}
