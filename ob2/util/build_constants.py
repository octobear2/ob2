QUEUED = -2
IN_PROGRESS = -1
SUCCESS = 0
FAILED = 1


def build_status_to_string(status, default='Unknown'):
    return {QUEUED:      "Waiting in queue",
            IN_PROGRESS: "In progress",
            SUCCESS:     "Completed",
            FAILED:      "Failed to complete"}.get(status, default)
