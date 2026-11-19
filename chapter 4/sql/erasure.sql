UPDATE agent_memory
SET valid_to = now(), tombstoned = true
WHERE user_id = :erasure_subject
  AND legal_hold = false;
