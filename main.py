# main.py

from fastapi import FastAPI, Query, HTTPException, UploadFile, File, Form, Body
from fastapi.responses import JSONResponse
from rdflib import Graph, plugin, URIRef, Literal
from rdflib.serializer import Serializer
import time, random
from utils.sparql_client import DEFAULT_QUERY_PREFIX, DEFAULT_METADATA_IRI, DEFAULT_ONTOLOGY_IRI,  run_sparql_query, run_sparql_update, run_ask_query
from utils.helper_functions import guess_format, is_valid_iri
from typing import Optional, Union
from rdflib.namespace import XSD
from pydantic import BaseModel, Field

app = FastAPI(title="Ontology Service", version="1.0", root_path="/ontology-service")

@app.post("/store_ontology")
async def store_ontology(
    ontology_content: UploadFile = File(..., description="Ontology RDF file"),
    user_name: str = Form(..., description="Name of the user uploading the ontology"),
    tool_id: str = Form(..., description="ID of the tool making the call")
):
    # Validate uploaded ontology
    ontology_data = await ontology_content.read()
    g = Graph()
    g.parse(data=ontology_data.decode('utf-8'), format=guess_format(ontology_content.filename))

    timestamp = int(time.time() * 1000)
    random_int = random.randint(0, 1000)
    repo_id = f"https://eu-upcast.github.io/ontology/repo/{timestamp}{random_int}"
    graph_uri = repo_id

    triples = g.serialize(format='nt')
    insert_query = f"""
    INSERT DATA {{
        GRAPH <{graph_uri}> {{
            {triples}
        }}
    }}
    """
    run_sparql_update(insert_query)

    user_obj = f"<{user_name}>" if is_valid_iri(user_name) else f'"{user_name}"'
    tool_obj = f"<{tool_id}>" if is_valid_iri(tool_id) else f'"{tool_id}"'

    # Format timestamp as ISO 8601 string
    from datetime import datetime
    iso_timestamp = datetime.fromtimestamp(timestamp / 1000).isoformat() + "Z"

    core_metadata_insert_query = f"""
    PREFIX prov: <http://www.w3.org/ns/prov#>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    INSERT DATA {{
      GRAPH <{DEFAULT_METADATA_IRI}> {{
        <{graph_uri}> prov:wasAttributedTo {user_obj} .
        <{graph_uri}> prov:wasGeneratedBy {tool_obj} .
        <{graph_uri}> dcterms:created "{iso_timestamp}"^^xsd:dateTime .
      }}
    }}
    """
    run_sparql_update(core_metadata_insert_query)

    return {"repository_id": repo_id}


@app.post("/delete_ontology")
async def delete_ontology(
    ontology_ID: str = Body(..., embed=True, description="IRI of the ontology to delete"),
    user_name: str = Body(..., embed=True, description="Name of the user attempting the deletion"),
    tool_id: str = Body(..., embed=True, description="ID of the tool making the call")
):
    if not is_valid_iri(ontology_ID):
        raise HTTPException(status_code=400, detail="Invalid ontology IRI provided.")

    graph_uri = URIRef(ontology_ID)

    # 1) Check if the ontology graph exists
    check_query = f"""
    ASK WHERE {{
        GRAPH <{graph_uri}> {{ ?s ?p ?o }}
    }}
    """
    exists = run_ask_query(check_query)
    check_query_metadata = f"""
        ASK WHERE {{
            GRAPH <{DEFAULT_METADATA_IRI}> {{ <{graph_uri}> ?p ?o }}
        }}
        """
    exists_metadata = run_ask_query(check_query_metadata)
    if not (exists.get("boolean") | exists_metadata.get("boolean")):
        raise HTTPException(status_code=404, detail="ontology_not_found")

    # 2) Check if the user is the owner
    user_obj = f"<{user_name}>" if is_valid_iri(user_name) else f'"{user_name}"'

    ownership_query = f"""
    PREFIX prov: <http://www.w3.org/ns/prov#>
    ASK WHERE {{
        GRAPH <{DEFAULT_METADATA_IRI}> {{
            <{graph_uri}> prov:wasAttributedTo {user_obj} .
        }}
    }}
    """
    is_owner = run_ask_query(ownership_query)
    if not is_owner.get("boolean"):
        raise HTTPException(status_code=403, detail="no_ontology_edit_rights")

    # 3) Delete the ontology graph and metadata
    delete_query = f"""
    DROP GRAPH <{graph_uri}> ;
    """
    run_sparql_update(delete_query)

    delete_metadata_query = f"""
    WITH <{DEFAULT_METADATA_IRI}>
    DELETE {{ <{graph_uri}> ?p ?o . }}
    WHERE {{ <{graph_uri}> ?p ?o . }}
        """
    run_sparql_update(delete_metadata_query)
    return JSONResponse(status_code=200, content={"detail": "Ontology and metadata successfully deleted."})


