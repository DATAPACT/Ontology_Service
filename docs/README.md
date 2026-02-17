# Ontology Service

Powered by

[![UoSLOGO](./images/UniSouthampton.png)](https://dips.soton.ac.uk/#home)


## **General Description**

This is a docker container of a FastAPI implementation of an Ontology Service that enables:
* the storage and management of ontologies,
* the storage and management of ontology metadata (e.g. the user who created it and when) and 
* functions to extract ODRL relevant terms (e.g. lists of actions or purposes) from specific ontologies.


## **Commercial Information**

| Organisation (s) | License Nature | License |
| --- | --- | --- |
| University of Southampton  | Open Source | MIT Licence |


## **How To Install**

### Requirements

Docker

### Software

FastAPI, Python

### Triplestore Configuration

This service requires access to a SPARQL endpoint that enables select, ask and update queries. It was tested with Fuseki, with username and password authentication for the endpoint, but it should work with any other triplestore that exposes a SPARQL endpoint.

The sparql_client.py file should be configured to point to the triplestore.
The requirements for the triplestores are as follows:
* Accept SPARQL and SPARQL UPDATE queries
* Contains a default graph with the default ontology already loaded (which will be used to return default results to the ODRL-sepcific queries even if no domain specific ontology has been selected)

Configuration: 
* SPARQL_ENDPOINT the endpoint for the sparql queries
* SPARQL_UPDATE_ENDPOINT the endpoint for the sparql update queries
* DEFAULT_ONTOLOGY_IRI the IRI for the named graph where the default ontology has been loaded (optional configuration, you can keep the default value)
* DEFAULT_METADATA_IRI the IRI for the named graph that will contain the metadata of the ontologies (optional configuration, you can keep the default value)

You can configure the port the docker container will listen to in the `docker-compose.yml` file. By default it is 8009.

### Authentication configuration
The docker compose file must include a .env file with the following environment variables.
* USERNAME the username of the user account to access the triplestore
* PASSWORD the password of the user account to access the triplestore

### Docker Setup Instructions

* Configure the files as mentioned above
* Build and run the docker container as usual (e.g. `docker compose build` and `docker compose up`)
* The API documentation will then be available under the `/docs` sub path, such as `http://127.0.0.1:8000/docs`

### Manual Installation Instructions

If you are not using docker, you can run the project as follows:
* Configure the files as mentioned above
* Install required libraries using `pip install fastapi uvicorn SPARQLWrapper python-multipart`
* Run FastAPI `uvicorn main:app --reload` from the project directory
* See the API here `http://127.0.0.1:8000/docs`

## Expected KPIs

These KPI relate to the Policy Service suite of tools, which include the Policy Editor, the Policy Enginge and the Ontology Service.

| What | How | Values |
| --- | --- | --- |
| 1) Policy management expressiveness: ability to represent data processing regulations in a machine processable form. 2) Policy-based Data Access Control Accuracy | 1) analysis of an existing large (>100) corpus of data sharing/data processing agreements 2) Experiments over at least two policies, asking the pilots to express (in machine processable form, through our tool's interface) a sample (min 20 each) of( access requests (evenly distributed as requests to be permitted, and to be denied).  | 1) Ability to move >15% of contractual clauses and privacy policies in an average agreement to machine-processable form. 2) High accuracy (>90%) in predicting the correct access control response  |


