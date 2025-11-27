from urllib.parse import urlparse

def guess_format(filename: str) -> str:
    ext = filename.lower()
    if ext.endswith(".ttl"):
        return "turtle"
    elif ext.endswith(".rdf") or ext.endswith(".xml"):
        return "xml"
    elif ext.endswith(".jsonld"):
        return "json-ld"
    elif ext.endswith(".nt"):
        return "nt"
    else:
        return "xml"

def is_valid_iri(value: str) -> bool:
    try:
        result = urlparse(value)
        return all([result.scheme, result.netloc])
    except:
        return False