@app.get("/get_own_ontologies")
async def get_own_ontologies(
    user_name: str = Query(..., description="Name of the user"),
    tool_id: Optional[str] = Query(None, description="ID of the tool used")
):
    if not user_name:
        raise HTTPException(status_code=400, detail="Username is required.")

    user_obj = f"<{user_name}>" if is_valid_iri(user_name) else f'"{user_name}"'
    tool_filter = ""

    if tool_id:
        tool_obj = f"<{tool_id}>" if is_valid_iri(tool_id) else f'"{tool_id}"'
        tool_filter = f"    ?n prov:wasGeneratedBy {tool_obj} .\n"

    query = f"""
    PREFIX prov: <http://www.w3.org/ns/prov#>

    SELECT ?n
    WHERE {{
        GRAPH <{DEFAULT_METADATA_IRI}> {{
            ?n prov:wasAttributedTo {user_obj} .
            {tool_filter}
        }}
    }}
    """

    results = run_sparql_query(query)

    if isinstance(results, dict):
        bindings = results.get("results", {}).get("bindings", [])
    else:
        bindings = results

    ontologies = [binding["n"]["value"] for binding in bindings]

    return {"ontologies": ontologies}



class OntologyIDsRequest(BaseModel):
    ontology_IDs: Optional[list[str]] = None

@app.post("/get_actions")
async def get_actions(request: OntologyIDsRequest):
    ontology_ids = request.ontology_IDs or []

    # Validate IRIs only if provided
    invalid_iris = [iri for iri in ontology_ids if not is_valid_iri(iri)]
    if invalid_iris:
        raise HTTPException(status_code=400, detail=f"Invalid IRIs: {invalid_iris}")

    # Conditionally build FROM clauses
    from_clauses = "\n".join(f"FROM <{iri}>" for iri in ontology_ids)

    query = DEFAULT_QUERY_PREFIX + f"""
    SELECT DISTINCT ?node ?label 
    FROM <{DEFAULT_ONTOLOGY_IRI}>
    {from_clauses}
    WHERE {{
        ?node rdf:type odrl:Action . 
        ?node rdfs:label ?label . 
    }} ORDER BY ?label
    """

    results = run_sparql_query(query)

    bindings = results.get("results", {}).get("bindings", []) if isinstance(results, dict) else results

    actions = [
        {
            "value": binding["node"]["value"],
            "label": binding["label"]["value"]
        }
        for binding in bindings
    ]

    return {"actions": actions}

