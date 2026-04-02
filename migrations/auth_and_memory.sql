-- Run this in your Supabase SQL editor

-- Registered users
CREATE TABLE IF NOT EXISTS users (
    id         uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
    email      text        UNIQUE NOT NULL,
    created_at timestamptz DEFAULT now()
);

-- OTP codes (email login)
CREATE TABLE IF NOT EXISTS otp_codes (
    id         uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
    email      text        NOT NULL,
    code       text        NOT NULL,
    expires_at timestamptz NOT NULL,
    used       boolean     DEFAULT false,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS otp_codes_email_idx ON otp_codes (email);

-- OTP codes (phone / SMS login)
CREATE TABLE IF NOT EXISTS phone_otp_codes (
    id         uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
    phone      text        NOT NULL,
    code       text        NOT NULL,
    expires_at timestamptz NOT NULL,
    used       boolean     DEFAULT false,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS phone_otp_codes_phone_idx ON phone_otp_codes (phone);

-- Per-user memories
CREATE TABLE IF NOT EXISTS user_memories (
    id         uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
    user_email text        NOT NULL,
    memory     text        NOT NULL,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS user_memories_email_idx ON user_memories (user_email);
