/**
 * API client for Planning Precedent AI backend
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import {
  SearchQuery,
  SearchResult,
  AnalysisRequest,
  AnalysisResponse,
  PlanningDecision,
  DatabaseStats,
  WardInfo,
} from '@/types';

// Create axios instance
const api: AxiosInstance = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  timeout: 60000, // 60 seconds for AI operations
  headers: {
    'Content-Type': 'application/json',
  },
});

// Error handler
const handleError = (error: AxiosError): never => {
  if (error.response) {
    const message =
      (error.response.data as { detail?: string })?.detail ||
      'An error occurred';
    throw new Error(message);
  } else if (error.request) {
    throw new Error('Unable to connect to the server. Please try again.');
  } else {
    throw new Error(error.message);
  }
};

// ==================== Search API ====================

export const searchPrecedents = async (
  query: SearchQuery
): Promise<SearchResult> => {
  try {
    const response = await api.post<SearchResult>('/api/v1/search', query);
    return response.data;
  } catch (error) {
    throw handleError(error as AxiosError);
  }
};

export const quickSearch = async (
  q: string,
  ward?: string,
  limit: number = 5
): Promise<SearchResult> => {
  try {
    const params = new URLSearchParams({ q, limit: limit.toString() });
    if (ward) params.append('ward', ward);

    const response = await api.get<SearchResult>(
      `/api/v1/search/quick?${params}`
    );
    return response.data;
  } catch (error) {
    throw handleError(error as AxiosError);
  }
};

export const searchByAddress = async (
  address: string
): Promise<{
  address_searched: string;
  exact_matches: PlanningDecision[];
  nearby_decisions: PlanningDecision[];
  total_found: number;
}> => {
  try {
    const response = await api.get('/api/v1/search/by-address', {
      params: { address },
    });
    return response.data;
  } catch (error) {
    throw handleError(error as AxiosError);
  }
};

export const findSimilarCases = async (
  caseReference: string,
  limit: number = 10
): Promise<{
  original_case: PlanningDecision;
  similar_cases: Array<{
    decision: PlanningDecision;
    similarity_score: number;
  }>;
}> => {
  try {
    const response = await api.get(
      `/api/v1/search/similar-to/${encodeURIComponent(caseReference)}`,
      { params: { limit } }
    );
    return response.data;
  } catch (error) {
    throw handleError(error as AxiosError);
  }
};

// ==================== Analysis API ====================

export const analyseDevelopment = async (
  request: AnalysisRequest
): Promise<AnalysisResponse> => {
  try {
    const response = await api.post<AnalysisResponse>(
      '/api/v1/analyse',
      request
    );
    return response.data;
  } catch (error) {
    throw handleError(error as AxiosError);
  }
};

export const quickAnalysis = async (
  query: string,
  ward?: string
): Promise<{
  summary: string;
  recommendation: string;
  approval_likelihood: string;
  confidence: number;
  key_precedents: Array<{
    case_reference: string;
    address: string;
    similarity: number;
  }>;
  key_risks: string[];
}> => {
  try {
    const params = new URLSearchParams({ query });
    if (ward) params.append('ward', ward);

    const response = await api.post(`/api/v1/analyse/quick?${params}`);
    return response.data;
  } catch (error) {
    throw handleError(error as AxiosError);
  }
};

export const generateAppealArgument = async (
  caseReference: string,
  refusalReasons: string
): Promise<{
  refused_case: {
    reference: string;
    address: string;
    refusal_reasons: string;
  };
  similar_approved_cases: Array<{
    reference: string;
    address: string;
    similarity: number;
    decision_date: string;
  }>;
  appeal_argument: string;
  strength_assessment: {
    rating: string;
    score: number;
    reason: string;
  };
}> => {
  try {
    const response = await api.post('/api/v1/analyse/appeal', {
      case_reference: caseReference,
      refusal_reasons: refusalReasons,
    });
    return response.data;
  } catch (error) {
    throw handleError(error as AxiosError);
  }
};

// ==================== Cases API ====================

export const getCaseDetail = async (
  caseReference: string
): Promise<{
  decision: PlanningDecision;
  full_text: string;
  related_cases: PlanningDecision[];
  similar_cases: Array<{
    decision: PlanningDecision;
    similarity_score: number;
  }>;
  key_policies: string[];
  officer_conclusions?: string;
}> => {
  try {
    const response = await api.get(
      `/api/v1/cases/${encodeURIComponent(caseReference)}`
    );
    return response.data;
  } catch (error) {
    throw handleError(error as AxiosError);
  }
};

export const listCases = async (params: {
  ward?: string;
  outcome?: string;
  development_type?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}): Promise<{
  cases: PlanningDecision[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}> => {
  try {
    const response = await api.get('/api/v1/cases', { params });
    return response.data;
  } catch (error) {
    throw handleError(error as AxiosError);
  }
};

export const getCaseTimeline = async (
  caseReference: string
): Promise<{
  address: string;
  postcode?: string;
  timeline: Array<{
    case_reference: string;
    date: string;
    description: string;
    outcome: string;
    development_type?: string;
  }>;
  total_applications: number;
}> => {
  try {
    const response = await api.get(
      `/api/v1/cases/${encodeURIComponent(caseReference)}/timeline`
    );
    return response.data;
  } catch (error) {
    throw handleError(error as AxiosError);
  }
};

// ==================== Export API ====================

export const exportAnalysisPdf = async (
  siteAddress?: string,
  clientName?: string
): Promise<Blob> => {
  try {
    const response = await api.post(
      '/api/v1/export/pdf',
      {
        site_address: siteAddress,
        client_name: clientName,
        format: 'pdf',
      },
      { responseType: 'blob' }
    );
    return response.data;
  } catch (error) {
    throw handleError(error as AxiosError);
  }
};

export const exportPrecedentsList = async (
  caseReferences: string[],
  format: 'pdf' | 'html' = 'pdf'
): Promise<Blob> => {
  try {
    const response = await api.post(
      '/api/v1/export/precedents',
      { case_references: caseReferences, format },
      { responseType: 'blob' }
    );
    return response.data;
  } catch (error) {
    throw handleError(error as AxiosError);
  }
};

// ==================== Reference Data API ====================

export const getStats = async (): Promise<DatabaseStats> => {
  try {
    const response = await api.get<DatabaseStats>('/api/v1/stats');
    return response.data;
  } catch (error) {
    throw handleError(error as AxiosError);
  }
};

export const getWards = async (): Promise<{
  wards: WardInfo[];
  total_wards: number;
}> => {
  try {
    const response = await api.get('/api/v1/wards');
    return response.data;
  } catch (error) {
    throw handleError(error as AxiosError);
  }
};

export const getWardDetail = async (wardName: string): Promise<WardInfo> => {
  try {
    const response = await api.get<WardInfo>(
      `/api/v1/wards/${encodeURIComponent(wardName)}`
    );
    return response.data;
  } catch (error) {
    throw handleError(error as AxiosError);
  }
};

export const getDevelopmentTypes = async (): Promise<{
  development_types: Array<{
    value: string;
    name: string;
    description: string;
  }>;
}> => {
  try {
    const response = await api.get('/api/v1/search/development-types');
    return response.data;
  } catch (error) {
    throw handleError(error as AxiosError);
  }
};

export const getConservationAreas = async (): Promise<{
  conservation_areas: Array<{ value: string; name: string }>;
}> => {
  try {
    const response = await api.get('/api/v1/search/conservation-areas');
    return response.data;
  } catch (error) {
    throw handleError(error as AxiosError);
  }
};

export const getPolicies = async (): Promise<{
  camden_local_plan: {
    title: string;
    key_policies: Array<{
      code: string;
      title: string;
      summary: string;
    }>;
  };
  london_plan: {
    title: string;
    key_policies: Array<{
      code: string;
      title: string;
      summary: string;
    }>;
  };
  nppf: {
    title: string;
    key_paragraphs: Array<{
      paragraph: string;
      summary: string;
    }>;
  };
}> => {
  try {
    const response = await api.get('/api/v1/policies');
    return response.data;
  } catch (error) {
    throw handleError(error as AxiosError);
  }
};

export const healthCheck = async (): Promise<{
  status: string;
  components: Record<string, { status: string; message?: string }>;
}> => {
  try {
    const response = await api.get('/api/v1/health');
    return response.data;
  } catch (error) {
    throw handleError(error as AxiosError);
  }
};

export default api;
