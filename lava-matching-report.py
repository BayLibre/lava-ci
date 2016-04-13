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
# Usage ./lava-matching-report.py  --section baylibre --matching $(subst, /,-,$(TAG))

import os
import json
import argparse

from lib import utils
from lib import configuration

POWER_METRICS = ["vbus_max", "energy", "power_min",
                "power_max", "power_avg", "current_min", "current_max"]

## FIXME: config, temporary ?
ATTACH_FOLDER = "/var/www/images/kernel-ci/attachments/"
ATTACH_FILE = "data.csv"
MATCHING_BOOTS = "matching-boots.json"
MATCHING_TESTS = "matching-tests.json"

def main(args):
    config = configuration.get_config(args)
    url = utils.validate_input(config.get("username"),
                               config.get("token"), config.get("server"))
    connection = utils.connect(url)

    bundle_stream = None
    if config.get("stream"):
        bundle_stream = config.get("stream")

    bundles = connection.dashboard.bundles(bundle_stream)

    folder = os.getcwd() + '/results'
    utils.mkdir(folder)

    matching = None
    if args.has_key("matching"):
        matching = args['matching']
        print "Searching bundles named after '%s'..." % matching

    generate_matching_boots(config, connection, bundles, folder, matching)
    


def generate_matching_boots(config, connection, bundles, folder, matching):

    powerci_json = {}
    powerci_json['username'] = config.get("username")
    powerci_json['token'] = config.get("token")
    powerci_json['server'] = config.get("server")
    powerci_json['duration'] = 0

    total_bundles = len(bundles)

    for bundle in bundles:
        if bundle['associated_job'] == "NA":
            bundles.remove(bundle)
            continue

        if matching is not None:
            if matching not in bundle['content_filename']:
#                print "remove" + str(bundle['content_filename'])
                bundles.remove(bundle)
                continue

        json_bundle = connection.dashboard.get(bundle['content_sha1'])
        bundle_data = json.loads(json_bundle['content'])

        number = bundle["associated_job"]

        # A suitable job:
        # - has a uuid that matches a storage folder under
        # /var/www/images/kernel-ci/attachments/
        # - could upload a non-empty CSV file with the power measurements
        # - has power metrics is it's test_run metadata
        #
        found_suitable = False

        for test_results in bundle_data['test_runs']:
            if test_results['test_id'] == 'lava-command':
                uuid = test_results['analyzer_assigned_uuid'].split('-', 1)[0]
                attach_dir = os.path.join(ATTACH_FOLDER, uuid)
                try:
                    files = os.listdir(attach_dir)
                    for a_file in files:
                        if not ATTACH_FILE in str(a_file):
                            continue
                        fullpath = os.path.join(attach_dir, str(a_file))
                        stats = os.stat(fullpath)
                        if not stats.st_size:
                            print "Empty Data file %s, skipped" % fullpath
                            continue
                except:
                    print "Failed walking dir %s, skipped" % attach_dir
                    continue

                for test in test_results['test_results']:
                    if test['test_case_id'] in POWER_METRICS:
                        found_suitable = True

        if not found_suitable:
            bundles.remove(bundle)
            continue

        data = {}
        data['bundle'] = bundle['content_sha1']
        data['result'] = "PASS"
        powerci_json[number] = data

    utils.write_json(MATCHING_BOOTS, folder, powerci_json)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", help="configuration for the LAVA server")
    parser.add_argument("--section", default="default", help="section in the LAVA config file")
    parser.add_argument("--username", help="username for the LAVA server")
    parser.add_argument("--token", help="token for LAVA server api")
    parser.add_argument("--server", help="server url for LAVA server")
    parser.add_argument("--stream", help="bundle stream for LAVA server")
    parser.add_argument("--matching", help="a substring to look for in the job name")
    my_args = vars(parser.parse_args())
    main(my_args)
