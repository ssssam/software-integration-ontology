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

        project['total_commit_count'] = total_commit_count

    if 'children' in project:
        for child in project['children']:
            process_project(child, call_ohloh)

        if 'total_commit_count' not in project:
            child_commit_count = sum(
                child['total_commit_count'] for child in project['children'])
            project['total_commit_count'] = child_commit_count


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

    json.dump(data, sys.stdout)


main()
