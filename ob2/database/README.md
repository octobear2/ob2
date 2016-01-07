Schema documentation
====================

## options
* key TEXT PRIMARY KEY
* value TEXT

## users
* id INT PRIMARY KEY
* name TEXT
* sid TEXT
* login TEXT
* github TEXT
* email TEXT
* super INT
* grouplimit INT
* photo BLOB

## gradeslog
* transaction_name TEXT
* description TEXT
* source TEXT
* updated TEXT
* user INT
* assignment TEXT
* score REAL
* slipunits INT

## grades
* user INT
* assignment TEXT
* score REAL
* slipunits INT
* updated TEXT
* manual INT
* PRIMARY KEY(user, assignment)

## builds
* build_name TEXT
* source TEXT
* commit TEXT
* message TEXT
* job TEXT
* status INT
* score REAL
* started TEXT
* updated TEXT
* log TEXT

## repomanager
* id INT PRIMARY KEY
* operation TEXT
* payload TEXT
* updated TEXT
* completed INT

## groupsusers
* user INT
* group TEXT
* PRIMARY KEY(user, group)

## invitations
* invitation_id INT
* user INT
* status INT
* PRIMARY KEY(invitation_id, user)

## mailerqueue
* id INT PRIMARY KEY
* operation TEXT
* payload TEXT
* updated TEXT
* completed INT
