# Copyright 2015 Sam Thursfield
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.


'''Helpers for working with Software Information Ontology data.'''


import rdflib


class SoftwareNamespace(rdflib.Namespace):
    '''Suggested naming scheme for use with Software Integration Ontology.

    The locations of the resources contain the type of the resource, so
    for example source 'foo' is 'sources/foo'. This prevents any unexpected
    name collisions. Some tools might enforce a flat namespace, but at the
    level of an abstract data model we shouldn't enforce that.

    '''
    def build_instructions(self, name):
        '''Returns a URIRef for a specific build instruction.'''
        # FIXME: loong url
        return self.term('build-instructions/' + name)

    def git_object(self, repo_uriref, object_id):
        '''Returns a URIRef for a Git commit or tree in a given repo.'''
        assert isinstance(repo_uriref, rdflib.URIRef)
        return repo_uriref + '/' + object_id

    def git_repository(self, repo_location):
        '''Returns a URIRef for a Git repository based on its location.'''
        # FIXME: rubbish
        return self.term('git/' + repo_location)

    def group(self, group_name):
        '''Returns a URIRef for a Group with the given name.'''
        return self.term('groups/' + group_name)

    def source(self, source_name):
        '''Returns a URIRef for a Source with the given name.'''
        return self.term('sources/' + source_name)

    def __getattr__(self, attr):
        # By default RDFLib namespaces are 'open', but we can only handle the
        # types of resource that we actually know about.
        raise KeyError("Not a known software resource type: %s" % attr)


def serialize_to_json_ld(rdflib_graph):
    context = {
        "@vocab": SOFTWARE,
        "@language": "en"
    }
    # requires rdflib-jsonld Python module.
    return rdflib_graph.serialize(format='json-ld', indent=4, context=context)


def serialize_to_rdfxml(rdflib_graph):
    return rdflib_graph.serialize(format='xml', indent=4)
