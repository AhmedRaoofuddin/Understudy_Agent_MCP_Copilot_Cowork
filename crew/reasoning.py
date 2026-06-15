"""A small ReAct engine: the reasoning substrate for the thinking agents.

ReAct interleaves a thought, an action, and an observation until the agent
produces a final answer. The Planner and the Scribe reason on top of this. We
keep the engine deterministic in structure: the model proposes the next step in
a simple text format, the engine parses it, runs any named tool, feeds back the
observation, and loops until the model returns a final answer or the step budget
runs out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple


@dataclass
class ReActStep:
    thought: str = ""
    action: str = ""
    action_input: str = ""
    observation: str = ""


@dataclass
class ReasoningTrace:
    steps: List[ReActStep] = field(default_factory=list)
    final_answer: str = ""


class ReActEngine:
    def __init__(
        self,
        model_client,
        tools: Optional[Dict[str, Callable[[str], object]]] = None,
        max_steps: int = 4,
    ) -> None:
        self.model_client = model_client
        self.tools = tools or {}
        self.max_steps = max_steps

    def run(self, system: str, task: str, context: str) -> ReasoningTrace:
        trace = ReasoningTrace()
        transcript = ""
        for _ in range(self.max_steps):
            prompt = self._build_prompt(task, context, transcript)
            raw = self.model_client.generate(system, prompt)
            thought, action, action_input, final = self._parse(raw)

            if final is not None:
                trace.steps.append(ReActStep(thought=thought))
                trace.final_answer = final
                return trace

            if action in self.tools:
                observation = str(self.tools[action](action_input))
            else:
                observation = "no tool named " + repr(action)

            trace.steps.append(ReActStep(thought, action, action_input, observation))
            transcript += (
                "\nTHOUGHT: " + thought
                + "\nACTION: " + action
                + "\nOBSERVATION: " + observation
            )

        trace.final_answer = "stopped without a final answer"
        return trace

    @staticmethod
    def _build_prompt(task: str, context: str, transcript: str) -> str:
        return (
            "Task:\n" + task + "\n\nContext:\n" + context + "\n\nProgress so far:"
            + (transcript if transcript else " none")
            + "\n\nReply with THOUGHT and then either ACTION and ACTION_INPUT, "
            + "or FINAL with your answer."
        )

    @staticmethod
    def _parse(raw: str) -> Tuple[str, str, str, Optional[str]]:
        thought = ""
        action = ""
        action_input = ""
        final: Optional[str] = None
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("THOUGHT:"):
                thought = stripped[len("THOUGHT:") :].strip()
            elif stripped.upper().startswith("ACTION_INPUT:"):
                action_input = stripped[len("ACTION_INPUT:") :].strip()
            elif stripped.upper().startswith("ACTION:"):
                action = stripped[len("ACTION:") :].strip()
            elif stripped.upper().startswith("FINAL:"):
                final = stripped[len("FINAL:") :].strip()
        return thought, action, action_input, final
