-- ─────────────────────────────────────────────
-- Dadi AI — Analytics Events Table + Views
-- Run this in the Supabase SQL editor.
-- ─────────────────────────────────────────────

-- TABLE
CREATE TABLE IF NOT EXISTS analytics_events (
    id          uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
    event_name  text        NOT NULL,
    session_id  text,
    user_email  text,                              -- NULL for guests
    user_type   text        NOT NULL DEFAULT 'guest', -- 'guest' | 'registered'
    properties  jsonb       NOT NULL DEFAULT '{}',
    created_at  timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ae_name_idx       ON analytics_events (event_name);
CREATE INDEX IF NOT EXISTS ae_created_at_idx ON analytics_events (created_at DESC);
CREATE INDEX IF NOT EXISTS ae_session_idx    ON analytics_events (session_id);
CREATE INDEX IF NOT EXISTS ae_user_idx       ON analytics_events (user_email) WHERE user_email IS NOT NULL;

-- ─────────────────────────────────────────────
-- VIEWS
-- ─────────────────────────────────────────────

-- KPI summary (headline numbers)
CREATE OR REPLACE VIEW v_kpi_summary AS
SELECT
    (SELECT COUNT(DISTINCT COALESCE(user_email, session_id))
     FROM analytics_events
     WHERE event_name = 'session_start'
       AND created_at >= now() - interval '1 day')   AS dau,

    (SELECT COUNT(DISTINCT COALESCE(user_email, session_id))
     FROM analytics_events
     WHERE event_name = 'session_start'
       AND created_at >= now() - interval '7 days')  AS wau,

    (SELECT COUNT(DISTINCT COALESCE(user_email, session_id))
     FROM analytics_events
     WHERE event_name = 'session_start'
       AND created_at >= now() - interval '30 days') AS mau,

    (SELECT COUNT(*)
     FROM analytics_events
     WHERE event_name = 'message_sent'
       AND created_at >= now() - interval '1 day')   AS messages_today,

    (SELECT ROUND(AVG((properties->>'message_count')::int), 1)
     FROM analytics_events
     WHERE event_name = 'session_end'
       AND created_at >= now() - interval '7 days')  AS avg_messages_per_session,

    (SELECT ROUND(AVG((properties->>'duration_seconds')::int / 60.0), 1)
     FROM analytics_events
     WHERE event_name = 'session_end'
       AND (properties->>'duration_seconds')::int > 0
       AND created_at >= now() - interval '7 days')  AS avg_session_minutes;

-- Daily active users (last 30 days)
CREATE OR REPLACE VIEW v_dau AS
SELECT
    date_trunc('day', created_at AT TIME ZONE 'UTC')::date             AS day,
    COUNT(DISTINCT COALESCE(user_email, session_id))                   AS unique_users,
    COUNT(DISTINCT CASE WHEN user_type = 'registered' THEN user_email END) AS registered_users,
    COUNT(DISTINCT CASE WHEN user_type = 'guest'      THEN session_id  END) AS guest_users
FROM analytics_events
WHERE event_name = 'session_start'
  AND created_at >= now() - interval '30 days'
GROUP BY 1
ORDER BY 1 DESC;

-- Weekly active users (last 12 weeks)
CREATE OR REPLACE VIEW v_wau AS
SELECT
    date_trunc('week', created_at AT TIME ZONE 'UTC')::date AS week,
    COUNT(DISTINCT COALESCE(user_email, session_id))        AS unique_users
FROM analytics_events
WHERE event_name = 'session_start'
  AND created_at >= now() - interval '12 weeks'
GROUP BY 1
ORDER BY 1 DESC;

-- Monthly active users (last 12 months)
CREATE OR REPLACE VIEW v_mau AS
SELECT
    date_trunc('month', created_at AT TIME ZONE 'UTC')::date AS month,
    COUNT(DISTINCT COALESCE(user_email, session_id))         AS unique_users
FROM analytics_events
WHERE event_name = 'session_start'
  AND created_at >= now() - interval '12 months'
GROUP BY 1
ORDER BY 1 DESC;

-- Guest vs registered ratio (last 30 days)
CREATE OR REPLACE VIEW v_user_type_ratio AS
SELECT
    user_type,
    COUNT(*) AS session_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
FROM analytics_events
WHERE event_name = 'session_start'
  AND created_at >= now() - interval '30 days'
GROUP BY user_type;

-- Top starter prompts (last 30 days)
CREATE OR REPLACE VIEW v_top_starters AS
SELECT
    properties->>'starter_label' AS starter_label,
    COUNT(*)                     AS uses
FROM analytics_events
WHERE event_name = 'starter_used'
  AND created_at >= now() - interval '30 days'
GROUP BY 1
ORDER BY 2 DESC
LIMIT 20;

-- OTP funnel (last 30 days)
CREATE OR REPLACE VIEW v_otp_funnel AS
SELECT
    SUM(CASE WHEN event_name = 'otp_requested' THEN 1 ELSE 0 END) AS requested,
    SUM(CASE WHEN event_name = 'otp_verified'  THEN 1 ELSE 0 END) AS verified,
    SUM(CASE WHEN event_name = 'otp_failed'    THEN 1 ELSE 0 END) AS failed,
    ROUND(
        SUM(CASE WHEN event_name = 'otp_verified' THEN 1 ELSE 0 END) * 100.0
        / NULLIF(SUM(CASE WHEN event_name = 'otp_requested' THEN 1 ELSE 0 END), 0),
        1
    ) AS conversion_pct
FROM analytics_events
WHERE event_name IN ('otp_requested', 'otp_verified', 'otp_failed')
  AND created_at >= now() - interval '30 days';

-- RAG usage rate per day (last 30 days)
CREATE OR REPLACE VIEW v_rag_usage AS
SELECT
    date_trunc('day', created_at AT TIME ZONE 'UTC')::date AS day,
    COUNT(*)                                               AS total_messages,
    SUM(CASE WHEN (properties->>'rag_used')::boolean THEN 1 ELSE 0 END) AS rag_messages,
    ROUND(
        SUM(CASE WHEN (properties->>'rag_used')::boolean THEN 1 ELSE 0 END) * 100.0
        / NULLIF(COUNT(*), 0),
        1
    ) AS rag_pct
FROM analytics_events
WHERE event_name = 'message_sent'
  AND created_at >= now() - interval '30 days'
GROUP BY 1
ORDER BY 1 DESC;

-- Memory extractions per day (last 30 days)
CREATE OR REPLACE VIEW v_memory_extractions AS
SELECT
    date_trunc('day', created_at AT TIME ZONE 'UTC')::date AS day,
    COUNT(*)                                               AS extractions,
    SUM((properties->>'facts_count')::int)                 AS total_facts_saved,
    properties->>'trigger'                                 AS trigger
FROM analytics_events
WHERE event_name = 'memory_extracted'
  AND created_at >= now() - interval '30 days'
GROUP BY 1, 3
ORDER BY 1 DESC;

-- Session stats (raw rows for histogram, last 30 days)
CREATE OR REPLACE VIEW v_session_stats AS
SELECT
    (properties->>'message_count')::int  AS message_count,
    (properties->>'duration_seconds')::int AS duration_seconds,
    user_type,
    created_at::date                     AS day
FROM analytics_events
WHERE event_name = 'session_end'
  AND created_at >= now() - interval '30 days';
