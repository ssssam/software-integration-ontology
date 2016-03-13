#!/usr/bin/env python3

import defusedxml.minidom  # 'defusedxml' on PyPI
import pyld.jsonld         # 'pyld' on PyPI
import requests            # 'requests' on PyPI
import requests_cache      # 'requests-cache' on PyPI
import yaml                # 'pyyaml' on PyPI

import json
import os
import sys
import urllib.parse


requests_cache.install_cache()


def ohloh_project(project_name, call_ohloh=None):
    '''Gets data from Ohloh for a specific project.

    Returns an xml.dom.Node instance for the <project> element tree.

    '''
    xml = call_ohloh('projects/%s.xml' % project_name)

    response = xml.getElementsByTagName('response')[0]
    result = response.getElementsByTagName('result')[0]
    project = result.getElementsByTagName('project')[0]

    return project


def process_project(project, call_ohloh=None):
    if 'ohloh' in project:
        ohloh_data = ohloh_project(project['ohloh'], call_ohloh=call_ohloh)

        total_commit_count = int(ohloh_data.getElementsByTagName(
            'total_commit_count')[0].firstChild.data)
        total_code_lines = int(ohloh_data.getElementsByTagName(
            'total_code_lines')[0].firstChild.data)
        total_contributor_count = int(ohloh_data.getElementsByTagName(
            'total_contributor_count')[0].firstChild.data)

        project['total_commit_count'] = total_commit_count
        project['total_code_lines'] = total_code_lines
        project['total_contributor_count'] = total_contributor_count

    if 'children' in project:
        for child in project['children']:
            process_project(child, call_ohloh)

    def propagate_property(name, project):
        '''Calculate a property from children's values, if needed.

        This doesn't do any 'deduplication', of course, so if a project
        is made up of 4 component projects all of which are developed by
        the same folk, those folk will be counted 4 times.

        '''
        if name not in project:
            if 'children' in project:
                value = sum(
                    child[name] for child in project['children'])
                project[name] = value

    propagate_property('total_commit_count', project)
    propagate_property('total_code_lines', project)
    propagate_property('total_contributor_count', project)


def main():
    if not os.path.exists('ohloh-apikey'):
        raise RuntimeError(
            "Please create a file in the current working directory named "
            "'ohloh-apikey'. This file needs to contain a valid API key for "
            "the Black Duck OpenHub website. You can register an application "
            "for an API key here: "
            "<https://www.openhub.net/accounts/me/api_keys/new>")

    with open('ohloh-apikey') as f:
        ohloh_apikey = f.read().strip()

    def call_ohloh(url):
        ohloh_base = 'https://www.openhub.net/'
        response = requests.get(
            ohloh_base + url,
            params={'api_key': ohloh_apikey})
        response.raise_for_status()
        return defusedxml.minidom.parseString(response.text)

    data = yaml.load(sys.stdin)

    for project in data['@graph']:
        process_project(project, call_ohloh=call_ohloh)

    json.dump(data, sys.stdout, indent=4)


main()