@app.post("/get_purposes")
async def get_purposes(request: OntologyIDsRequest):
    ontology_ids = request.ontology_IDs or []

    # Validate IRIs only if provided
    invalid_iris = [iri for iri in ontology_ids if not is_valid_iri(iri)]
    if invalid_iris:
        raise HTTPException(status_code=400, detail=f"Invalid IRIs: {invalid_iris}")

    # Conditionally build FROM clauses
    from_clauses = "\n".join(f"FROM <{iri}>" for iri in ontology_ids)

    query = DEFAULT_QUERY_PREFIX+f"""
    SELECT DISTINCT ?node ?label
    FROM <{DEFAULT_ONTOLOGY_IRI}>
    {from_clauses}
        WHERE {{
            ?node rdf:type dpvowl:Purpose .
            ?node ( rdfs:label | skos:prefLabel ) ?label. 
        }}
    """

    results = run_sparql_query(query)

    bindings = results.get("results", {}).get("bindings", []) if isinstance(results, dict) else results

    purposes = [
        {
            "value": binding["node"]["value"],
            "label": binding["label"]["value"]
        }
        for binding in bindings
    ]

    return {"purposes": purposes}

@app.post("/get_actors")
async def get_actors(request: OntologyIDsRequest):
    ontology_ids = request.ontology_IDs or []

    # Validate IRIs only if provided
    invalid_iris = [iri for iri in ontology_ids if not is_valid_iri(iri)]
    if invalid_iris:
        raise HTTPException(status_code=400, detail=f"Invalid IRIs: {invalid_iris}")

    # Conditionally build FROM clauses
    from_clauses = "\n".join(f"FROM <{iri}>" for iri in ontology_ids)

    query = DEFAULT_QUERY_PREFIX+f"""
    SELECT DISTINCT ?node ?label
    FROM <{DEFAULT_ONTOLOGY_IRI}>
    {from_clauses}
        WHERE {{
            ?node rdfs:subClassOf* dpvowl:Entity .
            ?node ( rdfs:label | skos:prefLabel ) ?label. 
        }}
    """

    results = run_sparql_query(query)

    bindings = results.get("results", {}).get("bindings", []) if isinstance(results, dict) else results

    actors = [
        {
            "value": binding["node"]["value"],
            "label": binding["label"]["value"]
        }
        for binding in bindings
    ]

    return {"actors": actors}

@app.post("/get_assets")
async def get_assets(request: OntologyIDsRequest):
    ontology_ids = request.ontology_IDs or []

    # Validate IRIs only if provided
    invalid_iris = [iri for iri in ontology_ids if not is_valid_iri(iri)]
    if invalid_iris:
        raise HTTPException(status_code=400, detail=f"Invalid IRIs: {invalid_iris}")

    # Conditionally build FROM clauses
    from_clauses = "\n".join(f"FROM <{iri}>" for iri in ontology_ids)

    query = DEFAULT_QUERY_PREFIX+f"""
    SELECT DISTINCT ?node ?label
    FROM <{DEFAULT_ONTOLOGY_IRI}>
    {from_clauses}
        WHERE {{
            ?node rdfs:subClassOf* odrl:Asset .
            ?node ( rdfs:label | skos:prefLabel ) ?label. 
        }}
    """

    results = run_sparql_query(query)

    bindings = results.get("results", {}).get("bindings", []) if isinstance(results, dict) else results

    assets = [
        {
            "value": binding["node"]["value"],
            "label": binding["label"]["value"]
        }
        for binding in bindings
    ]

    return {"assets": assets}


class EntityRefinementsRequest(BaseModel):
    ontology_IDs: Optional[list[str]] = Field(default_factory=list)
    entity_IRI: str

    class Config:
        schema_extra = {
            "example": {
                "ontology_IDs": [
                    "https://eu-upcast.github.io/ontology/repo/defaultontology"
                ],
                "entity_IRI": "https://w3id.org/dpv/owl#AcademicResearch"
            }
        }

