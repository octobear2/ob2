INVITED = 0
ACCEPTED = 1
REJECTED = 2


def invitation_status_to_string(status, default='Unknown'):
    return {INVITED:  "invited",
            ACCEPTED: "accepted",
            REJECTED: "rejected"}.get(status, default)
