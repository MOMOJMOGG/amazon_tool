-- Competition Tables Setup for Amazon Product Monitoring Tool
-- Run this script in your PostgreSQL database to enable competition features

-- Create schemas if they don't exist
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS mart;

-- Core table: Competitor relationships
CREATE TABLE IF NOT EXISTS core.competitor_links (
    asin_main VARCHAR(10) NOT NULL,
    asin_comp VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (asin_main, asin_comp)
);

-- Index for performance
CREATE INDEX IF NOT EXISTS idx_competitor_links_main 
ON core.competitor_links(asin_main);

-- Mart table: Daily competitor comparisons
CREATE TABLE IF NOT EXISTS mart.competitor_comparison_daily (
    asin_main VARCHAR(10) NOT NULL,
    asin_comp VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    price_diff NUMERIC(10,2),
    bsr_gap INTEGER,
    rating_diff NUMERIC(3,2),
    reviews_gap INTEGER,
    buybox_diff NUMERIC(10,2),
    extras JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (asin_main, asin_comp, date)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_competitor_comparison_main_date 
ON mart.competitor_comparison_daily(asin_main, date);

-- Mart table: Competition reports (AI-generated)
CREATE TABLE IF NOT EXISTS mart.competition_reports (
    id SERIAL PRIMARY KEY,
    asin_main VARCHAR(10) NOT NULL,
    version INTEGER NOT NULL,
    summary JSONB NOT NULL,
    evidence JSONB,
    model VARCHAR(50),
    generated_at TIMESTAMP DEFAULT NOW()
);

-- Index for performance
CREATE INDEX IF NOT EXISTS idx_competition_reports_asin_version 
ON mart.competition_reports(asin_main, version DESC);

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Competition tables created successfully!';
    RAISE NOTICE 'You can now use the competition features in the demo app.';
END $$;