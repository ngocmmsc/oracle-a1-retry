# oracle-a1-retry
Retries creating one Oracle Always Free A1 VM (2 OCPU/12 GB). All identifiers are stored as Actions secrets.

Each run loops for about 5 hours 30 minutes, attempting a launch every 3 minutes. If the window ends without success, the workflow redispatches itself. On success it opens an issue and disables itself.
