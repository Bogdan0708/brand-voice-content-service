-- Only create tables for IMPLEMENTED features
-- No phantom tables for vaporware

CREATE TABLE instagram_media (
    id VARCHAR(255) PRIMARY KEY,
    caption TEXT,
    media_type VARCHAR(20) CHECK (media_type IN ('IMAGE', 'VIDEO', 'CAROUSEL_ALBUM')),
    media_url VARCHAR(500),
    timestamp TIMESTAMP NOT NULL,
    like_count INTEGER DEFAULT 0 CHECK (like_count >= 0),
    comments_count INTEGER DEFAULT 0 CHECK (comments_count >= 0),
    engagement_rate FLOAT,
    hashtags TEXT[],
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_instagram_timestamp ON instagram_media(timestamp DESC);
CREATE INDEX idx_instagram_engagement ON instagram_media(engagement_rate DESC);
CREATE INDEX idx_instagram_hashtags ON instagram_media USING GIN(hashtags);

-- Auto-update updated_at trigger (from Claude project - KEEP)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_instagram_media_updated_at
    BEFORE UPDATE ON instagram_media
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Auto-calculate engagement rate (from Claude project - KEEP)
CREATE OR REPLACE FUNCTION calculate_engagement_rate()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.like_count IS NOT NULL AND NEW.comments_count IS NOT NULL THEN
        -- Interaction rate calculation
        NEW.engagement_rate = (NEW.like_count + NEW.comments_count)::FLOAT;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER calculate_instagram_engagement
    BEFORE INSERT OR UPDATE ON instagram_media
    FOR EACH ROW
    EXECUTE FUNCTION calculate_engagement_rate();

CREATE TABLE generated_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic VARCHAR(500) NOT NULL,
    platform VARCHAR(20) NOT NULL CHECK (platform IN ('instagram', 'facebook', 'twitter', 'tiktok')),
    brand_voice VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'scheduled', 'published', 'failed')),
    scheduled_for TIMESTAMP,
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_content_platform_status ON generated_content(platform, status);
CREATE INDEX idx_content_scheduled ON generated_content(scheduled_for) WHERE scheduled_for IS NOT NULL;

CREATE TRIGGER update_generated_content_updated_at
    BEFORE UPDATE ON generated_content
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Instagram insights cache (denormalized for performance)
CREATE TABLE instagram_insights_cache (
    account_id VARCHAR(255),
    date_range VARCHAR(50),
    metric_name VARCHAR(50),
    metric_value JSONB,
    cached_at TIMESTAMP DEFAULT NOW() NOT NULL,
    PRIMARY KEY (account_id, date_range, metric_name)
);

CREATE INDEX idx_insights_cached_at ON instagram_insights_cache(cached_at);

-- Cleanup old cache entries (older than 7 days)
CREATE OR REPLACE FUNCTION cleanup_old_cache()
RETURNS void AS $$
BEGIN
    DELETE FROM instagram_insights_cache WHERE cached_at < NOW() - INTERVAL '7 days';
END;
$$ LANGUAGE plpgsql;
