#!/usr/bin/env python3
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


'''Parser for the GNOME Continuous input manifest format.'''


import rdflib

import argparse
import json
import os
import sys
import urllib

import helpers


DEFAULT_URL = 'https://git.gnome.org/browse/gnome-continuous/plain/manifest.json'

SOFTWARE = rdflib.namespace.Namespace(
    'http://www.baserock.org/software-integration-ontology#')


def argument_parser():
    parser = argparse.ArgumentParser(
        description="Parse a GNOME Continuous input manifest")
    parser.add_argument('input_location', type=str,
                        help="Location to read the manifest from")
    parser.add_argument('output_location', type=str,
                        help="Location of the resulting resources (base URI)")
    return parser


class GnomeContinuousImporter():
    def parse_manifest(self, manifest, base_uri):
        namespace = helpers.SoftwareNamespace(base_uri)
        graph = rdflib.Graph()

        graph.bind('software', SOFTWARE)

        # FIXME: write a json-schema for gnome-continuous; put it upstream

        # Keyed URIs are allowed in the 'src' field, with the keys defined
        # in the 'vcsconfig' dict.
        aliases = dict() # rdflib.namespace.NamespaceManager(graph)
        for key, value in manifest['vcsconfig'].items():
            alias_namespace = rdflib.namespace.Namespace(value)
            # We perhaps shouldn't convert the key to lower case, but anyone
            # relying on case sensitivity here must be crazy, and this means
            # we can urllib.parse.urlsplit() to parse the URLs (it converts
            # the 'scheme' field to lower case).
            #aliases.bind(key, value)
            aliases[key.lower()] = alias_namespace

        for component in manifest['components']:
            resource = self.resource_for_component(
                namespace, graph, component, aliases)

        return graph

    def parse_src_field(self, src_field, aliases):
        def process_source_type_specifier(src_field):
            # Remove the non-standard extension to the source URIs.
            if src_field.startswith('git:'):
                source_type = SOFTWARE.GitRepository
                src_field = src_field[4:]
            elif src_field.startswith('tarball:'):
                source_type = SOFTWARE.Tarball
                src_field = src_field[8:]
            else:
                source_type = None
            return source_type, src_field

        source_type, location = process_source_type_specifier(src_field)

        if source_type is None:
            # Looks like a keyed URL.

            parts = urllib.parse.urlsplit(src_field)

            namespace = aliases[parts.scheme]
            location = namespace[parts.path]
            source_type, location = \
                process_source_type_specifier(location)

        return source_type, location

    def resource_for_component(self, namespace, graph, component, aliases):
        source_type, source_location = self.parse_src_field(component['src'], aliases)

        # There's no 'name' field, so we guess one based on the 'src' field.
        source_name = os.path.basename(source_location)
        source = rdflib.resource.Resource(
            graph, namespace.source(source_name))

        source.set(rdflib.RDF.type, SOFTWARE.Source)
        source.set(rdflib.RDF.type, source_type)
        source.set(SOFTWARE.location, rdflib.Literal(source_location))

        return component


def main():
    args = argument_parser().parse_args()

    with open(args.input_location, 'r') as f:
        manifest = json.load(f)

    graph = GnomeContinuousImporter().parse_manifest(
        manifest, args.output_location)

    #sys.stdout.write(helpers.serialize_to_json_ld(graph).decode('utf8'))
    sys.stdout.write(helpers.serialize_to_rdfxml(graph).decode('utf8'))


main()
