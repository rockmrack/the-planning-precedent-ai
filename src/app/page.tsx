'use client';

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import {
  Search,
  Building2,
  FileText,
  TrendingUp,
  Shield,
  Sparkles,
  ArrowRight,
  CheckCircle,
  AlertCircle,
  Clock,
  MapPin,
  Calendar,
  ExternalLink,
} from 'lucide-react';
import { searchPrecedents, getStats, analyseDevelopment } from '@/lib/api';
import { SearchResult, PrecedentMatch, AnalysisResponse } from '@/types';
import { cn, formatDate, formatSimilarity, getOutcomeColour, getRiskColour } from '@/lib/utils';
import { useSearchStore, useRecentSearchesStore } from '@/lib/store';

export default function HomePage() {
  const [query, setQuery] = useState('');
  const [showResults, setShowResults] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResponse | null>(null);
  const { addSearch } = useRecentSearchesStore();

  // Fetch database stats
  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: getStats,
  });

  // Search mutation
  const searchMutation = useMutation({
    mutationFn: (searchQuery: string) =>
      searchPrecedents({
        query: searchQuery,
        limit: 10,
        similarity_threshold: 0.65,
      }),
    onSuccess: (data) => {
      setShowResults(true);
      addSearch(query);
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });

  // Analysis mutation
  const analysisMutation = useMutation({
    mutationFn: (searchQuery: string) =>
      analyseDevelopment({
        query: searchQuery,
        include_counter_arguments: true,
      }),
    onSuccess: (data) => {
      setAnalysisResult(data);
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim().length < 10) {
      toast.error('Please provide more details about your proposed development');
      return;
    }
    searchMutation.mutate(query);
  };

  const handleAnalyse = () => {
    if (!searchMutation.data?.precedents.length) {
      toast.error('Please search for precedents first');
      return;
    }
    analysisMutation.mutate(query);
  };

  return (
    <div className="min-h-screen">
      {/* Navigation */}
      <nav className="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2">
              <Building2 className="w-8 h-8 text-primary-600" />
              <span className="text-xl font-bold text-slate-900">
                Planning Precedent AI
              </span>
            </div>
            <div className="flex items-center gap-4">
              <a href="/cases" className="text-slate-600 hover:text-slate-900">
                Browse Cases
              </a>
              <a href="/wards" className="text-slate-600 hover:text-slate-900">
                Wards
              </a>
              <a href="/policies" className="text-slate-600 hover:text-slate-900">
                Policies
              </a>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="bg-gradient-to-b from-slate-900 to-slate-800 text-white py-20">
        <div className="max-w-4xl mx-auto px-4 text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <h1 className="text-4xl md:text-5xl font-bold mb-6">
              Find Winning Precedents for Your
              <span className="text-primary-400"> Planning Application</span>
            </h1>
            <p className="text-xl text-slate-300 mb-8">
              AI-powered search across {stats?.total_decisions.toLocaleString() || '10,000'}+ Camden Council
              planning decisions. Get the evidence you need to support your application.
            </p>
          </motion.div>

          {/* Search Box */}
          <motion.form
            onSubmit={handleSearch}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="max-w-3xl mx-auto"
          >
            <div className="relative">
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Describe your proposed development... e.g., 'Single storey rear extension in Belsize Park conservation area with glazed roof and zinc cladding'"
                rows={3}
                className="w-full px-6 py-4 text-lg text-slate-900 bg-white rounded-xl border-2 border-transparent focus:border-primary-400 focus:outline-none focus:ring-4 focus:ring-primary-400/20 resize-none"
              />
              <button
                type="submit"
                disabled={searchMutation.isPending}
                className="absolute right-3 bottom-3 btn-primary btn-lg"
              >
                {searchMutation.isPending ? (
                  <span className="flex items-center gap-2">
                    <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                        fill="none"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    Searching...
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <Search className="w-5 h-5" />
                    Find Precedents
                  </span>
                )}
              </button>
            </div>
          </motion.form>

          {/* Quick Stats */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.4 }}
            className="flex flex-wrap justify-center gap-8 mt-12 text-sm text-slate-400"
          >
            <div className="flex items-center gap-2">
              <FileText className="w-5 h-5" />
              <span>{stats?.total_decisions.toLocaleString() || '10,000'}+ decisions</span>
            </div>
            <div className="flex items-center gap-2">
              <MapPin className="w-5 h-5" />
              <span>{stats?.wards_covered.length || 12} Camden wards</span>
            </div>
            <div className="flex items-center gap-2">
              <Calendar className="w-5 h-5" />
              <span>2015 - Present</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle className="w-5 h-5" />
              <span>{stats ? Math.round((stats.granted_count / stats.total_decisions) * 100) : 75}% approval rate</span>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Results Section */}
      <AnimatePresence>
        {showResults && searchMutation.data && (
          <motion.section
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="bg-white border-b border-slate-200"
          >
            <div className="max-w-6xl mx-auto px-4 py-12">
              {/* Results Header */}
              <div className="flex items-center justify-between mb-8">
                <div>
                  <h2 className="heading-2">
                    Found {searchMutation.data.total_matches} Precedents
                  </h2>
                  <p className="text-muted mt-1">
                    Search completed in {searchMutation.data.search_time_ms.toFixed(0)}ms
                  </p>
                </div>
                <button
                  onClick={handleAnalyse}
                  disabled={analysisMutation.isPending}
                  className="btn-primary btn-lg flex items-center gap-2"
                >
                  {analysisMutation.isPending ? (
                    <>
                      <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                          fill="none"
                        />
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                        />
                      </svg>
                      Analysing...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-5 h-5" />
                      Generate Arguments
                    </>
                  )}
                </button>
              </div>

              {/* Precedent Cards */}
              <div className="grid gap-4">
                {searchMutation.data.precedents.map((precedent, index) => (
                  <PrecedentCard key={precedent.decision.id} precedent={precedent} index={index} />
                ))}
              </div>
            </div>
          </motion.section>
        )}
      </AnimatePresence>

      {/* Analysis Results */}
      <AnimatePresence>
        {analysisResult && (
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="bg-slate-50 py-12"
          >
            <div className="max-w-4xl mx-auto px-4">
              <AnalysisResults analysis={analysisResult} />
            </div>
          </motion.section>
        )}
      </AnimatePresence>

      {/* Features Section */}
      <section className="py-20 bg-white">
        <div className="max-w-6xl mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="heading-1 mb-4">How It Works</h2>
            <p className="text-xl text-muted max-w-2xl mx-auto">
              Our AI analyses 10 years of planning decisions to find the precedents
              that will strengthen your application.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <FeatureCard
              icon={<Search className="w-8 h-8 text-primary-600" />}
              title="Semantic Search"
              description="Describe your development in plain English. Our AI understands context, not just keywords."
            />
            <FeatureCard
              icon={<FileText className="w-8 h-8 text-primary-600" />}
              title="Find Precedents"
              description="Discover approved applications with similar characteristics - extensions, dormers, basements, and more."
            />
            <FeatureCard
              icon={<Sparkles className="w-8 h-8 text-primary-600" />}
              title="Generate Arguments"
              description="Get AI-written planning arguments citing specific cases and officer wording."
            />
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-primary-600 text-white">
        <div className="max-w-4xl mx-auto px-4 text-center">
          <h2 className="text-3xl font-bold mb-6">
            Stop Researching. Start Building.
          </h2>
          <p className="text-xl text-primary-100 mb-8">
            Architects charge £200/hour. Our AI does 10 hours of research in seconds.
          </p>
          <button
            onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
            className="bg-white text-primary-600 px-8 py-4 rounded-xl font-semibold text-lg hover:bg-primary-50 transition-colors"
          >
            Try Your First Search Free
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-slate-900 text-slate-400 py-12">
        <div className="max-w-6xl mx-auto px-4">
          <div className="grid md:grid-cols-4 gap-8">
            <div>
              <div className="flex items-center gap-2 text-white mb-4">
                <Building2 className="w-6 h-6" />
                <span className="font-bold">Planning Precedent AI</span>
              </div>
              <p className="text-sm">
                AI-powered planning precedent search for London Borough of Camden.
              </p>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Product</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="/search" className="hover:text-white">Search</a></li>
                <li><a href="/cases" className="hover:text-white">Browse Cases</a></li>
                <li><a href="/wards" className="hover:text-white">Wards</a></li>
                <li><a href="/policies" className="hover:text-white">Policies</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Resources</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="https://www.camden.gov.uk/planning" className="hover:text-white flex items-center gap-1">
                  Camden Planning <ExternalLink className="w-3 h-3" />
                </a></li>
                <li><a href="/policies" className="hover:text-white">Planning Policies</a></li>
                <li><a href="/conservation-areas" className="hover:text-white">Conservation Areas</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Legal</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="/privacy" className="hover:text-white">Privacy Policy</a></li>
                <li><a href="/terms" className="hover:text-white">Terms of Service</a></li>
                <li><a href="/disclaimer" className="hover:text-white">Disclaimer</a></li>
              </ul>
            </div>
          </div>
          <div className="border-t border-slate-800 mt-12 pt-8 text-sm text-center">
            <p>&copy; {new Date().getFullYear()} Planning Precedent AI. All rights reserved.</p>
            <p className="mt-2 text-slate-500">
              This service is not affiliated with London Borough of Camden.
              Planning decisions are provided for informational purposes only.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

// Precedent Card Component
function PrecedentCard({ precedent, index }: { precedent: PrecedentMatch; index: number }) {
  const { decision, similarity_score, relevant_excerpt, key_policies } = precedent;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.1 }}
      className="result-card"
    >
      <div className="card-body">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <span className="font-mono text-primary-600 font-semibold">
                {decision.case_reference}
              </span>
              <span className={cn('badge', getOutcomeColour(decision.outcome))}>
                {decision.outcome}
              </span>
              <span className="text-sm text-muted">
                {formatDate(decision.decision_date)}
              </span>
            </div>
            <h3 className="heading-4 mb-1">{decision.address}</h3>
            <p className="text-muted text-sm mb-3">{decision.description}</p>

            {/* Relevant excerpt */}
            <div className="bg-slate-50 rounded-lg p-3 text-sm text-slate-700 mb-3">
              <p className="italic">"{relevant_excerpt}"</p>
            </div>

            {/* Policies */}
            {key_policies.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {key_policies.map((policy, i) => (
                  <span key={i} className="policy-tag">{policy}</span>
                ))}
              </div>
            )}
          </div>

          {/* Similarity score */}
          <div className="ml-4 text-right">
            <div className={cn(
              'text-2xl font-bold',
              similarity_score >= 0.8 ? 'text-green-600' :
              similarity_score >= 0.6 ? 'text-amber-600' : 'text-slate-400'
            )}>
              {Math.round(similarity_score * 100)}%
            </div>
            <div className="text-xs text-muted">match</div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

