"""
Neo4j Database Service
Handles all graph database operations for the research paper knowledge graph.
"""
from neo4j import GraphDatabase
from typing import Optional, List, Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()


class Neo4jService:
    """Service class for Neo4j database operations."""
    
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "password")
        self.driver = None
    
    def connect(self):
        """Establish connection to Neo4j database."""
        if not self.driver:
            self.driver = GraphDatabase.driver(
                self.uri, 
                auth=(self.user, self.password)
            )
        return self
    
    def close(self):
        """Close the database connection."""
        if self.driver:
            self.driver.close()
            self.driver = None
    
    def verify_connection(self) -> bool:
        """Verify that the connection to Neo4j is working."""
        try:
            with self.driver.session() as session:
                session.run("RETURN 1")
            return True
        except Exception as e:
            print(f"Neo4j connection failed: {e}")
            return False
    
    # ==========================================
    # Paper Operations
    # ==========================================
    
    def create_paper(self, title: str, abstract: str = None, 
                     year: int = None, venue: str = None,
                     full_text: str = None, job_id: str = None) -> Dict[str, Any]:
        """Create or merge a Paper node."""
        with self.driver.session() as session:
            result = session.run("""
                MERGE (p:Paper {title: $title})
                ON CREATE SET 
                    p.abstract = $abstract,
                    p.year = $year,
                    p.venue = $venue,
                    p.full_text = $full_text,
                    p.job_id = $job_id,
                    p.created_at = datetime()
                ON MATCH SET
                    p.updated_at = datetime()
                RETURN p
            """, title=title, abstract=abstract, year=year, 
                venue=venue, full_text=full_text, job_id=job_id)
            record = result.single()
            return dict(record["p"]) if record else None
    
    # ==========================================
    # Author Operations
    # ==========================================
    
    def create_author(self, name: str, affiliation: str = None) -> Dict[str, Any]:
        """Create or merge an Author node."""
        with self.driver.session() as session:
            result = session.run("""
                MERGE (a:Author {name: $name})
                ON CREATE SET 
                    a.affiliation = $affiliation,
                    a.created_at = datetime()
                RETURN a
            """, name=name, affiliation=affiliation)
            record = result.single()
            return dict(record["a"]) if record else None
    
    def link_author_to_paper(self, author_name: str, paper_title: str) -> bool:
        """Create AUTHORED relationship between Author and Paper."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (a:Author {name: $author_name})
                MATCH (p:Paper {title: $paper_title})
                MERGE (a)-[r:AUTHORED]->(p)
                RETURN r
            """, author_name=author_name, paper_title=paper_title)
            return result.single() is not None
    
    # ==========================================
    # Citation Operations  
    # ==========================================
    
    def create_citation(self, citing_title: str, cited_title: str) -> bool:
        """Create CITES relationship between two papers."""
        with self.driver.session() as session:
            # First ensure cited paper exists (even if just as title placeholder)
            session.run("""
                MERGE (p:Paper {title: $cited_title})
            """, cited_title=cited_title)
            
            # Create the citation relationship
            result = session.run("""
                MATCH (citing:Paper {title: $citing_title})
                MATCH (cited:Paper {title: $cited_title})
                MERGE (citing)-[r:CITES]->(cited)
                RETURN r
            """, citing_title=citing_title, cited_title=cited_title)
            return result.single() is not None
    
    # ==========================================
    # Method/Dataset/Metric/Task Operations
    # ==========================================
    
    def create_method(self, name: str, description: str = None) -> Dict[str, Any]:
        """Create or merge a Method node."""
        with self.driver.session() as session:
            result = session.run("""
                MERGE (m:Method {name: $name})
                ON CREATE SET m.description = $description
                RETURN m
            """, name=name, description=description)
            record = result.single()
            return dict(record["m"]) if record else None
    
    def link_paper_uses_method(self, paper_title: str, method_name: str) -> bool:
        """Create USES_METHOD relationship."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Paper {title: $paper_title})
                MATCH (m:Method {name: $method_name})
                MERGE (p)-[r:USES_METHOD]->(m)
                RETURN r
            """, paper_title=paper_title, method_name=method_name)
            return result.single() is not None
    
    def create_dataset(self, name: str, description: str = None) -> Dict[str, Any]:
        """Create or merge a Dataset node."""
        with self.driver.session() as session:
            result = session.run("""
                MERGE (d:Dataset {name: $name})
                ON CREATE SET d.description = $description
                RETURN d
            """, name=name, description=description)
            record = result.single()
            return dict(record["d"]) if record else None
    
    def link_paper_uses_dataset(self, paper_title: str, dataset_name: str) -> bool:
        """Create USES_DATASET relationship."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Paper {title: $paper_title})
                MATCH (d:Dataset {name: $dataset_name})
                MERGE (p)-[r:USES_DATASET]->(d)
                RETURN r
            """, paper_title=paper_title, dataset_name=dataset_name)
            return result.single() is not None
    
    def create_task(self, name: str, description: str = None) -> Dict[str, Any]:
        """Create or merge a Task node."""
        with self.driver.session() as session:
            result = session.run("""
                MERGE (t:Task {name: $name})
                ON CREATE SET t.description = $description
                RETURN t
            """, name=name, description=description)
            record = result.single()
            return dict(record["t"]) if record else None
    
    def link_paper_addresses_task(self, paper_title: str, task_name: str) -> bool:
        """Create ADDRESSES_TASK relationship."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Paper {title: $paper_title})
                MATCH (t:Task {name: $task_name})
                MERGE (p)-[r:ADDRESSES_TASK]->(t)
                RETURN r
            """, paper_title=paper_title, task_name=task_name)
            return result.single() is not None
    
    # ==========================================
    # Bulk Ingestion (used by app.py)
    # ==========================================
    
    def ingest_paper_data(self, job_id: str, title: str, authors: List[str], 
                          citations: List[str], full_text: str = None,
                          methods: List[str] = None, datasets: List[str] = None,
                          tasks: List[str] = None) -> Dict[str, Any]:
        """
        Ingest a complete paper with all its relationships.
        This is the main method called after PDF processing.
        """
        results = {
            "paper": None,
            "authors_linked": 0,
            "citations_created": 0,
            "methods_linked": 0,
            "datasets_linked": 0,
            "tasks_linked": 0
        }
        
        # Create the paper
        results["paper"] = self.create_paper(
            title=title, 
            full_text=full_text,
            job_id=job_id
        )
        
        # Link authors
        for author_name in authors:
            if author_name.strip():
                self.create_author(author_name.strip())
                if self.link_author_to_paper(author_name.strip(), title):
                    results["authors_linked"] += 1
        
        # Create citation relationships
        for cited_title in citations:
            if cited_title.strip():
                if self.create_citation(title, cited_title.strip()):
                    results["citations_created"] += 1
        
        # Link methods (if extracted by LLM)
        if methods:
            for method_name in methods:
                if method_name.strip():
                    self.create_method(method_name.strip())
                    if self.link_paper_uses_method(title, method_name.strip()):
                        results["methods_linked"] += 1
        
        # Link datasets (if extracted by LLM)
        if datasets:
            for dataset_name in datasets:
                if dataset_name.strip():
                    self.create_dataset(dataset_name.strip())
                    if self.link_paper_uses_dataset(title, dataset_name.strip()):
                        results["datasets_linked"] += 1
        
        # Link tasks (if extracted by LLM)
        if tasks:
            for task_name in tasks:
                if task_name.strip():
                    self.create_task(task_name.strip())
                    if self.link_paper_addresses_task(title, task_name.strip()):
                        results["tasks_linked"] += 1
        
        return results
    
    # ==========================================
    # Query Operations
    # ==========================================
    
    def get_paper_by_title(self, title: str) -> Optional[Dict[str, Any]]:
        """Get a paper and its relationships by title."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Paper {title: $title})
                OPTIONAL MATCH (a:Author)-[:AUTHORED]->(p)
                OPTIONAL MATCH (p)-[:CITES]->(cited:Paper)
                OPTIONAL MATCH (p)-[:USES_METHOD]->(m:Method)
                OPTIONAL MATCH (p)-[:USES_DATASET]->(d:Dataset)
                OPTIONAL MATCH (p)-[:ADDRESSES_TASK]->(t:Task)
                RETURN p,
                       collect(DISTINCT a.name) as authors,
                       collect(DISTINCT cited.title) as citations,
                       collect(DISTINCT m.name) as methods,
                       collect(DISTINCT d.name) as datasets,
                       collect(DISTINCT t.name) as tasks
            """, title=title)
            record = result.single()
            if record:
                paper_data = dict(record["p"])
                paper_data["authors"] = record["authors"]
                paper_data["citations"] = record["citations"]
                paper_data["methods"] = record["methods"]
                paper_data["datasets"] = record["datasets"]
                paper_data["tasks"] = record["tasks"]
                return paper_data
            return None
    
    def get_all_papers(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all papers with basic info."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Paper)
                OPTIONAL MATCH (a:Author)-[:AUTHORED]->(p)
                RETURN p.title as title, p.job_id as job_id,
                       collect(DISTINCT a.name) as authors
                ORDER BY p.created_at DESC
                LIMIT $limit
            """, limit=limit)
            return [dict(record) for record in result]
    
    def find_related_papers(self, title: str) -> List[Dict[str, Any]]:
        """Find papers related through shared authors, methods, or citations."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Paper {title: $title})
                OPTIONAL MATCH (p)<-[:AUTHORED]-(a:Author)-[:AUTHORED]->(related:Paper)
                WHERE related.title <> $title
                OPTIONAL MATCH (p)-[:USES_METHOD]->(m:Method)<-[:USES_METHOD]-(method_related:Paper)
                WHERE method_related.title <> $title
                OPTIONAL MATCH (p)-[:CITES]->(cited:Paper)
                OPTIONAL MATCH (citing:Paper)-[:CITES]->(p)
                WITH collect(DISTINCT related) + collect(DISTINCT method_related) + 
                     collect(DISTINCT cited) + collect(DISTINCT citing) as all_related
                UNWIND all_related as r
                RETURN DISTINCT r.title as title, r.job_id as job_id
                LIMIT 20
            """, title=title)
            return [dict(record) for record in result]


# Singleton instance
_neo4j_service = None

def get_neo4j_service() -> Neo4jService:
    """Get or create the Neo4j service singleton."""
    global _neo4j_service
    if _neo4j_service is None:
        _neo4j_service = Neo4jService()
        _neo4j_service.connect()
    return _neo4j_service