@app.post("/get_entity_refinements")
async def get_entity_refinements(request: EntityRefinementsRequest):
    ontology_ids = request.ontology_IDs or []

    # Validate IRIs
    invalid_iris = [iri for iri in ontology_ids if not is_valid_iri(iri)]
    if not is_valid_iri(request.entity_IRI):
        invalid_iris.append(request.entity_IRI)

    if invalid_iris:
        raise HTTPException(status_code=400, detail=f"Invalid IRIs: {invalid_iris}")

    # Build FROM clauses
    from_clauses = "\n".join(f"FROM <{iri}>" for iri in ontology_ids)

    query = DEFAULT_QUERY_PREFIX + f"""
    SELECT DISTINCT ?node ?label
    FROM <{DEFAULT_ONTOLOGY_IRI}>
    {from_clauses}
    WHERE {{
        <{request.entity_IRI}> rdf:type? / ( skos:broader? | rdfs:subClassOf? ) ?class .
          ?node ( rdfs:domain | schema:domainIncludes | dcam:domainIncludes ) / ( skos:broader | rdfs:subClassOf)? ?class ;
                    ( rdfs:label | skos:prefLabel ) ?label .
        
    }}
    """

    results = run_sparql_query(query)
    bindings = results.get("results", {}).get("bindings", []) if isinstance(results, dict) else results

    left_operands = [
        {
            "value": binding["node"]["value"],
            "label": binding["label"]["value"]
        }
        for binding in bindings
    ]

    return {"left_operands": left_operands}


@app.post("/get_constraints")
async def get_assets(request: OntologyIDsRequest):
    ontology_ids = request.ontology_IDs or []

    # Validate IRIs only if provided
    invalid_iris = [iri for iri in ontology_ids if not is_valid_iri(iri)]
    if invalid_iris:
        raise HTTPException(status_code=400, detail=f"Invalid IRIs: {invalid_iris}")

    # Conditionally build FROM clauses
    from_clauses = "\n".join(f"FROM <{iri}>" for iri in ontology_ids)

    query = DEFAULT_QUERY_PREFIX+f"""
    SELECT DISTINCT ?node ?label
    FROM <{DEFAULT_ONTOLOGY_IRI}>
    {from_clauses}
        WHERE {{
          ?node rdf:type odrl:LeftOperand ;
                    ( rdfs:label | skos:prefLabel ) ?label .
        }}
    """

    results = run_sparql_query(query)

    bindings = results.get("results", {}).get("bindings", []) if isinstance(results, dict) else results

    left_operands = [
        {
            "value": binding["node"]["value"],
            "label": binding["label"]["value"]
        }
        for binding in bindings
    ]

    return {"left_operands": left_operands}


@app.post("/get_operators")
async def get_assets(request: OntologyIDsRequest):
    ontology_ids = request.ontology_IDs or []

    # Validate IRIs only if provided
    invalid_iris = [iri for iri in ontology_ids if not is_valid_iri(iri)]
    if invalid_iris:
        raise HTTPException(status_code=400, detail=f"Invalid IRIs: {invalid_iris}")

    return {
          "left_operand": [
            {
              "value": "http://www.w3.org/ns/odrl/2/eq",
              "label": "Equal to"
            },
            {
              "value": "http://www.w3.org/ns/odrl/2/gt",
              "label": "Greater than"
            },
            {
              "value": "http://www.w3.org/ns/odrl/2/gteq",
              "label": "Greater than or equal to"
            },
            {
              "value": "http://www.w3.org/ns/odrl/2/hasPart",
              "label": "Has part"
            },
            {
              "value": "http://www.w3.org/ns/odrl/2/isA",
              "label": "Is a"
            },
            {
              "value": "http://www.w3.org/ns/odrl/2/isAllOf",
              "label": "Is all of"
            },
            {
              "value": "http://www.w3.org/ns/odrl/2/isAnyOf",
              "label": "Is any of"
            },
            {
              "value": "http://www.w3.org/ns/odrl/2/isNoneOf",
              "label": "Is none of"
            },
            {
              "value": "http://www.w3.org/ns/odrl/2/isPartOf",
              "label": "Is part of"
            },
            {
              "value": "http://www.w3.org/ns/odrl/2/lt",
              "label": "Less than"
            },
            {
              "value": "http://www.w3.org/ns/odrl/2/lteq",
              "label": "Less than or equal to"
            },
            {
              "value": "http://www.w3.org/ns/odrl/2/neq",
              "label": "Not equal to"
            }
          ]
        }