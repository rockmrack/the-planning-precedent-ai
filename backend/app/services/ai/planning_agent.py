"""
Autonomous Planning Agent
An AI agent that can autonomously research, analyse, and generate planning documents

This implements a ReAct-style agent that can:
1. Search for precedents
2. Analyse documents
3. Generate arguments
4. Create full application documents
5. Monitor application status
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
import re

from openai import AsyncOpenAI
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class AgentAction(str, Enum):
    """Available agent actions"""
    SEARCH_PRECEDENTS = "search_precedents"
    GET_CASE_DETAILS = "get_case_details"
    ANALYSE_DOCUMENT = "analyse_document"
    IDENTIFY_POLICIES = "identify_policies"
    GENERATE_ARGUMENT = "generate_argument"
    ASSESS_RISK = "assess_risk"
    CHECK_CONSERVATION_AREA = "check_conservation_area"
    FIND_SIMILAR_ADDRESSES = "find_similar_addresses"
    CALCULATE_APPROVAL_RATE = "calculate_approval_rate"
    GENERATE_REPORT = "generate_report"
    FINISH = "finish"


@dataclass
class AgentStep:
    """A single step in the agent's execution"""
    thought: str
    action: AgentAction
    action_input: Dict[str, Any]
    observation: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AgentResult:
    """Final result from agent execution"""
    success: bool
    answer: str
    steps: List[AgentStep]
    sources_used: List[str]
    confidence: float
    execution_time_seconds: float


