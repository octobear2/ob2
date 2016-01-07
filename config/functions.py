import logging
from ob2.util.hooks import register_job

logging.info("Hello world!")


@register_job("hw0")
def hw0_job_handler(repo, commit_hash):
    return "You get full credit!", 10.0
