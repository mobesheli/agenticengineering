CREATE TABLE reconciliation_episode (
    episode_id      UUID PRIMARY KEY,
    patient_ref     TEXT NOT NULL,
    org_id          UUID NOT NULL,
    occurred_at     TIMESTAMPTZ NOT NULL,
    summary         TEXT NOT NULL,
    importance      INT,
    embedding       VECTOR(1024),
    valid_to        TIMESTAMPTZ,
    tombstoned      BOOLEAN DEFAULT false,
    legal_hold      BOOLEAN DEFAULT true,
    retention_until TIMESTAMPTZ NOT NULL
);

ALTER TABLE reconciliation_episode ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON reconciliation_episode
    USING (org_id = current_setting('app.org_id')::uuid);
