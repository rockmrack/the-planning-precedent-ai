/**
 * Utility functions for Planning Precedent AI
 */

import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { format, parseISO } from 'date-fns';

/**
 * Merge Tailwind CSS classes with clsx
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format a date string for display
 */
export function formatDate(dateString: string | Date): string {
  const date = typeof dateString === 'string' ? parseISO(dateString) : dateString;
  return format(date, 'd MMMM yyyy');
}

/**
 * Format a date string as short format
 */
export function formatDateShort(dateString: string | Date): string {
  const date = typeof dateString === 'string' ? parseISO(dateString) : dateString;
  return format(date, 'dd/MM/yyyy');
}

/**
 * Format percentage for display
 */
export function formatPercentage(value: number): string {
  return `${Math.round(value * 100)}%`;
}

/**
 * Format similarity score
 */
export function formatSimilarity(score: number): string {
  return `${Math.round(score * 100)}% match`;
}

/**
 * Get colour class for outcome
 */
export function getOutcomeColour(outcome: string): string {
  switch (outcome) {
    case 'Granted':
    case 'Appeal Allowed':
      return 'text-green-600 bg-green-50';
    case 'Refused':
    case 'Appeal Dismissed':
      return 'text-red-600 bg-red-50';
    case 'Withdrawn':
      return 'text-gray-600 bg-gray-50';
    case 'Pending':
      return 'text-amber-600 bg-amber-50';
    default:
      return 'text-gray-600 bg-gray-50';
  }
}

/**
 * Get colour class for risk level
 */
export function getRiskColour(risk: 'High' | 'Medium' | 'Low'): string {
  switch (risk) {
    case 'High':
      return 'text-green-600 bg-green-50 border-green-200';
    case 'Medium':
      return 'text-amber-600 bg-amber-50 border-amber-200';
    case 'Low':
      return 'text-red-600 bg-red-50 border-red-200';
    default:
      return 'text-gray-600 bg-gray-50 border-gray-200';
  }
}

/**
 * Get confidence level text
 */
export function getConfidenceText(score: number): string {
  if (score >= 0.8) return 'Very High';
  if (score >= 0.6) return 'High';
  if (score >= 0.4) return 'Moderate';
  if (score >= 0.2) return 'Low';
  return 'Very Low';
}

/**
 * Truncate text with ellipsis
 */
export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - 3) + '...';
}

/**
 * Extract postcode from address
 */
export function extractPostcode(address: string): string | null {
  const match = address.match(/([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})/i);
  return match ? match[1].toUpperCase() : null;
}

/**
 * Format case reference for display
 */
export function formatCaseReference(ref: string): string {
  return ref.toUpperCase();
}

/**
 * Generate a download filename
 */
export function generateFilename(prefix: string, extension: string): string {
  const timestamp = format(new Date(), 'yyyyMMdd_HHmmss');
  return `${prefix}_${timestamp}.${extension}`;
}

/**
 * Download a blob as a file
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

/**
 * Parse development type for display
 */
export function formatDevelopmentType(type: string): string {
  // Convert enum value to readable text
  return type.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
}

/**
 * Get icon name for development type
 */
export function getDevelopmentTypeIcon(type: string): string {
  const icons: Record<string, string> = {
    'Rear Extension': 'arrow-right',
    'Side Extension': 'arrow-left',
    'Loft Conversion': 'chevron-up',
    'Dormer Window': 'square',
    'Basement/Subterranean': 'arrow-down',
    'Roof Extension': 'chevron-up',
    'Change of Use': 'refresh',
    'New Build': 'plus-circle',
    'Demolition': 'trash',
    'Alterations': 'edit',
    'Listed Building Consent': 'star',
    'Tree Works': 'tree',
    'Advertisement': 'image',
    Other: 'circle',
  };
  return icons[type] || 'circle';
}

/**
 * Validate UK postcode format
 */
export function isValidPostcode(postcode: string): boolean {
  const pattern = /^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$/i;
  return pattern.test(postcode.trim());
}

/**
 * Validate case reference format
 */
export function isValidCaseReference(ref: string): boolean {
  const pattern = /^\d{4}\/\d{4,5}\/[A-Z]+$/i;
  return pattern.test(ref.trim());
}

/**
 * Debounce function
 */
export function debounce<T extends (...args: unknown[]) => unknown>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeoutId: NodeJS.Timeout | null = null;

  return (...args: Parameters<T>) => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }

    timeoutId = setTimeout(() => {
      func(...args);
    }, wait);
  };
}

/**
 * Copy text to clipboard
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/**
 * Generate share URL for a case
 */
export function generateShareUrl(caseReference: string): string {
  const baseUrl = typeof window !== 'undefined' ? window.location.origin : '';
  return `${baseUrl}/cases/${encodeURIComponent(caseReference)}`;
}
