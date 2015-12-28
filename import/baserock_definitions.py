#!/usr/bin/env python3
# Copyright (C) 2015  Codethink Limited
# Copyright 2015 Sam Thursfield
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.


'''Parser for the Baserock Definitions format.

This code understands the syntax of Baserock Definitions format version 5.

The current version of the Baserock Definitions format is defined at:

    http://wiki.baserock.org/definitions/current

'''


import rdflib
import rdflib.collection
import yaml

import argparse
import logging
import os
import sys
import warnings

import helpers


DEFAULT_URL = \
    'https://git.baserock.org/cgi-bin/cgit.cgi/baserock/baserock/definitions'

DUBLIN_CORE = rdflib.Namespace('http://purl.org/dc/terms/')
RDF = rdflib.RDF
SOFTWARE = rdflib.namespace.Namespace(
    'http://www.baserock.org/software-integration-ontology#')


def argument_parser():
    parser = argparse.ArgumentParser(
        description="Parse a Baserock definitions repository")
    parser.add_argument('input_location', type=str,
                        help="Path to the root of the definitions repository")
    parser.add_argument('output_location', type=str,
                        help="Location of the resulting resources (base URI)")
    return parser


def parse_morph_file(path):
    '''Parse an individual .morph file.

    This function does a tiny amount of validation: checking the 'name' and
    'type' fields.

    Returns a Python dict with the entire contents of the file deserialised
    from YAML.

    '''
    with open(path) as f:
        text = f.read()
    contents = yaml.safe_load(text)
    assert 'name' in contents
    assert contents['kind'] in ['cluster', 'system', 'stratum', 'chunk']
    return contents


def get_name_from_morph_file(path):
    '''Returns the 'name' defined in a specific .morph file.

    This is a convenience function for resolving places where one .morph file
    in a set references another one.

    '''
    contents = parse_morph_file(path)
    return contents['name']


class BaserockSoftwareNamespace(helpers.SoftwareNamespace):
    '''Helpers to construct URIs for Baserock entities.

    The Baserock definitions data model doesn't map exactly to the
    software-integration-ontology. We need to do further namespacing
    for Baserock entities to make sure names do not clash.

    '''

    def chunk(self, stratum_source_uriref, chunk_source_name):
        assert isinstance(stratum_source_uriref, rdflib.URIRef)
        return stratum_source_uriref + '/' + chunk_source_name

    def chunk_artifact(self, stratum_artifact_uriref, chunk_artifact_name):
        assert isinstance(stratum_artifact_uriref, rdflib.URIRef)
        return stratum_artifact_uriref + '/' + chunk_artifact_name

    def cluster(self, cluster_name):
        return self.group('clusters/' + cluster_name)

#    def command_sequence(self, chunk_uriref, sequence_name):
#        # We use '-' rather than '/' between chunk name and sequence name,
#        # mainly because the rdflib_web browser tool goes nuts if you have
#        # many resources with the same 'basename'. If we used '/' then there
#        # would be hundreds of URIs ending with '.../install-commands',
#        # '.../build-commands' etc.
#        chunk_name = os.path.basename(chunk_uriref)
#        return self.term('commands/' + chunk_name + '-' + sequence_name)

    def stratum(self, stratum_name):
        return self.group('strata/' + stratum_name)

    def stratum_artifact(self, stratum_uriref, artifact_name):
        assert isinstance(stratum_uriref, rdflib.URIRef)
        return stratum_uriref + '/products/' + artifact_name

    def system(self, system_name):
        return self.group('systems/' + system_name)

    def system_artifact(self, system_name, artifact_name):
        return self.group('systems/' + system_name + '-' + artifact_name)

#    def system_deployment(self, cluster_uriref, label):
#        assert isinstance(cluster_uriref, rdflib.URIRef)
#        return cluster_uriref + '/' + label


def ordered(graph, value_list, list_uriref=None):
    '''Create an ordered RDF collection from a list of values.

    This uses the rdf:Seq class to represent the ordered list. The rdf:Seq
    class is apparently deprecated. However, the alternatives (rdf:List, or
    the Ordered List Ontology) are more verbose.

    Further reading:
        - http://www.w3.org/2011/rdf-wg/track/issues/77
        - http://purl.org/ontology/olo/core

    To define an ordered list in RDF, you need an identifier for the list
    itself. By default this function will create a 'blank node', which will end
    up with a random unique URI when serialised. To make serialised data more
    readable you can pass in your own rdflib.URIRef term to identify the list.

    '''
    node = list_uriref or rdflib.BNode()
    graph.add((node, RDF.type, RDF.Seq))
    for i, value in enumerate(value_list):
        index = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#_%i' % (i + 1)
        graph.add((node, rdflib.URIRef(index), rdflib.Literal(value)))
    return node


def to_property(name):
    '''Convert a normal property name to stupidCamelCase.'''
    property_name = []
    hyphen = False
    for char in name:
        if char == '-':
            hyphen = True
        else:
            if hyphen:
                property_name.append(char.upper())
            else:
                property_name.append(char)
            hyphen = False
    return ''.join(property_name)


