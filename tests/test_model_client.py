import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crew.model_client import AnthropicModelClient, DeterministicModelClient


class _FakeBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeMessage:
    def __init__(self, text):
        self.content = [_FakeBlock(text)]


class _FakeMessages:
    def __init__(self, text):
        self._text = text

    def create(self, **kwargs):
        return _FakeMessage(self._text)


class _FakeAnthropic:
    def __init__(self, text):
        self.messages = _FakeMessages(text)


class ModelClientTests(unittest.TestCase):
    def test_deterministic_planner_output_is_parseable(self):
        output = DeterministicModelClient().generate("ROLE: planner", "do the task")
        self.assertIn("FINAL:", output)

    def test_deterministic_scribe_returns_steps(self):
        output = DeterministicModelClient().generate("ROLE: scribe", "induce")
        self.assertIn("STEP:", output)

    def test_anthropic_client_uses_injected_client(self):
        client = AnthropicModelClient(client=_FakeAnthropic("hello from the model"))
        self.assertEqual(client.generate("system", "prompt"), "hello from the model")


if __name__ == "__main__":
    unittest.main()
