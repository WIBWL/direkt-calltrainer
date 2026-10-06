"""The queued job name resolves the way RQ resolves it."""

from rq.utils import import_attribute

from shared.feedback.queue import JOB_FUNCTION
from worker.generator import generate_feedback


def test_the_queued_name_resolves_to_the_generator():
    assert import_attribute(JOB_FUNCTION) is generate_feedback
