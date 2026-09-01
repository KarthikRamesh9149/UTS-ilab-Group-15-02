import ollama
from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

MAX_STEPS = 15
MODEL_NAME = "qwen2.5-coder:3b"

class MyGeminiAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "my-custom-agent"

    def version(self) -> str | None:
        return "0.1.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        pass

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        system_prompt = (
            "You are an agent working in a Linux terminal. "
            "You will be given a task. Respond with ONLY the single next shell "
            "command to run, and nothing else. No explanations, no markdown, "
            "no code fences. If the task is complete, respond with exactly: DONE"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task: {instruction}"},
        ]

        total_input_tokens = 0
        total_output_tokens = 0

        for step in range(MAX_STEPS):
            response = ollama.chat(model=MODEL_NAME, messages=messages)
            command = response["message"]["content"].strip()

            total_input_tokens += response.get("prompt_eval_count", 0)
            total_output_tokens += response.get("eval_count", 0)

            if command.upper() == "DONE":
                break

            messages.append({"role": "assistant", "content": command})

            result = await environment.exec(command)

            messages.append({"role": "user", "content": f"Output:\n{result.stdout}"})

        context.n_input_tokens = total_input_tokens
        context.n_output_tokens = total_output_tokens
