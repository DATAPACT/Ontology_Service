import os
from SPARQLWrapper import SPARQLWrapper, JSON, BASIC, POST

SPARQL_ENDPOINT = "http://188.166.88.64:3030/triplestore/query"
SPARQL_UPDATE_ENDPOINT = "http://188.166.88.64:3030/triplestore/update"

USERNAME = os.environ.get("USERNAME")
PASSWORD = os.environ.get("PASSWORD")

DEFAULT_ONTOLOGY_IRI = "https://eu-upcast.github.io/ontology/repo/defaultontology"
DEFAULT_METADATA_IRI = "https://eu-upcast.github.io/ontology/repo/metadata"


DEFAULT_QUERY_PREFIX = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX odrl: <http://www.w3.org/ns/odrl/2/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX dpvowl: <https://w3id.org/dpv/owl#>
PREFIX dcam: <http://purl.org/dc/dcam/>
PREFIX schema: <http://schema.org/>
"""
def run_sparql_query(query: str):
    sparql = SPARQLWrapper(SPARQL_ENDPOINT)
    sparql.setReturnFormat(JSON)
    sparql.setQuery(query)

    sparql.setHTTPAuth(BASIC)
    sparql.setCredentials(USERNAME, PASSWORD)

    try:
        results = sparql.query().convert()
        return results["results"]["bindings"]
    except Exception as e:
        raise RuntimeError(f"SPARQL query failed: {str(e)}")

def run_ask_query(query: str) -> bool:
    sparql = SPARQLWrapper(SPARQL_ENDPOINT)
    sparql.setReturnFormat(JSON)
    sparql.setQuery(query)

    sparql.setHTTPAuth(BASIC)
    sparql.setCredentials(USERNAME, PASSWORD)

    try:
        results = sparql.query().convert()
        return results
    except Exception as e:
        raise RuntimeError(f"SPARQL ASK query failed: {str(e)}")

def run_sparql_update(update_query: str):
    sparql = SPARQLWrapper(SPARQL_UPDATE_ENDPOINT)
    sparql.setMethod(POST)
    sparql.setQuery(update_query)

    sparql.setHTTPAuth(BASIC)
    sparql.setCredentials(USERNAME, PASSWORD)

    try:
        sparql.query()
    except Exception as e:
        raise RuntimeError(f"SPARQL update failed: {str(e)}")