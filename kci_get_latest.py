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
# @param job kernel job to check
# @param defconfig_full config type specific part of kernel to check
# @param limit (default=1) 
#
# @return tag found
###############################################################################
def get_latest_tags(config, kernel=None, defconfig_full="allmodconfig", limit=1):
    """Return the list of latest kernels tags."""

    headers = {
            'Authorization': config.get('token')
        }

    query = "?sort=created_on&sort_order=-1"

    if kernel is not None:
        query = '&kernel=%s' % kernel
    if config.get('last') is None:
        query += '&limit=%s' % limit
        if config.get('job') is not None:
            query += '&job=%s' % config.get('job')
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
            if config.get('job') is None:
                tags.append(tag)
            elif config.get('job') in tag:   
                tags.append(tag)
        if config.get('last') is not None and tag==config.get('last'):
            break

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

    tags = get_latest_tags(config, None )

    return tags


###############################################################################
## @brief api access from another python script
#
# @param api api adress to check
# @param token token to access api
# @param config (default=None) config arguments
# @param section (default=None)
# @param job (default=None) 
#
# @return tag found or error code = 1
###############################################################################
def kci_get_latest(api,token,config=None,section=None,job=None,last=None):
    args = {'api':api,'token':token,'config':config,'section':section,'job':job,'last':last}
    
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
    parser.add_argument('-c','--config',  dest='config',  help="Configuration for the LAVA server")
    parser.add_argument('-s','--section', dest='section', help="Section in .lavarc")
    parser.add_argument('-j','--job',     dest='job',     help="Job to check (next, mainline,etc...")
    parser.add_argument('-l','--last',    dest='last',    help="returns tags from this tag")
    required = parser.add_argument_group('MANDATORY argument')
    required.add_argument('-a','--api',   dest='api',   required=True, help="API url")
    required.add_argument('-t','--token', dest='token', required=True, help="Authentication token")
    args = vars(parser.parse_args(args))

    try:
        res=run(args)
        if len(res)==1: 
            print res[0]
        else:
            for r in res:
                print r
    except Exception, err:
        print "### ERROR ###", str(err)
        sys.exit(1)

    return 0

###############################################################################
###############################################################################
if __name__ == '__main__':
    main(sys.argv[1:])
