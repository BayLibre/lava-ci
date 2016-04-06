#!/usr/bin/python
#
# Copyright (C) BayLibre SAS, 2016
# $Author: Marc Titinger <marc.titinger@baylibre.com>
#
# This script is intended to gather all suitable job results
# from the LAVA instance in order to post them using the PowerCI API.
# A suitable  job has a non empty bundles, and optionally contains
# the string passed with "--matching" in it's job name.
#
# Usage ./lava-all-jobs.py  --section baylibre

import os
import xmlrpclib
import json
import subprocess
import fnmatch
import time
import re
import argparse
import httplib

from lib import utils
from lib import configuration

# status = connection.scheduler.job_status(submitted_jobs[job])

def main(args):
    config = configuration.get_config(args)
    url = utils.validate_input(config.get("username"), config.get("token"), config.get("server"))
    connection = utils.connect(url)

    bundle_stream = None
    if config.get("stream"):
        bundle_stream = config.get("stream")

    jobs = connection.scheduler.all_jobs()

    bundles = connection.dashboard.bundles(bundle_stream)

    results_directory = os.getcwd() + '/results'
    utils.mkdir(results_directory)

    powerci_json = {}
    powerci_json['username'] = config.get("username")
    powerci_json['token'] = config.get("token")
    powerci_json['server']= config.get("server")
    powerci_json['duration']= config.get("0")

    for bundle in bundles:
	if bundle['associated_job'] == "NA": continue
	if args.has_key('matching'):
            if args['matching'] in bundle['content_filename']:
                print "found %s" % bundle['content_filename']
            else: continue

        number = bundle["associated_job"]
        data = {}
        data['bundle'] = bundle['content_sha1']
        data['result'] = "PASS"
        powerci_json[number] = data

    utils.write_json("all.json", results_directory, powerci_json)
  
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", help="configuration for the LAVA server")
    parser.add_argument("--section", default="default", help="section in the LAVA config file")
    parser.add_argument("--username", help="username for the LAVA server")
    parser.add_argument("--token", help="token for LAVA server api")
    parser.add_argument("--server", help="server url for LAVA server")
    parser.add_argument("--stream", help="bundle stream for LAVA server")
    parser.add_argument("--matching", help="a substring to look for in the job name")
    args = vars(parser.parse_args())
    main(args)
