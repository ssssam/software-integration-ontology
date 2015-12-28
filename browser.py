import rdflib_web.lod
from flask import Flask

import rdflib

graph = rdflib.Graph()
#graph.load('foo.json', format='json-ld')
graph.load('foo.rdfxml', format='xml')

import pdb
pdb.set_trace()

app = rdflib_web.lod.get(graph)

app.run(host="0.0.0.0", debug=True)

