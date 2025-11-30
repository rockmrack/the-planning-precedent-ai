"""
Predictive Analytics Engine for Planning Decisions
Uses historical data patterns to predict approval likelihood and trends

Features:
1. Approval probability prediction
2. Trend analysis over time
3. Ward-level analytics
4. Development type success patterns
5. Seasonal patterns
6. Officer decision patterns
"""

import asyncio
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import statistics

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


@dataclass
class PredictionFactors:
    """Factors used in prediction calculation"""
    ward_approval_rate: float
    development_type_rate: float
    conservation_area_modifier: float
    precedent_strength: float
    seasonal_modifier: float
    recent_trend_modifier: float
    complexity_modifier: float


@dataclass
class ApprovalPrediction:
    """Prediction result for an application"""
    probability: float
    confidence: float
    factors: PredictionFactors
    comparable_cases: int
    key_factors_positive: List[str]
    key_factors_negative: List[str]
    recommendation: str
    predicted_timeline_days: int


@dataclass
class TrendAnalysis:
    """Analysis of approval trends"""
    ward: str
    development_type: Optional[str]
    period_months: int
    approval_rate_current: float
    approval_rate_previous: float
    trend_direction: str  # "increasing", "decreasing", "stable"
    trend_strength: float  # -1 to 1
    notable_changes: List[str]
    prediction_next_quarter: float


@dataclass
class WardInsights:
    """Deep insights for a specific ward"""
    ward: str
    total_applications: int
    approval_rate: float
    average_decision_time_days: int
    most_successful_types: List[Tuple[str, float]]
    least_successful_types: List[Tuple[str, float]]
    conservation_area_impact: float
    busy_months: List[int]
    recent_notable_decisions: List[Dict[str, Any]]
    recommendations: List[str]


