// ===================================
// Initial Schema - Constraints
// ===================================

// Paper nodes must have unique titles
CREATE CONSTRAINT paper_title_unique IF NOT EXISTS
FOR (p:Paper) REQUIRE p.title IS UNIQUE;

// Author nodes must have unique names
CREATE CONSTRAINT author_name_unique IF NOT EXISTS
FOR (a:Author) REQUIRE a.name IS UNIQUE;

// Method nodes must have unique names
CREATE CONSTRAINT method_name_unique IF NOT EXISTS
FOR (m:Method) REQUIRE m.name IS UNIQUE;

// Dataset nodes must have unique names
CREATE CONSTRAINT dataset_name_unique IF NOT EXISTS
FOR (d:Dataset) REQUIRE d.name IS UNIQUE;

// Metric nodes must have unique names
CREATE CONSTRAINT metric_name_unique IF NOT EXISTS
FOR (met:Metric) REQUIRE met.name IS UNIQUE;

// Task nodes must have unique names
CREATE CONSTRAINT task_name_unique IF NOT EXISTS
FOR (t:Task) REQUIRE t.name IS UNIQUE;