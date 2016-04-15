#!/usr/bin/python
"""Return the list of latest kernels tags."""

import urlparse
import json
import argparse
import requests

from lib import configuration

def get_latest_tags(config, kernel, job, defconfig_full, limit=1):

    """Return the list of latest kernels tags."""

    if config.get('token'):
        headers = {
            'Authorization': config.get('token')
        }
    else:
        print "No token found in config, bailing out."
        exit(1)

    if config.get('api') is None:
        print "No api found in config, bailing out."
        exit(1)

    query = "?sort=created_on&sort_order=-1"

    if kernel is not None:
        query = '?kernel=%s' % kernel
    if job is not None:
        query += '&job=%s' % job

    query += '&limit=%s' % limit
    query += '&defconfig_full=%s' % defconfig_full
    api_url = urlparse.urljoin(config.get('api'), '/build' + query)

    response = requests.get(api_url, headers=headers)
    data = json.loads(response.content)

    if response.status_code == 404:
        print "ERROR: page not found"
        exit(1)
    if response.status_code == 403:
        print "ERROR: access forbidden"
        exit(1)
    if response.status_code == 500:
        print "ERROR: internal database error"
        exit(1)

    tags = []
    for result in data['result']:
        tag = result['kernel']
        if tag not in tags:
            tags.append(tag)

    return tags


def main(args):

    """Query the list of latest kernels tags."""

    config = configuration.get_config(args)

    print get_latest_tags(config, None, "next", "allmodconfig", 16)

    exit(0)

if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument("--config", help="configuration for the LAVA server")
    PARSER.add_argument("--section", help="section in .lavarc")
    PARSER.add_argument("--api", help="api url")
    PARSER.add_argument("--token", help="authentication token")
    ARGS = vars(PARSER.parse_args())
    main(ARGS)
