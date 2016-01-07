from ob2.util.time import now


class Job(object):
    def __init__(self, build_name, source, trigger):
        """
        Creates a new dockergrader job to be added to the queue.

        """
        self.build_name = build_name
        self.source = source
        self.trigger = trigger
        self.updated = now()


class JobFailedError(Exception):
    def __init__(self, message, critical=False):
        super(JobFailedError, self).__init__(message)
        self.args = (message, critical)

    def __str__(self):
        return self.args[0]