class BaserockDefinitionsImporter():
    def __init__(self, base_uri):
        self.ns = BaserockSoftwareNamespace(base_uri)

        self.graph = rdflib.Graph()
        self.graph.bind('software', SOFTWARE)

    def new_resource(self, uriref, types=[]):
        '''Create a new resource, stored in 'graph' and identified by 'uriref'.

        Returns an rdflib.resource.Resource instance which can be used to query
        and update the information about the resource that is stored in 'graph'.

        '''
        entity = self.graph.resource(uriref)
        for rdf_type in types:
            entity.set(RDF.type, rdf_type)
        return entity

    def artifacts_for_stratum(self, source_name, include_list=[]):
        # FIXME: need to include all strata if 'include_list' isn't passed,
        # which is difficult because they might not all be loaded yet ...
        # so for now I cheat and just assume -runtime and -devel. If there
        # are extra artifacts for the stratum they won't be incuded by
        # default. I'm not sure if this is how Morph behaves or not.
        if include_list is None:
            include_list = ['%s-runtime' % source_name,
                            '%s-devel' % source_name]

        result = []
        for artifact in include_list:
            artifact_uriref = self.ns.stratum_artifact(
                self.ns.stratum(source_name), artifact)
            result.append(artifact_uriref)
        return result

    def artifacts_for_chunk(self, stratum_artifact_uriref,
                            chunk_source_name, include_list=None):
        # FIXME: need to read DEFAULTS instead of hardcoding this,
        # and you need to allow for custom artifacts in the chunk .morph.
        if include_list is None:
            include_list = ['%s-bins' % chunk_source_name,
                            '%s-debug' % chunk_source_name,
                            '%s-devel' % chunk_source_name,
                            '%s-doc' % chunk_source_name,
                            '%s-libs' % chunk_source_name,
                            '%s-locale' % chunk_source_name,
                            '%s-misc' % chunk_source_name]

        result = []
        for artifact in include_list:
            artifact_uriref = self.ns.chunk_artifact(
                stratum_artifact_uriref, artifact)
            result.append(artifact_uriref)
        return result

    def load_all_morphologies(self, path='.'):
        '''Load Baserock Definitions serialisation format V5 as an RDFLib 'graph'.

        This code does very little validation, so the 'graph' that it returns
        may not fully make sense according to the Baserock data model.

        '''
        logging.info('Parsing .morph files...')
        for dirname, dirnames, filenames in os.walk(path):
            if '.git' in dirnames:
                dirnames.remove('.git')
            for filename in sorted(filenames):
                if filename.endswith('.morph'):
                    try:
                        self.load_morph(path, os.path.join(dirname, filename))
                    except KeyError as e:
                        raise RuntimeError("Error while loading %s: %s" % (filename, e))

        return self.graph

    def load_morph(self, toplevel_path, filename):
        try:
            contents = parse_morph_file(filename)
        except Exception as e:
            warnings.warn("Problem loading %s: %s" % (filename, e))

        entity = None

        if contents['kind'] == 'chunk':
            #chunk_uriref = self.ns.chunk(contents['name'])
            #entity = chunk = new_resource(graph, chunk_uriref, BASEROCK.Chunk)

            #def set_command_sequence(resource, name):
            #    if name in contents:
            #        property = BASEROCK.term(to_property(name))
            #        list_node = self.ns.command_sequence(resource.identifier, name)
            ##        resource.set(property,
            #                     ordered(graph, contents[name], list_node))

            #set_command_sequence(chunk, 'pre-configure-commands')
            #set_command_sequence(chunk, 'configure-commands')
            #set_command_sequence(chunk, 'post-configure-commands')
            ##set_command_sequence(chunk, 'pre-build-commands')
            #set_command_sequence(chunk, 'build-commands')
            #set_command_sequence(chunk, 'post-build-commands')
            #set_command_sequence(chunk, 'pre-install-commands')
            #set_command_sequence(chunk, 'install-commands')
            #set_command_sequence(chunk, 'post-install-commands')
            pass

        elif contents['kind'] == 'stratum':
            self.process_stratum(toplevel_path, contents)

        elif contents['kind'] == 'system':
            self.process_system(contents)

        elif contents['kind'] == 'cluster':
            # Clusters are ignored.
            pass

        #if 'description' in contents:
        #    entity.set(DUBLIN_CORE.description,
        #               rdflib.Literal(contents['description']))

        # FIXME: comments from the .yaml file are lost ... as a quick solution,
        # you could manually find every line from the YAML that starts with a
        # '#' and dump that into a property. Or ruamel.yaml might help?

    def process_stratum(self, toplevel_path, contents):
        source_uriref = self.ns.stratum(contents['name'])
        entity = source = self.new_resource(
            source_uriref, types=[SOFTWARE.BuildInstructions])

        for entry in contents.get('build-depends', []):
            build_dep_file = os.path.join(toplevel_path, entry['morph'])
            build_dep_name = get_name_from_morph_file(build_dep_file)
            build_dep_artifacts = self.artifacts_for_stratum(build_dep_name)
            for build_dep_uriref in build_dep_artifacts:
                source.add(SOFTWARE.buildRequires, build_dep_uriref)

        artifacts = []
        for entry in contents.get('products', []):
            artifact_uri = self.ns.stratum_artifact(
                source_uriref, entry['artifact'])
            artifact = self.new_resource(
                artifact_uri, types=[SOFTWARE.Group, SOFTWARE.Artifact])
            if 'include' in entry:
                # To handle 'include', we need to actually run the splitting
                # rules against all the chunks that exist.
                warnings.warn(
                    "Ignoring 'include' list for %s" % artifact_uri)
            artifacts.append(artifact)
            source.add(SOFTWARE.producesArtifact, artifact)

        for entry in contents.get('chunks', []):
            if 'morph' in entry:
                chunk_file = os.path.join(toplevel_path, entry['morph'])
                chunk_name = get_name_from_morph_file(chunk_file)
                if chunk_name != entry['name']:
                    warnings.warn(
                        "Chunk name %s in stratum %s doesn't match "
                        "name from %s" % (entry['name'], source_uriref,
                                          entry['morph']))
            else:
                chunk_name = entry['name']

            chunk_source_uriref = self.ns.chunk(source_uriref, chunk_name)
            chunk_source = self.new_resource(
                chunk_source_uriref, types=[SOFTWARE.BuildInstructions])

            # FIXME: these are Baserock-specific parameters... what to
            # do? Set them in Baserock prefix for Baserock build tools
            # to handle!
            #chunk_ref.set(BASEROCK.buildMode,
            #              rdflib.Literal(entry.get('build-mode', 'normal')))
            #chunk_ref.set(BASEROCK.prefix,
            #          rdflib.Literal(entry.get('prefix', '/usr')))

            # 

            for stratum_artifact in artifacts:
                for entry_dep in entry.get('build-depends', []):
                    build_dep_artifacts = self.artifacts_for_chunk(
                        rdflib.URIRef(stratum_artifact.identifier),
                        entry_dep)
                    for build_dep_artifact in build_dep_artifacts:
                        build_dep_uriref = self.ns.chunk_artifact(
                            rdflib.URIRef(stratum_artifact.identifier),
                            build_dep_artifact)
                        chunk_source.set(
                            SOFTWARE.BuildRequires, build_dep_uriref)

                # FIXME: need to honour the splitting rules here
                chunk_artifacts = self.artifacts_for_chunk(
                    stratum_artifact.identifier, chunk_name)

                for chunk_artifact in chunk_artifacts:
                    repo_uriref = self.ns.git_repository(entry['repo'])
                    repo = self.new_resource(
                        repo_uriref, types=[SOFTWARE.GitRepository])

                    commit_uriref = self.ns.git_object(repo_uriref, entry['ref'])
                    commit = self.new_resource(
                        commit_uriref,
                        types=[SOFTWARE.GitObject, SOFTWARE.Source])
                    repo.set(SOFTWARE.containsArtifact, commit)

                    # FIXME: unpetrify-ref: is it important to keep track of
                    # the named ref in this data-model? I think you should
                    # keep that as a note, it's up to the tooling...
                    if 'unpetrify-ref' in entry:
                        # This needs to be converted to a string as it may be
                        # parsed as a floating point number by PyYAML.
                        comment = 'unpetrify-ref:%s' % entry['unpetrify-ref']
                        commit.set(SOFTWARE.hasComment,
                                    rdflib.Literal(comment))

                    stratum_artifact.add(
                        SOFTWARE.containsArtifact, chunk_artifact)

    def process_system(self, contents):
        source_uriref = self.ns.system(contents['name'])
        entity = source = self.new_resource(
            source_uriref, types=[SOFTWARE.BuildInstructions])

        artifact_uriref = self.ns.system_artifact(contents['name'], 'rootfs')
        artifact = self.new_resource(
            artifact_uriref,
            types=[SOFTWARE.Group, SOFTWARE.ExecutableArtifact])

        source.set(SOFTWARE.producesArtifact, artifact)
        artifact.set(SOFTWARE.forArchitecture, rdflib.Literal(contents['arch']))

        for entry in contents.get('strata', []):
            stratum_artifacts = self.artifacts_for_stratum(
                entry['name'], include_list=entry.get('artifacts'))
            for stratum_artifact_uriref in stratum_artifacts:
                artifact.add(
                    SOFTWARE.containsArtifact, stratum_artifact_uriref)


def main():
    args = argument_parser().parse_args()

    # FIXME: validate against schemas if present!
    # and check VERSION and DEFAULTS!

    graph = BaserockDefinitionsImporter(args.output_location).load_all_morphologies(
        path=args.input_location)

    #sys.stdout.write(helpers.serialize_to_json_ld(graph).decode('utf8'))
    sys.stdout.write(helpers.serialize_to_rdfxml(graph).decode('utf8'))


try:
    main()
except RuntimeError as e:
    sys.stderr.write('%s\n' % e)
    sys.exit(1)