class PlanningAgent:
    """
    Autonomous agent for planning research and analysis.

    Uses ReAct (Reasoning + Acting) pattern to:
    1. Think about what to do
    2. Take an action
    3. Observe the result
    4. Repeat until task is complete
    """

    SYSTEM_PROMPT = """You are an expert UK planning consultant agent. You have access to tools to research planning precedents and generate professional planning arguments.

You work for clients in London Borough of Camden. Your goal is to help them understand their chances of planning approval and build strong cases.

Available tools:
1. search_precedents(query, ward, limit) - Search for similar planning decisions
2. get_case_details(case_reference) - Get full details of a specific case
3. analyse_document(text) - Analyse planning document text for key points
4. identify_policies(development_type, conservation_area) - Identify relevant planning policies
5. generate_argument(topic, precedents, policies) - Generate a planning argument
6. assess_risk(proposal, context) - Assess risks to approval
7. check_conservation_area(address) - Check if address is in a conservation area
8. find_similar_addresses(address, radius) - Find planning history near an address
9. calculate_approval_rate(ward, development_type) - Get approval statistics
10. generate_report(sections) - Generate a formatted report
11. finish(answer) - Complete the task with final answer

Always think step by step. Use tools to gather information before generating arguments.

Respond in this format:
Thought: [Your reasoning about what to do next]
Action: [tool_name]
Action Input: {"param": "value"}

After receiving an observation, continue with another Thought/Action or finish.
When you have enough information, use the finish action with your complete answer."""

    def __init__(self, tools: Dict[str, Callable[..., Awaitable[str]]]):
        """
        Initialise agent with tool functions.

        Args:
            tools: Dictionary mapping tool names to async functions
        """
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o"
        self.tools = tools
        self.max_steps = 15

    async def run(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """
        Execute the agent on a task.

        Args:
            task: The task description
            context: Optional context (address, ward, etc.)

        Returns:
            AgentResult with answer and execution trace
        """
        start_time = datetime.utcnow()
        steps: List[AgentStep] = []
        sources: List[str] = []

        # Build initial prompt
        context_str = ""
        if context:
            context_str = f"\n\nContext:\n{json.dumps(context, indent=2)}"

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": f"Task: {task}{context_str}"}
        ]

        logger.info("agent_starting", task=task[:100])

        for step_num in range(self.max_steps):
            try:
                # Get next action from LLM
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=2000,
                    temperature=0.2,
                )

                assistant_message = response.choices[0].message.content
                messages.append({"role": "assistant", "content": assistant_message})

                # Parse the response
                thought, action, action_input = self._parse_response(assistant_message)

                step = AgentStep(
                    thought=thought,
                    action=action,
                    action_input=action_input
                )

                logger.debug(
                    "agent_step",
                    step=step_num + 1,
                    action=action.value,
                    thought=thought[:100]
                )

                # Check if agent wants to finish
                if action == AgentAction.FINISH:
                    steps.append(step)
                    execution_time = (datetime.utcnow() - start_time).total_seconds()

                    return AgentResult(
                        success=True,
                        answer=action_input.get("answer", ""),
                        steps=steps,
                        sources_used=list(set(sources)),
                        confidence=self._calculate_confidence(steps),
                        execution_time_seconds=execution_time
                    )

                # Execute the action
                observation = await self._execute_action(action, action_input)
                step.observation = observation
                steps.append(step)

                # Track sources
                if action == AgentAction.SEARCH_PRECEDENTS:
                    sources.append(f"Search: {action_input.get('query', '')[:50]}")
                elif action == AgentAction.GET_CASE_DETAILS:
                    sources.append(f"Case: {action_input.get('case_reference', '')}")

                # Add observation to messages
                messages.append({
                    "role": "user",
                    "content": f"Observation: {observation}"
                })

            except Exception as e:
                logger.error("agent_step_failed", step=step_num, error=str(e))
                messages.append({
                    "role": "user",
                    "content": f"Error: {str(e)}. Try a different approach."
                })

        # Max steps reached
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        return AgentResult(
            success=False,
            answer="I was unable to complete the task within the step limit.",
            steps=steps,
            sources_used=list(set(sources)),
            confidence=0.3,
            execution_time_seconds=execution_time
        )

    def _parse_response(
        self,
        response: str
    ) -> tuple[str, AgentAction, Dict[str, Any]]:
        """Parse LLM response into thought, action, and input"""
        thought = ""
        action = AgentAction.FINISH
        action_input = {}

        # Extract thought
        thought_match = re.search(r"Thought:\s*(.+?)(?=Action:|$)", response, re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()

        # Extract action
        action_match = re.search(r"Action:\s*(\w+)", response)
        if action_match:
            action_name = action_match.group(1).lower()
            try:
                action = AgentAction(action_name)
            except ValueError:
                action = AgentAction.FINISH

        # Extract action input
        input_match = re.search(r"Action Input:\s*({.+?})", response, re.DOTALL)
        if input_match:
            try:
                action_input = json.loads(input_match.group(1))
            except json.JSONDecodeError:
                action_input = {"raw": input_match.group(1)}

        return thought, action, action_input

    async def _execute_action(
        self,
        action: AgentAction,
        action_input: Dict[str, Any]
    ) -> str:
        """Execute an action using the registered tools"""
        tool_name = action.value

        if tool_name not in self.tools:
            return f"Tool '{tool_name}' not available."

        try:
            result = await self.tools[tool_name](**action_input)
            return str(result)[:3000]  # Truncate long results
        except Exception as e:
            return f"Tool error: {str(e)}"

    def _calculate_confidence(self, steps: List[AgentStep]) -> float:
        """Calculate confidence based on execution quality"""
        if not steps:
            return 0.0

        # Factors that increase confidence
        precedent_searches = sum(1 for s in steps if s.action == AgentAction.SEARCH_PRECEDENTS)
        case_details = sum(1 for s in steps if s.action == AgentAction.GET_CASE_DETAILS)
        policy_checks = sum(1 for s in steps if s.action == AgentAction.IDENTIFY_POLICIES)
        risk_assessments = sum(1 for s in steps if s.action == AgentAction.ASSESS_RISK)

        score = 0.5  # Base score

        if precedent_searches >= 1:
            score += 0.15
        if case_details >= 2:
            score += 0.1
        if policy_checks >= 1:
            score += 0.1
        if risk_assessments >= 1:
            score += 0.1

        # Penalty for too many steps (might indicate confusion)
        if len(steps) > 10:
            score -= 0.1

        return min(max(score, 0.1), 0.95)


class PlanningAgentToolkit:
    """
    Toolkit providing tools for the Planning Agent.
    Connects agent actions to actual service implementations.
    """

    def __init__(self, db, embedding_service, analysis_service):
        self.db = db
        self.embedding_service = embedding_service
        self.analysis_service = analysis_service

    def get_tools(self) -> Dict[str, Callable[..., Awaitable[str]]]:
        """Get dictionary of tool functions"""
        return {
            AgentAction.SEARCH_PRECEDENTS.value: self.search_precedents,
            AgentAction.GET_CASE_DETAILS.value: self.get_case_details,
            AgentAction.ANALYSE_DOCUMENT.value: self.analyse_document,
            AgentAction.IDENTIFY_POLICIES.value: self.identify_policies,
            AgentAction.GENERATE_ARGUMENT.value: self.generate_argument,
            AgentAction.ASSESS_RISK.value: self.assess_risk,
            AgentAction.CHECK_CONSERVATION_AREA.value: self.check_conservation_area,
            AgentAction.FIND_SIMILAR_ADDRESSES.value: self.find_similar_addresses,
            AgentAction.CALCULATE_APPROVAL_RATE.value: self.calculate_approval_rate,
            AgentAction.GENERATE_REPORT.value: self.generate_report,
        }

    async def search_precedents(
        self,
        query: str,
        ward: Optional[str] = None,
        limit: int = 5
    ) -> str:
        """Search for similar planning precedents"""
        embedding = await self.embedding_service.generate_embedding(query)

        filters = None
        if ward:
            from app.models.planning import SearchFilters
            filters = SearchFilters(wards=[ward])

        results = await self.db.search_similar(
            query_embedding=embedding,
            filters=filters,
            limit=limit,
            similarity_threshold=0.6
        )

        if not results:
            return "No similar precedents found."

        output = []
        for r in results:
            output.append(
                f"- {r.decision.case_reference} ({r.decision.outcome.value}): "
                f"{r.decision.description[:100]}... "
                f"[Similarity: {r.similarity_score:.0%}]"
            )

        return f"Found {len(results)} precedents:\n" + "\n".join(output)

    async def get_case_details(self, case_reference: str) -> str:
        """Get full details of a planning case"""
        decision = await self.db.get_decision_by_reference(case_reference)

        if not decision:
            return f"Case {case_reference} not found."

        return f"""
Case: {decision.case_reference}
Address: {decision.address}
Ward: {decision.ward}
Date: {decision.decision_date}
Outcome: {decision.outcome.value}
Type: {decision.development_type.value if decision.development_type else 'Unknown'}
Conservation Area: {decision.conservation_area.value if decision.conservation_area else 'None'}
Description: {decision.description}
"""

    async def analyse_document(self, text: str) -> str:
        """Analyse planning document text"""
        # Use LLM to extract key points
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Extract key planning points from this document. List: 1) Main proposal, 2) Key policies cited, 3) Officer conclusions, 4) Conditions (if approved)"},
                {"role": "user", "content": text[:4000]}
            ],
            max_tokens=500
        )

        return response.choices[0].message.content

    async def identify_policies(
        self,
        development_type: str,
        conservation_area: Optional[str] = None
    ) -> str:
        """Identify relevant planning policies"""
        policies = {
            "extensions": ["D1", "D3", "A1"],
            "dormers": ["D1", "D3"],
            "basements": ["D1", "D3", "A1", "Camden Basement SPD"],
            "change_of_use": ["D1", "E1", "E2"],
            "new_build": ["D1", "D2", "H1"],
        }

        dev_lower = development_type.lower()
        relevant = []

        for key, pols in policies.items():
            if key in dev_lower:
                relevant.extend(pols)

        if conservation_area and conservation_area != "None":
            relevant.extend(["D2", "Section 72 P(LBCA) Act 1990"])

        return f"Relevant policies for {development_type}: {', '.join(set(relevant))}"

    async def generate_argument(
        self,
        topic: str,
        precedents: List[str],
        policies: List[str]
    ) -> str:
        """Generate a planning argument"""
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a planning consultant. Write a professional planning argument."},
                {"role": "user", "content": f"Topic: {topic}\nPrecedents: {', '.join(precedents)}\nPolicies: {', '.join(policies)}"}
            ],
            max_tokens=500
        )

        return response.choices[0].message.content

    async def assess_risk(
        self,
        proposal: str,
        context: Dict[str, Any]
    ) -> str:
        """Assess risks to planning approval"""
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a planning risk assessor. List key risks to approval with severity (High/Medium/Low)."},
                {"role": "user", "content": f"Proposal: {proposal}\nContext: {json.dumps(context)}"}
            ],
            max_tokens=500
        )

        return response.choices[0].message.content

    async def check_conservation_area(self, address: str) -> str:
        """Check if address is in a conservation area"""
        # In production, this would check against GIS data
        address_lower = address.lower()

        conservation_indicators = {
            "hampstead": "Hampstead Conservation Area",
            "belsize": "Belsize Conservation Area",
            "frognal": "Redington Frognal Conservation Area",
            "swiss cottage": "Swiss Cottage Conservation Area",
            "primrose hill": "Primrose Hill Conservation Area",
        }

        for indicator, ca in conservation_indicators.items():
            if indicator in address_lower:
                return f"Address is within {ca}. Special design considerations apply."

        return "Address does not appear to be in a conservation area (verify with Camden)."

    async def find_similar_addresses(
        self,
        address: str,
        radius: int = 500
    ) -> str:
        """Find planning history near an address"""
        # Search database for nearby addresses
        decisions, total = await self.db.list_decisions(page_size=10)

        # Simple address matching
        address_parts = address.lower().split()
        matches = []

        for d in decisions:
            if any(part in d.address.lower() for part in address_parts[:2]):
                matches.append(f"- {d.case_reference}: {d.outcome.value} ({d.decision_date})")

        if matches:
            return f"Found {len(matches)} nearby applications:\n" + "\n".join(matches[:5])
        return "No planning history found for this address."

    async def calculate_approval_rate(
        self,
        ward: str,
        development_type: Optional[str] = None
    ) -> str:
        """Calculate approval statistics"""
        stats = await self.db.get_ward_stats(ward)

        if not stats:
            return f"No data available for ward: {ward}"

        return f"""
Ward: {stats.name}
Total applications: {stats.case_count}
Approval rate: {stats.approval_rate:.1%}
Common development types: {', '.join(stats.common_development_types[:3])}
"""

    async def generate_report(self, sections: List[Dict[str, str]]) -> str:
        """Generate a formatted report"""
        report = ["# Planning Analysis Report", f"Generated: {datetime.utcnow().strftime('%d %B %Y')}", ""]

        for section in sections:
            report.append(f"## {section.get('title', 'Section')}")
            report.append(section.get('content', ''))
            report.append("")

        return "\n".join(report)