// Analysis Results Component
function AnalysisResults({ analysis }: { analysis: AnalysisResponse }) {
  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="card">
        <div className="card-header">
          <h3 className="heading-3 flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-primary-600" />
            AI Analysis Summary
          </h3>
        </div>
        <div className="card-body">
          <p className="text-lg mb-4">{analysis.summary}</p>
          <p className="text-muted">{analysis.recommendation}</p>
        </div>
      </div>

      {/* Risk Assessment */}
      <div className={cn(
        'card border-l-4',
        getRiskColour(analysis.risk_assessment.approval_likelihood)
      )}>
        <div className="card-body">
          <div className="flex items-center justify-between mb-4">
            <h3 className="heading-3 flex items-center gap-2">
              <Shield className="w-5 h-5" />
              Risk Assessment
            </h3>
            <span className="text-2xl font-bold">
              {analysis.risk_assessment.approval_likelihood} Likelihood
            </span>
          </div>
          <div className="w-full bg-slate-200 rounded-full h-2 mb-4">
            <div
              className={cn(
                'h-2 rounded-full',
                analysis.risk_assessment.approval_likelihood === 'High' ? 'bg-green-500' :
                analysis.risk_assessment.approval_likelihood === 'Medium' ? 'bg-amber-500' : 'bg-red-500'
              )}
              style={{ width: `${analysis.risk_assessment.confidence_score * 100}%` }}
            />
          </div>
          {analysis.risk_assessment.key_risks.length > 0 && (
            <div className="mt-4">
              <h4 className="font-medium mb-2">Key Risks:</h4>
              <ul className="list-disc list-inside text-muted">
                {analysis.risk_assessment.key_risks.map((risk, i) => (
                  <li key={i}>{risk}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* Arguments */}
      <div className="card">
        <div className="card-header">
          <h3 className="heading-3">Planning Arguments</h3>
        </div>
        <div className="card-body space-y-6">
          {analysis.arguments.map((arg, i) => (
            <div key={i} className="border-b border-slate-100 last:border-0 pb-6 last:pb-0">
              <h4 className="heading-4 mb-2">{arg.heading}</h4>
              <p className="text-muted mb-3">{arg.content}</p>
              {arg.officer_quotes.length > 0 && (
                <div className="bg-slate-50 rounded-lg p-3 text-sm italic">
                  "{arg.officer_quotes[0].quote}"
                  <span className="text-primary-600 ml-2">— {arg.officer_quotes[0].case}</span>
                </div>
              )}
              {arg.policy_references.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-3">
                  {arg.policy_references.map((policy, j) => (
                    <span key={j} className="policy-tag">{policy}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Export Button */}
      <div className="flex justify-center">
        <button className="btn-primary btn-lg flex items-center gap-2">
          <FileText className="w-5 h-5" />
          Export as PDF Report
        </button>
      </div>
    </div>
  );
}

// Feature Card Component
function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="text-center p-6">
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-xl bg-primary-50 mb-4">
        {icon}
      </div>
      <h3 className="heading-3 mb-2">{title}</h3>
      <p className="text-muted">{description}</p>
    </div>
  );
}
