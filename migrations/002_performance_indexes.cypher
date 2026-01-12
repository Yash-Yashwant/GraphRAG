// ===================================
// Performance Indexes
// ===================================


// Index on paper year for temporal queries
CREATE INDEX paper_year_index IF NOT EXISTS ON (p:Paper) ON (p.year);


// Index on paper venue for filtering 
CREATE INDEX paper_venue_index IF NOT EXISTS ON (p:Paper) ON (p.venue);

// Index on author affiliation
CREATE INDEX author_affiliation_index IF NOT EXISTS ON (a:Author) ON (a.affiliation);

// Full-text search on paper titles
CREATE FULLTEXT INDEX paper_text_search IF NOT EXISTS
FOR (p:Paper) ON EACH [p.title, p.abstract];