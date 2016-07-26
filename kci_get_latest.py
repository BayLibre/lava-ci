#!/usr/bin/python
###############################################################################
## @package kci_get_latest
# @brief Get the list of latests kernel tags found in kernelci.org
#


"""Return the list of latest kernels tags."""
import sys,os

import urlparse
import json
import argparse
import requests

from lib import configuration

###############################################################################
## @brief get the latest tags from api (kernelci.org)
#
# @param config input configuration elements
# @param kernel specific kernel to check
# @param job kernel branch to check
# @param defconfig_full config type specific part of kernel to check
# @param limit (default=1) 
#
# @return tag found
###############################################################################
def get_latest_tags(config, kernel, job, defconfig_full, limit=1):
    """Return the list of latest kernels tags."""

    headers = {
            'Authorization': config.get('token')
        }

    query = "?sort=created_on&sort_order=-1"

    if kernel is not None:
        query = '&kernel=%s' % kernel
    if job is not None:
        query += '&job=%s' % job

    query += '&limit=%s' % limit
    query += '&defconfig_full=%s' % defconfig_full
    api_url = urlparse.urljoin(config.get('api'), '/build' + query)

    response = requests.get(api_url, headers=headers)
    data = json.loads(response.content)

    if response.status_code >= 400:
        print data
        exit(1)

    tags = []
    for result in data['result']:
        tag = os.path.join(result['job'],result['kernel'])

        if tag not in tags:
            tags.append(tag)

    return tags

###############################################################################
## @brief global access to execute the script wherever it come from
#
# @param args (dict) input arguments
#
# @return tag found
###############################################################################
def run(args):
    config = configuration.get_config(args)
    if config.get('token') is None: 
        raise ValueError("No token found in config")
    if config.get('api') is None: 
        raise ValueError("No api found in config")

    tags = get_latest_tags(config, None, config.get('branch'), "allmodconfig")

    return tags


###############################################################################
## @brief api access from another python script
#
# @param api api adress to check
# @param token token to access api
# @param config (default=None) config arguments
# @param section (default=None)
# @param branch (default=None) 
#
# @return tag found or error code = 1
###############################################################################
def kci_get_latest(api,token,config=None,section=None,branch=None):
    args = {'api':api,'token':token,'config':config,'section':section,'branch':branch}
    
    try:
        return run(args)
    except Exception, err:
        print "### ERROR ###", str(err)
        return 1
    

###############################################################################
## @brief main called via command lines
#
# @param args input command line
#
# @return None
###############################################################################
def main(args):

    parser = argparse.ArgumentParser(description='Get latest kernel build from kernelci.org')
    parser.add_argument('-c','--config',  dest='config', help="Configuration for the LAVA server")
    parser.add_argument('-s','--section', dest='section',help="Section in .lavarc")
    parser.add_argument('-b','--branch',  dest='branch', help="Branch to check (next, mainline,etc...")
    required = parser.add_argument_group('MANDATORY argument')
    required.add_argument('-a','--api',     dest='api',   required=True, help="API url")
    required.add_argument('-t','--token',   dest='token', required=True, help="Authentication token")
    args = vars(parser.parse_args())

    try:
        print run(args)[0]
    except Exception, err:
        print "### ERROR ###", str(err)
        sys.exit(1)

###############################################################################
###############################################################################
if __name__ == '__main__':
    main(sys.argv[1:])
