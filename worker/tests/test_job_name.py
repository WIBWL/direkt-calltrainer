"""The backend queues the wrap-up by name (`shared/feedback/queue.py`), so that it
never imports the worker. A renamed or moved generator would then fail every job
in the worker and nothing else -- the call and the queueing look healthy.

This resolves the name the way RQ does when it runs the job.
"""

from rq.utils import import_attribute

from shared.feedback.queue import JOB_FUNCTION
from worker.generator import generate_feedback


def test_the_queued_name_resolves_to_the_generator():
    """The string in the queue is the function the worker runs."""
    assert import_attribute(JOB_FUNCTION) is generate_feedback