class PredictionEngine:
    """
    Machine learning-style prediction engine for planning decisions.

    Uses statistical analysis of historical decisions to predict
    approval probability for new applications.
    """

    # Base approval rates by development type (from UK planning data)
    BASE_RATES = {
        "Rear Extension": 0.85,
        "Side Extension": 0.82,
        "Loft Conversion": 0.80,
        "Dormer Window": 0.75,
        "Basement/Subterranean": 0.70,
        "Roof Extension": 0.72,
        "Change of Use": 0.65,
        "New Build": 0.55,
        "Demolition": 0.60,
        "Alterations": 0.88,
        "Listed Building Consent": 0.65,
        "Tree Works": 0.90,
        "Other": 0.70,
    }

    # Conservation area penalty factors
    CONSERVATION_PENALTIES = {
        "Hampstead Conservation Area": 0.15,  # Very strict
        "Belsize Conservation Area": 0.12,
        "Redington Frognal Conservation Area": 0.12,
        "South Hampstead Conservation Area": 0.10,
        "Swiss Cottage Conservation Area": 0.08,
        "Primrose Hill Conservation Area": 0.10,
        "None": 0.0,
    }

    def __init__(self, db):
        self.db = db
        self._cache = {}
        self._cache_expiry = {}

    async def predict_approval(
        self,
        development_type: str,
        ward: str,
        conservation_area: Optional[str] = None,
        precedent_count: int = 0,
        precedent_avg_similarity: float = 0.0,
        is_listed_building: bool = False,
        proposal_complexity: str = "standard",  # simple, standard, complex
    ) -> ApprovalPrediction:
        """
        Predict approval probability for a planning application.

        Args:
            development_type: Type of development
            ward: Camden ward
            conservation_area: Conservation area if applicable
            precedent_count: Number of similar precedents found
            precedent_avg_similarity: Average similarity of precedents
            is_listed_building: Whether property is listed
            proposal_complexity: Complexity level

        Returns:
            ApprovalPrediction with probability and analysis
        """
        logger.info(
            "predicting_approval",
            development_type=development_type,
            ward=ward,
            conservation_area=conservation_area
        )

        # Get ward statistics
        ward_stats = await self._get_ward_stats(ward)
        ward_rate = ward_stats.get("approval_rate", 0.75)

        # Get development type statistics
        type_stats = await self._get_type_stats(ward, development_type)
        type_rate = type_stats.get("approval_rate", self.BASE_RATES.get(development_type, 0.70))

        # Conservation area modifier
        ca_penalty = self.CONSERVATION_PENALTIES.get(
            conservation_area or "None",
            0.05
        )
        ca_modifier = 1.0 - ca_penalty

        # Listed building modifier
        lb_modifier = 0.85 if is_listed_building else 1.0

        # Precedent strength
        if precedent_count >= 5 and precedent_avg_similarity >= 0.8:
            precedent_strength = 1.15
        elif precedent_count >= 3 and precedent_avg_similarity >= 0.7:
            precedent_strength = 1.08
        elif precedent_count >= 1:
            precedent_strength = 1.0
        else:
            precedent_strength = 0.90

        # Seasonal modifier (applications in Jan-Mar slightly lower success)
        month = datetime.now().month
        if month in [1, 2, 3]:
            seasonal_modifier = 0.98
        elif month in [4, 5, 6]:
            seasonal_modifier = 1.02
        else:
            seasonal_modifier = 1.0

        # Recent trend modifier
        trend = await self._get_recent_trend(ward, development_type)
        trend_modifier = 1.0 + (trend * 0.05)

        # Complexity modifier
        complexity_modifiers = {
            "simple": 1.05,
            "standard": 1.0,
            "complex": 0.90
        }
        complexity_modifier = complexity_modifiers.get(proposal_complexity, 1.0)

        # Calculate final probability
        factors = PredictionFactors(
            ward_approval_rate=ward_rate,
            development_type_rate=type_rate,
            conservation_area_modifier=ca_modifier,
            precedent_strength=precedent_strength,
            seasonal_modifier=seasonal_modifier,
            recent_trend_modifier=trend_modifier,
            complexity_modifier=complexity_modifier
        )

        # Weighted combination
        base_prob = (type_rate * 0.4 + ward_rate * 0.3 + self.BASE_RATES.get(development_type, 0.7) * 0.3)
        final_prob = base_prob * ca_modifier * lb_modifier * precedent_strength * seasonal_modifier * trend_modifier * complexity_modifier

        # Clamp to valid range
        final_prob = max(0.1, min(0.95, final_prob))

        # Identify key factors
        positive_factors = []
        negative_factors = []

        if precedent_strength > 1.05:
            positive_factors.append(f"Strong precedent support ({precedent_count} similar approved cases)")
        if ward_rate > 0.8:
            positive_factors.append(f"High ward approval rate ({ward_rate:.0%})")
        if type_rate > 0.8:
            positive_factors.append(f"Good success rate for {development_type} ({type_rate:.0%})")
        if trend > 0.05:
            positive_factors.append("Recent positive trend in approvals")

        if ca_modifier < 0.9:
            negative_factors.append(f"Conservation area restrictions ({conservation_area})")
        if is_listed_building:
            negative_factors.append("Listed building consent required")
        if precedent_count < 2:
            negative_factors.append("Limited precedent support")
        if complexity_modifier < 1.0:
            negative_factors.append("Complex proposal may face scrutiny")

        # Calculate confidence
        confidence = self._calculate_confidence(
            precedent_count=precedent_count,
            ward_data_points=ward_stats.get("total", 0),
            type_data_points=type_stats.get("total", 0)
        )

        # Generate recommendation
        if final_prob >= 0.8:
            recommendation = "Proceed with confidence. Strong indicators for approval."
        elif final_prob >= 0.65:
            recommendation = "Good prospects. Consider pre-application advice to strengthen case."
        elif final_prob >= 0.5:
            recommendation = "Mixed indicators. Pre-application discussion strongly recommended."
        else:
            recommendation = "Significant risks identified. Consider design amendments or alternatives."

        # Estimate timeline
        timeline = self._estimate_timeline(development_type, proposal_complexity)

        return ApprovalPrediction(
            probability=final_prob,
            confidence=confidence,
            factors=factors,
            comparable_cases=precedent_count + type_stats.get("total", 0),
            key_factors_positive=positive_factors,
            key_factors_negative=negative_factors,
            recommendation=recommendation,
            predicted_timeline_days=timeline
        )

    async def analyse_trends(
        self,
        ward: str,
        development_type: Optional[str] = None,
        months: int = 12
    ) -> TrendAnalysis:
        """
        Analyse approval trends over time.
        """
        # Get historical data
        current_stats = await self._get_period_stats(
            ward, development_type, months
        )
        previous_stats = await self._get_period_stats(
            ward, development_type, months, offset_months=months
        )

        current_rate = current_stats.get("approval_rate", 0.75)
        previous_rate = previous_stats.get("approval_rate", 0.75)

        # Calculate trend
        rate_change = current_rate - previous_rate

        if rate_change > 0.05:
            direction = "increasing"
            strength = min(rate_change * 5, 1.0)
        elif rate_change < -0.05:
            direction = "decreasing"
            strength = max(rate_change * 5, -1.0)
        else:
            direction = "stable"
            strength = rate_change * 5

        # Identify notable changes
        notable = []
        if abs(rate_change) > 0.1:
            notable.append(f"Significant {direction} trend ({rate_change:+.0%})")
        if current_stats.get("total", 0) < previous_stats.get("total", 0) * 0.8:
            notable.append("Application volumes declining")
        elif current_stats.get("total", 0) > previous_stats.get("total", 0) * 1.2:
            notable.append("Application volumes increasing")

        # Predict next quarter
        prediction = current_rate + (rate_change * 0.5)  # Momentum-based

        return TrendAnalysis(
            ward=ward,
            development_type=development_type,
            period_months=months,
            approval_rate_current=current_rate,
            approval_rate_previous=previous_rate,
            trend_direction=direction,
            trend_strength=strength,
            notable_changes=notable,
            prediction_next_quarter=max(0.3, min(0.95, prediction))
        )

    async def get_ward_insights(self, ward: str) -> WardInsights:
        """
        Get deep insights for a specific ward.
        """
        stats = await self._get_ward_stats(ward)

        # Get type breakdowns
        type_rates = await self._get_all_type_rates(ward)
        sorted_types = sorted(type_rates.items(), key=lambda x: x[1], reverse=True)

        most_successful = sorted_types[:5]
        least_successful = sorted_types[-5:]

        # Conservation area impact
        ca_rates = await self._compare_conservation_areas(ward)
        ca_impact = ca_rates.get("in_ca", 0.7) - ca_rates.get("outside_ca", 0.8)

        # Busy months analysis
        monthly_data = await self._get_monthly_distribution(ward)
        busy_months = sorted(monthly_data.items(), key=lambda x: x[1], reverse=True)[:3]
        busy_months = [m[0] for m in busy_months]

        # Generate recommendations
        recommendations = []
        if stats.get("approval_rate", 0.75) > 0.8:
            recommendations.append("Ward has high approval rate - proceed with standard applications")
        if ca_impact < -0.1:
            recommendations.append("Conservation area significantly impacts approvals - ensure high design quality")
        if most_successful:
            recommendations.append(f"Best success with: {most_successful[0][0]} ({most_successful[0][1]:.0%})")

        return WardInsights(
            ward=ward,
            total_applications=stats.get("total", 0),
            approval_rate=stats.get("approval_rate", 0.75),
            average_decision_time_days=stats.get("avg_decision_time", 56),
            most_successful_types=most_successful,
            least_successful_types=least_successful,
            conservation_area_impact=ca_impact,
            busy_months=busy_months,
            recent_notable_decisions=[],  # Would be populated from DB
            recommendations=recommendations
        )

    async def compare_scenarios(
        self,
        scenarios: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Compare multiple development scenarios.

        Useful for exploring different design options.
        """
        results = []

        for scenario in scenarios:
            prediction = await self.predict_approval(
                development_type=scenario.get("development_type", "Other"),
                ward=scenario.get("ward", "Unknown"),
                conservation_area=scenario.get("conservation_area"),
                precedent_count=scenario.get("precedent_count", 0),
                precedent_avg_similarity=scenario.get("precedent_similarity", 0),
                proposal_complexity=scenario.get("complexity", "standard")
            )

            results.append({
                "scenario_name": scenario.get("name", "Unnamed"),
                "probability": prediction.probability,
                "recommendation": prediction.recommendation,
                "key_advantages": prediction.key_factors_positive,
                "key_risks": prediction.key_factors_negative,
            })

        # Sort by probability
        results.sort(key=lambda x: x["probability"], reverse=True)

        return results

    # ==================== Helper Methods ====================

    async def _get_ward_stats(self, ward: str) -> Dict[str, Any]:
        """Get statistics for a ward"""
        cache_key = f"ward_stats_{ward}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            stats = await self.db.get_ward_stats(ward)
            if stats:
                result = {
                    "approval_rate": stats.approval_rate,
                    "total": stats.case_count,
                    "avg_decision_time": 56,  # Default
                }
            else:
                result = {"approval_rate": 0.75, "total": 0}

            self._cache[cache_key] = result
            return result
        except Exception:
            return {"approval_rate": 0.75, "total": 0}

    async def _get_type_stats(
        self,
        ward: str,
        development_type: str
    ) -> Dict[str, Any]:
        """Get statistics for a development type in a ward"""
        # Would query database - simplified for now
        base_rate = self.BASE_RATES.get(development_type, 0.70)
        return {
            "approval_rate": base_rate,
            "total": 50,
        }

    async def _get_recent_trend(
        self,
        ward: str,
        development_type: str
    ) -> float:
        """Get recent trend (-1 to 1)"""
        # Simplified - would analyse recent decisions
        return 0.0

    async def _get_period_stats(
        self,
        ward: str,
        development_type: Optional[str],
        months: int,
        offset_months: int = 0
    ) -> Dict[str, Any]:
        """Get stats for a specific time period"""
        # Simplified implementation
        return {
            "approval_rate": 0.75,
            "total": 100,
        }

    async def _get_all_type_rates(self, ward: str) -> Dict[str, float]:
        """Get approval rates for all development types"""
        return self.BASE_RATES.copy()

    async def _compare_conservation_areas(self, ward: str) -> Dict[str, float]:
        """Compare rates inside vs outside conservation areas"""
        return {
            "in_ca": 0.70,
            "outside_ca": 0.82,
        }

    async def _get_monthly_distribution(self, ward: str) -> Dict[int, int]:
        """Get application distribution by month"""
        return {
            1: 80, 2: 75, 3: 90, 4: 100, 5: 95, 6: 110,
            7: 85, 8: 70, 9: 105, 10: 100, 11: 90, 12: 60
        }

    def _calculate_confidence(
        self,
        precedent_count: int,
        ward_data_points: int,
        type_data_points: int
    ) -> float:
        """Calculate prediction confidence"""
        data_score = min(
            (precedent_count / 10 + ward_data_points / 500 + type_data_points / 100) / 3,
            1.0
        )
        return 0.5 + (data_score * 0.4)

    def _estimate_timeline(
        self,
        development_type: str,
        complexity: str
    ) -> int:
        """Estimate decision timeline in days"""
        base_times = {
            "Rear Extension": 56,
            "Side Extension": 56,
            "Loft Conversion": 56,
            "Dormer Window": 56,
            "Basement/Subterranean": 70,
            "Change of Use": 70,
            "New Build": 91,
            "Listed Building Consent": 70,
        }

        complexity_multipliers = {
            "simple": 0.9,
            "standard": 1.0,
            "complex": 1.3
        }

        base = base_times.get(development_type, 56)
        multiplier = complexity_multipliers.get(complexity, 1.0)

        return int(base * multiplier)
