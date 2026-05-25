from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, ContextualRelevancyMetric

from app.chat_agent.engine import run_sales_support_agent
from app.chat_agent.retrieval import retrieve_context, build_context


TENANT_ID = 1  # change this to your real tenant id
SESSION_ID = "deepeval_sales_test"


def check_agent(user_message: str):
    result = run_sales_support_agent(
        tenant_id=TENANT_ID,
        session_id=SESSION_ID,
        message=user_message,
        top_k=8,
        agent_type="chat",
    )

    results = retrieve_context(
        tenant_id=TENANT_ID,
        query=user_message,
        top_k=8,
    )

    context = build_context(results, max_chars=2600)

    test_case = LLMTestCase(
        input=user_message,
        actual_output=result["answer"],
        retrieval_context=[context],
    )

    assert_test(
        test_case,
        [
            AnswerRelevancyMetric(threshold=0.7),
            FaithfulnessMetric(threshold=0.7),
            ContextualRelevancyMetric(threshold=0.7),
        ],
    )


def test_buying_guidance():
    check_agent("I need plumbing pipes for my house, 304 or 316L?")


def test_support_installation():
    check_agent("What is the installation process?")


def test_pricing():
    check_agent("What is the price of 304 stainless steel pipe?")


def test_trust_proof():
    check_agent("Where have you supplied your products?")