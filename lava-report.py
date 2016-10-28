#!/usr/bin/python
# <variable> = required
# Usage ./lava-report.py <option> [json]
import os
import sys
import urlparse
import xmlrpclib
import json
import argparse
import time
import subprocess
import re
import urllib2
import requests

from lib import configuration
from lib import utils

from device_map import device_type_map as device_map
log2html = 'https://git.linaro.org/people/kevin.hilman/build-scripts.git/blob_plain/HEAD:/log2html.py'

################################################################################
def get_platform_name(arch,device_tree,device_type,test_plan):
    if (arch == 'arm' or arch =='arm64') and device_tree is None:
        platform_name = device_map[device_type][0] + ',legacy'
    else:
        if device_tree in ['vexpress-v2p-ca15_a7.dtb','fsl-ls2080a-simu.dtb']:
            platform_name = device_tree.split('.')[0]
        elif test_plan == 'boot-kvm' or test_plan == 'boot-kvm-uefi':
            if device_tree == 'sun7i-a20-cubietruck.dtb':
                    if device_type == 'dynamic-vm': 
                        device_type = 'cubieboard3-kvm-guest'
                    else:
                        device_type = 'cubieboard3-kvm-host'
                    platform_name = device_map[device_type][0]
            elif device_tree == 'apm-mustang.dtb':
                    if device_type == 'dynamic-vm':
                        if test_plan == 'boot-kvm-uefi': 
                            device_type = 'mustang-kvm-uefi-guest'
                        else:
                            device_type = 'mustang-kvm-guest'
                    else:
                        if test_plan == 'boot-kvm-uefi':
                            device_type = 'mustang-kvm-uefi-host'
                        else:
                            device_type = 'mustang-kvm-host'
                    platform_name = device_map[device_type][0]
            elif device_tree == 'juno.dtb':
                    if device_type == 'dynamic-vm':
                        if test_plan == 'boot-kvm-uefi':
                            device_type = 'juno-kvm-uefi-guest'
                        else:
                            device_type = 'juno-kvm-guest'
                    else:
                        if test_plan == 'boot-kvm-uefi':
                            device_type = 'juno-kvm-uefi-host'
                        else:
                            device_type = 'juno-kvm-host'
                    platform_name = device_map[device_type][0]
            else:
                print "Case not existing in original lava-report.py ?!"
                platform_name = device_map[device_type][0]
        elif test_plan == 'boot-nfs' or test_plan == 'boot-nfs-mp':
            platform_name = device_map[device_type][0] + '_rootfs:nfs'
        else:
            platform_name = device_map[device_type][0]

    return platform_name,device_type

################################################################################
def download_log2html(url):
    print 'Fetching latest log2html script'
    try:
        response = urllib2.urlopen(url, timeout=30)
    except IOError, e:
        print 'error fetching %s: %s' % (url, e)
        exit(1)
    script = response.read()
    utils.write_file(script, 'log2html.py', os.getcwd())


################################################################################
def parse_json(json):
    jobs = utils.load_json(json)
    url = utils.validate_input(jobs['username'], jobs['token'], jobs['server'])
    connection = utils.connect(url)
    duration = jobs['duration']
    # Remove unused data
    jobs.pop('duration')
    jobs.pop('username')
    jobs.pop('token')
    jobs.pop('server')
    return connection, jobs, duration


################################################################################
def push(method, url, data, headers):
    retry = True
    while retry:
        if method == 'POST':
            response = requests.post(url, data=data, headers=headers)
        elif method == 'PUT':
            response = requests.put(url, data=data, headers=headers)
        else:
            print "ERROR: unsupported method"
            exit(1)
        if response.status_code != 500:
            retry = False
            print "OK"
        else:
            time.sleep(10)
            print response.content


################################################################################
def get_job_detail(connection,job_id,job_elem):
    job_details = connection.scheduler.job_details(job_id)
    if job_details['requested_device_type_id']:
        device_type = job_details['requested_device_type_id']
        platform_name = device_map[device_type][0]
    if job_details['description']:
        job_name = job_details['description']
    result = job_elem['result']
    bundle = job_elem['bundle']

    return device_type,platform_name,job_name,result,bundle


################################################################################
def boot_report(config):
    result_name='results'
    if config.get('result'): result_name=config.get('result')
    results_directory = os.path.join(os.getcwd(),result_name)
    if not os.path.isdir(results_directory): utils.mkdir(results_directory)
    
    results = {}
    duration=0.0

    print 'treatment report of: '+config.get('boot')
    print "results_directory = %s" % results_directory
    connection, jobs, duration_instance =  parse_json(config.get("boot"))
    duration += float(duration_instance)

    # TODO: Fix this when multi-lab sync is working
    #download_log2html(log2html)
    dt_tests = False
    for job_id,job_elem in jobs.items():
        print 'Job ID: %s' % job_id
        # Init
        boot_meta = {}

        arch = None
        board_instance = None

        # this is the folder name (uuid) in /var/.../kernel-ci
        # where lava uploads attachments.
        #
        power_stats = []

        boot_retries = 0
        kernel_defconfig_full = None
        kernel_defconfig = None
        kernel_defconfig_base = None
        kernel_version = None
        device_tree = None
        kernel_endian = None
        kernel_tree = None
        kernel_addr = None
        initrd_addr = None
        dtb_addr = None
        dtb_append = None
        fastboot = None
        fastboot_cmd = None
        test_plan = None
        test_desc = None
        job_file = ''
        dt_test = None
        dt_test_result = None
        dt_tests_passed = None
        dt_tests_failed = None
        board_offline = False
        kernel_boot_time = None
        boot_failure_reason = None
        efi_rtc = False

        # Retrieve job details
        device_type,platform_name,job_name,result,bundle=get_job_detail(connection,job_id,job_elem)

        if bundle is None and device_type == 'dynamic-vm':
            host_job_id = job_id.replace('.1', '.0')
            bundle = jobs[host_job_id]['bundle']
            if bundle is None:
                print '%s bundle is empty, skipping...' % device_type
                continue
        # Retrieve the log file
        try:
            binary_job_file = connection.scheduler.job_output(job_id)
        except xmlrpclib.Fault:
            print 'Job output not found for %s' % device_type
            continue
        # Parse LAVA messages out of log
        raw_job_file = str(binary_job_file)
        for line in raw_job_file.splitlines():
            errors={'Infrastructure':True,'Bootloader':True,'Kernel':False,'Userspace':False}
            for error_type,offline_status in errors.items():
                if error_type+' Error:' in line:
                    print error_type+' Error detected'
                    index = line.find(error_type+' Error:')
                    boot_failure_reason = line[index:]
                    board_offline = offline_status

            if '<LAVA_DISPATCHER>' not in line:
                if len(line) != 0:
                    job_file += line + '\n'
            if '### dt-test ### end of selftest' in line:
                dt_tests = True
                regex = re.compile("(?P<test>\d+\*?)")
                dt_test_results = regex.findall(line)
                if len(dt_test_results) > 2:
                    dt_tests_passed = dt_test_results[2]
                    dt_tests_failed = dt_test_results[3]
                else:
                    dt_tests_passed = dt_test_results[0]
                    dt_tests_failed = dt_test_results[1]
                if int(dt_tests_failed) > 0:
                    dt_test_result = 'FAIL'
                else:
                    dt_test_result = 'PASS'
            if 'rtc-efi rtc-efi: setting system clock to' in line:
                if device_type == 'dynamic-vm':
                    efi_rtc = True
        # Retrieve bundle
        if bundle is not None:
            json_bundle = connection.dashboard.get(bundle)
            bundle_data = json.loads(json_bundle['content'])
            bundle_attributes = bundle_data['test_runs'][-1]['attributes']
            # Get the boot data from LAVA
            for test_results in bundle_data['test_runs']:
                # Check for the LAVA self boot test
                if test_results['test_id'] == 'lava':
                    for test in test_results['test_results']:
                        # TODO for compat :(
                        if test['test_case_id'] == 'kernel_boot_time':
                            kernel_boot_time = test['measurement']
                        if test['test_case_id'] == 'test_kernel_boot_time':
                            kernel_boot_time = test['measurement']
                # check for a PowerCI attachement UUID
                if test_results['test_id'] == 'lava-command':
                ## using this uuid on lava side to upload to the attachments folder
                #  we create a short uuid based on the first segment.
                # see lava-dispatcher/lava_dispatcher/actions/lava_command.py
                #
                    boot_meta['power_stats'] = test_results['analyzer_assigned_uuid'].split('-',1)[0]
                    power_test = {}
                    power_test['data'] = test_results['analyzer_assigned_uuid'].split('-',1)[0]
                    power_test['filename'] = "data.csv"
                    power_metrics= ["vbus_max", "energy", "power_min", \
                                "power_max", "power_avg", "current_min", "current_max"]
                    for test in test_results['test_results']:
                        if test['test_case_id'] in power_metrics:
                           ## TODO handle many attachments and power stats, but this requires a
                            # POWERCI API change
                            output = test['measurement']
                            power_test[test['test_case_id']] = test['measurement']
                    power_stats.append(power_test)
                    boot_meta['power_stats'] = power_stats
                    #print boot_meta['power_stats']


            if utils.in_bundle_attributes(bundle_attributes, 'kernel.defconfig'):
                print bundle_attributes['kernel.defconfig']
            if utils.in_bundle_attributes(bundle_attributes, 'target'):
                board_instance = bundle_attributes['target']
            if utils.in_bundle_attributes(bundle_attributes, 'kernel.defconfig'):
                kernel_defconfig = bundle_attributes['kernel.defconfig']
                defconfig_list = kernel_defconfig.split('-')
                arch = defconfig_list[0]
                # Remove arch
                defconfig_list.pop(0)
                kernel_defconfig_full = '-'.join(defconfig_list)
                kernel_defconfig_base = ''.join(kernel_defconfig_full.split('+')[:1])
                if kernel_defconfig_full == kernel_defconfig_base:
                    kernel_defconfig_full = None
            if utils.in_bundle_attributes(bundle_attributes, 'kernel.version'):
                kernel_version = bundle_attributes['kernel.version']
            if utils.in_bundle_attributes(bundle_attributes, 'device.tree'):
                device_tree = bundle_attributes['device.tree']
            if utils.in_bundle_attributes(bundle_attributes, 'kernel.endian'):
                kernel_endian = bundle_attributes['kernel.endian']
            if utils.in_bundle_attributes(bundle_attributes, 'platform.fastboot'):
                fastboot = bundle_attributes['platform.fastboot']
            if kernel_boot_time is None:
                if utils.in_bundle_attributes(bundle_attributes, 'kernel-boot-time'):
                    kernel_boot_time = bundle_attributes['kernel-boot-time']
            if utils.in_bundle_attributes(bundle_attributes, 'kernel.tree'):
                kernel_tree = bundle_attributes['kernel.tree']
            if utils.in_bundle_attributes(bundle_attributes, 'kernel-addr'):
                kernel_addr = bundle_attributes['kernel-addr']
            if utils.in_bundle_attributes(bundle_attributes, 'initrd-addr'):
                initrd_addr = bundle_attributes['initrd-addr']
            if utils.in_bundle_attributes(bundle_attributes, 'dtb-addr'):
                dtb_addr = bundle_attributes['dtb-addr']
            if utils.in_bundle_attributes(bundle_attributes, 'dtb-append'):
                dtb_append = bundle_attributes['dtb-append']
            if utils.in_bundle_attributes(bundle_attributes, 'boot_retries'):
                boot_retries = int(bundle_attributes['boot_retries'])
            if utils.in_bundle_attributes(bundle_attributes, 'test.plan'):
                test_plan = bundle_attributes['test.plan']
            if utils.in_bundle_attributes(bundle_attributes, 'test.desc'):
                test_desc = bundle_attributes['test.desc'].replace(" power test",'')

        # Check if we found efi-rtc
        if test_plan == 'boot-kvm-uefi' and not efi_rtc:
            if device_type == 'dynamic-vm':
                boot_failure_reason = 'Unable to read EFI rtc'
                result = 'FAIL'
        # Record the boot log and result
        # TODO: Will need to map device_types to dashboard device types
        if kernel_defconfig and device_type and result:

            platform_name,device_type=get_platform_name(arch,device_tree,device_type,test_plan)

            print 'Creating boot log for %s' % platform_name
            log = 'boot-%s.txt' % platform_name
            html = 'boot-%s.html' % platform_name
            if config.get("lab"):
                directory = os.path.join(results_directory, kernel_defconfig + '/' + config.get("lab"))
            else:
                directory = os.path.join(results_directory, kernel_defconfig)
            utils.ensure_dir(directory)
            utils.write_file(job_file, log, directory)
            if kernel_boot_time is None:
                kernel_boot_time = '0.0'
            if results.has_key(kernel_defconfig):
                results[kernel_defconfig].append({'device_type': platform_name, 'dt_test_result': dt_test_result, 'dt_tests_passed': dt_tests_passed, 'dt_tests_failed': dt_tests_failed, 'kernel_boot_time': kernel_boot_time, 'result': result})
            else:
                results[kernel_defconfig] = [{'device_type': platform_name, 'dt_test_result': dt_test_result, 'dt_tests_passed': dt_tests_passed, 'dt_tests_failed': dt_tests_failed, 'kernel_boot_time': kernel_boot_time, 'result': result}]
            # Create JSON format boot metadata
            print 'Creating JSON format boot metadata'
            if config.get("lab"):
                boot_meta['lab_name'] = config.get("lab")
            else:
                boot_meta['lab_name'] = None
            if board_instance:
                boot_meta['board_instance'] = board_instance
            boot_meta['retries'] = boot_retries
            boot_meta['boot_log'] = log
            boot_meta['boot_log_html'] = html
            # TODO: Fix this
            boot_meta['version'] = '1.0'
            boot_meta['arch'] = arch
            boot_meta['defconfig'] = kernel_defconfig_base
            if kernel_defconfig_full is not None:
                boot_meta['defconfig_full'] = kernel_defconfig_full
            if device_map[device_type][1]:
                boot_meta['mach'] = device_map[device_type][1]
            boot_meta['kernel'] = kernel_version
            boot_meta['job'] = kernel_tree
            boot_meta['board'] = platform_name

            # Add test plan to meta-data, to let the web feature
            # dedicated contents for power metrics for instance
            #
            boot_meta['test_plan'] = test_plan

            # Add searchable brief description or keyword
            boot_meta['test_desc'] = test_desc

            # Add lava bundle sha1 to link back from PowerCI to lava.
            boot_meta['lava_bundle'] = bundle
            print "lava_bundle= %s" % str(bundle)

            if board_offline and result == 'FAIL':
                boot_meta['boot_result'] = 'OFFLINE'
                #results[kernel_defconfig]['result'] = 'OFFLINE'
            else:
                boot_meta['boot_result'] = result
            if result == 'FAIL' or result == 'OFFLINE':
                if boot_failure_reason:
                    boot_meta['boot_result_description'] = boot_failure_reason
                else:
                    boot_meta['boot_result_description'] = 'Unknown Error: platform failed to boot'
            boot_meta['boot_time'] = kernel_boot_time
            # TODO: Fix this
            boot_meta['boot_warnings'] = None
            if device_tree:
                if arch == 'arm64':
                    boot_meta['dtb'] = os.path.join('dtbs',device_map[device_type][1],device_tree)
                else:
                    boot_meta['dtb'] = os.path.join('dtbs',device_tree)
            else:
                boot_meta['dtb'] = device_tree
            boot_meta['dtb_addr'] = dtb_addr
            boot_meta['dtb_append'] = dtb_append
            boot_meta['dt_test'] = dt_test
            boot_meta['endian'] = kernel_endian
            boot_meta['fastboot'] = fastboot
            # TODO: Fix this
            boot_meta['initrd'] = None
            boot_meta['initrd_addr'] = initrd_addr
            if arch == 'arm':
                boot_meta['kernel_image'] = 'zImage'
            elif arch == 'arm64':
                boot_meta['kernel_image'] = 'Image'
            else:
                boot_meta['kernel_image'] = 'bzImage'
            boot_meta['loadaddr'] = kernel_addr
            json_file = 'boot-%s.json' % platform_name
            utils.write_json(json_file, directory, boot_meta)
            print 'Creating html version of boot log for %s' % platform_name
            cmd = 'python log2html.py %s' % os.path.join(directory, log)
            subprocess.check_output(cmd, shell=True)
            if config.get("lab") and config.get("api") and config.get("token"):
                print 'Sending boot result to %s for %s' % (config.get("api"), platform_name)
                headers = {
                    'Authorization': config.get("token"),
                    'Content-Type': 'application/json'
                }
                api_url = urlparse.urljoin(config.get("api"), '/boot')
                push('POST', api_url, data=json.dumps(boot_meta), headers=headers)
                headers = {
                    'Authorization': config.get("token"),
                }
                print 'Uploading text version of boot log'
                with open(os.path.join(directory, log)) as lh:
                    data = lh.read()
                api_url = urlparse.urljoin(config.get("api"), '/upload/%s/%s/%s/%s/%s' % (kernel_tree,
                                                                                 kernel_version,
                                                                                 kernel_defconfig,
                                                                                 config.get("lab"),
                                                                                 log))
                push('PUT', api_url, data=data, headers=headers)
                print 'Uploading html version of boot log'
                with open(os.path.join(directory, html)) as lh:
                    data = lh.read()
                api_url = urlparse.urljoin(config.get("api"), '/upload/%s/%s/%s/%s/%s' % (kernel_tree,
                                                                                 kernel_version,
                                                                                 kernel_defconfig,
                                                                                 config.get("lab"),
                                                                                 html))
                push('PUT', api_url, data=data, headers=headers)

    report_directory=None
    if results and kernel_tree and kernel_version:
        print 'Creating boot summary for %s' % kernel_version
        boot = '%s-boot-report.txt' % kernel_version
        passed = 0
        failed = 0
        for defconfig, results_list in results.items():
            for result in results_list:
                if result['result'] == 'PASS': passed += 1
                else:                          failed += 1
        total = passed + failed
        if config.get("lab"):
            report_directory = os.path.join(results_directory, config.get("lab"))
            utils.mkdir(report_directory)
        else:
            report_directory = results_directory
        with open(os.path.join(report_directory, boot), 'a') as f:
            f.write('To: %s\n' % config.get("email"))
            f.write('From: bot@kernelci.org\n')
            f.write('Subject: %s boot: %s boots: %s passed, %s failed (%s)\n' % (kernel_tree,
                                                                                str(total),
                                                                                str(passed),
                                                                                str(failed),
                                                                                kernel_version))
            f.write('\n')
            f.write('Full Build Report: http://kernelci.org/build/%s/kernel/%s/\n' % (kernel_tree, kernel_version))
            f.write('Full Boot Report: http://kernelci.org/boot/all/job/%s/kernel/%s/\n' % (kernel_tree, kernel_version))
            f.write('\n')
            f.write('Total Duration: %.2f minutes\n' % (duration / 60))
            f.write('Tree/Branch: %s\n' % kernel_tree)
            f.write('Git Describe: %s\n' % kernel_version)
            first = True
            for defconfig, results_list in results.items():
                for result in results_list:
                    if result['result'] == 'OFFLINE':
                        if first:
                            f.write('\nBoards Offline:\n')
                            first = False
                        f.write('\n')
                        f.write(defconfig)
                        f.write('\n')
                        break
                for result in results_list:
                    if result['result'] == 'OFFLINE':
                        f.write('    %s   %ss   boot-test: %s\n\n' % (result['device_type'],
                                                                    result['kernel_boot_time'],
                                                                    result['result']))
            first = True
            for defconfig, results_list in results.items():
                for result in results_list:
                    if result['result'] == 'FAIL':
                        if first:
                            f.write('\nFailed Boot Tests:\n')
                            first = False
                        f.write('\n')
                        f.write(defconfig)
                        f.write('\n')
                        break
                for result in results_list:
                    if result['result'] == 'FAIL':
                        f.write('    %s   %ss   boot-test: %s\n' % (result['device_type'],
                                                                    result['kernel_boot_time'],
                                                                    result['result']))
                        if config.get("lab"):
                            f.write('    http://storage.kernelci.org/kernel-ci/%s/%s/%s/%s/boot-%s.html' % (kernel_tree,
                                                                                                            kernel_version,
                                                                                                            defconfig,
                                                                                                            config.get("lab"),
                                                                                                            result['device_type']))
                        else:
                            f.write('    http://storage.kernelci.org/kernel-ci/%s/%s/%s/boot-%s.html' % (kernel_tree,
                                                                                                         kernel_version,
                                                                                                         defconfig,
                                                                                                         result['device_type']))
                        f.write('\n')
            f.write('\n')
            f.write('Full Boot Report:\n')
            for defconfig, results_list in results.items():
                f.write('\n')
                f.write(defconfig)
                f.write('\n')
                for result in results_list:
                    f.write('    %s   %ss   boot-test: %s\n' % (result['device_type'], result['kernel_boot_time'], result['result']))

        # dt-self-test
        if dt_tests:
            print 'Creating device tree runtime self test summary for %s' % kernel_version
            dt_self_test = '%s-dt-runtime-self-test-report.txt' % kernel_version
            passed = 0
            failed = 0
            for defconfig, results_list in results.items():
                for result in results_list:
                    if result['dt_test_result'] == 'PASS':
                        passed += 1
                    elif result['dt_test_result'] == 'FAIL':
                        failed += 1
            total = passed + failed
            with open(os.path.join(report_directory, dt_self_test), 'a') as f:
                f.write('To: %s\n' % config.get("email"))
                f.write('From: bot@kernelci.org\n')
                f.write('Subject: %s dt-runtime-unit-tests: %s boards tested: %s passed, %s failed (%s)\n' % (kernel_tree,
                                                                                                           str(total),
                                                                                                           str(passed),
                                                                                                           str(failed),
                                                                                                           kernel_version))
                f.write('\n')
                f.write('Full Build Report: http://kernelci.org/build/%s/kernel/%s/\n' % (kernel_tree, kernel_version))
                f.write('Full Boot Report: http://kernelci.org/boot/all/job/%s/kernel/%s/\n' % (kernel_tree, kernel_version))
                f.write('Full Test Report: http://kernelci.org/test/%s/kernel/%s/\n' % (kernel_tree, kernel_version))
                f.write('\n')
                f.write('Tree/Branch: %s\n' % kernel_tree)
                f.write('Git Describe: %s\n' % kernel_version)
                first = True
                for defconfig, results_list in results.items():
                    for result in results_list:
                        if result['dt_test_result'] == 'FAIL':
                            if first:
                                f.write('\n')
                                f.write('Failed Device Tree Unit Tests:\n')
                                first = False
                            f.write('\n')
                            f.write(defconfig)
                            f.write('\n')
                            break
                    for result in results_list:
                        if result['dt_test_result'] == "FAIL":
                            f.write('    %s   passed: %s / failed: %s   dt-runtime-unit-tests: %s\n' % (result['device_type'],
                                                                                                    result['dt_tests_passed'],
                                                                                                    result['dt_tests_failed'],
                                                                                                    result['dt_test_result']))
                            if config.get("lab"):
                                f.write('    http://storage.kernelci.org/kernel-ci/%s/%s/%s/%s/boot-%s.html' % (kernel_tree,
                                                                                                        kernel_version,
                                                                                                        defconfig,
                                                                                                        config.get("lab"),
                                                                                                        result['device_type']))
                            else:
                                f.write('    http://storage.kernelci.org/kernel-ci/%s/%s/%s/boot-%s.html' % (kernel_tree,
                                                                                                         kernel_version,
                                                                                                         defconfig,
                                                                                                         result['device_type']))
                f.write('\n\n')
                f.write('Full Unit Test Report:\n')
                for defconfig, results_list in results.items():
                    first = True
                    for result in results_list:
                        if result['dt_test_result']:
                            if first:
                                f.write('\n')
                                f.write(defconfig)
                                f.write('\n')
                                first = False
                            f.write('    %s   passed: %s / failed: %s   dt-runtime-unit-tests: %s\n' % (result['device_type'],
                                                                                                    result['dt_tests_passed'],
                                                                                                    result['dt_tests_failed'],
                                                                                                    result['dt_test_result']))

    # sendmail
    if config.get("email"):
        print 'Sending e-mail summary to %s' % config.get("email")
        if report_directory and os.path.exists(report_directory):
            cmd = 'cat %s | sendmail -t' % os.path.join(report_directory, boot)
            subprocess.check_output(cmd, shell=True)
        if dt_tests:
            if os.path.exists(report_directory):
                cmd = 'cat %s | sendmail -t' % os.path.join(report_directory, dt_self_test)
                subprocess.check_output(cmd, shell=True)

################################################################################
def test_report(config):
    result_name='results'
    if config.get('result'): result_name=config.get('result')
    results_directory = os.path.join(os.getcwd(),result_name)
    if not os.path.isdir(results_directory): utils.mkdir(results_directory)

    results = {}
    duration=0.0

    for test in config.get('test'):
        print 'treatment report of: '+test
        print "results_directory = %s" % results_directory
        connection, jobs, duration_instance = parse_json(test)
        duration += float(duration_instance)
        for job_id,job_elem in jobs.items():
            print 'Job ID: %s' % job_id
            # Init
            test_meta = {}

            test_cases = []
            arch = None
            board_instance = None
            boot_retries = 0
            kernel_defconfig_full = None
            kernel_defconfig = None
            kernel_defconfig_base = None
            kernel_version = None
            device_tree = None
            kernel_endian = None
            kernel_tree = None
            kernel_addr = None
            initrd_addr = None
            dtb_addr = None
            dtb_append = None
            fastboot = None
            fastboot_cmd = None
            job_file = ''
            dt_test = None
            dt_test_result = None
            dt_tests_passed = None
            dt_tests_failed = None
            board_offline = False
            kernel_boot_time = None
            boot_failure_reason = None
            test_plan = None
            test_set = "default_set"
            test_suite = None
            test_type = None
            test_vcs_commit = None
            test_def_uri = None
            build_id = None
            efi_rtc = False

            device_type,platform_name,job_name,result,bundle = get_job_detail(connection,job_id,job_elem)

            # Retrieve bundle
            if bundle is not None:
                json_bundle = connection.dashboard.get(bundle)
                bundle_data = json.loads(json_bundle['content'])
                # Get the boot data from LAVA
                for test_results in bundle_data['test_runs']:
                    # Check for the LAVA test
                    if test_results['test_id'] != 'lava':
                        if 'testdef_metadata' in test_results:
                            if 'url' in test_results['testdef_metadata']:
                                test_def_uri = test_results['testdef_metadata']['url']
                            if 'version' in test_results['testdef_metadata']:
                                test_vcs_commit = test_results['testdef_metadata']['version']
                    # LAVA adds LAVA_SIGNAL_TESTCASE as another test_case_id, while
                    # the /TEST API expects something like test_set.test_case[],measurements[]
		    # A test_case_id w/o measurement will be a new test_case, a measurement
                    # will be attached to the measurements[] array of the current test_case.
                    #
                    # Now, this is a bit unprecise with scenarios like lava-command or
                    # lava-shell-test doing commands {A,B,C} and logging signals M0 M1 M2:
                    #  Mx are for instance the various power rails voltage measurements during
                    #  execution of A+B+C, but lava-test-shell/command show them as test_case_ids
                    #  each, so we might attach the Mx to the last command, i.e. C.
                    #  In pratice, this is no big deal IMO.
                    #

                        #FD 27/10/16: test_results['test_results'] contains:
                        # test11
                        # ...
                        # test1T
                        # measure11
                        # ...
                        # measure1M => All these measures are related to group of test1x
                        # test21
                        # ...
                        # test2T
                        # measure21
                        # ...
                        # measure2M => All these measures are related to goup of test2x
                        test_measures=[]
                        for test in test_results['test_results']:
                            if 'measurement' in test:
                                measure = {}
                                measure['name'] = test['test_case_id']
                                measure['measure'] = test['measurement']
                                if 'units' in test:
                                    measure['units'] = test['units']
                                measure['status'] = test['result'].upper()
                                test_measures.append(measure)
                            else:
                                # new group of test
                                # if there is a group of measurement link it to previous group of test
                                if len(test_measures)>0:
                                    test_case = {}
                                    test_case['version'] = '1.0'
                                    test_case['measurements'] = test_measures 
                                    #if 1 fail is found in group of measure, all measures are failed
                                    if 'FAIL' in [m['status'] for m in test_measures]:
                                        test_case['status']='FAIL'
                                    else:
                                        test_case['status']='PASS'
                                    test_cases.append(test_case)
                                    #reinit test_measures array
                                    test_measures=[]

                                test_case = {}
                                test_case['version'] = '1.0'
                                test_case['name'] = test['test_case_id']
                                test_case['status'] = test['result'].upper()
                                test_cases.append(test_case)

                        # last test is done and last measure may be done also
                        # if there is a group of measurement link it to previous group of test
                        if len(test_measures)>0:
                            test_case = {}
                            test_case['version'] = '1.0'
                            test_case['measurements'] = test_measures 
                            if 'FAIL' in [m['status'] for m in test_measures]:
                                test_case['status']='FAIL'
                            else:
                                test_case['status']='PASS'
                            test_cases.append(test_case)
                            test_measures=[]
                            

                        bundle_attributes = bundle_data['test_runs'][-1]['attributes']
                if utils.in_bundle_attributes(bundle_attributes, 'kernel.defconfig'):
                    print bundle_attributes['kernel.defconfig']
                if utils.in_bundle_attributes(bundle_attributes, 'target'):
                    board_instance = bundle_attributes['target']
                if utils.in_bundle_attributes(bundle_attributes, 'kernel.defconfig'):
                    kernel_defconfig = bundle_attributes['kernel.defconfig']
                    arch, kernel_defconfig_full = kernel_defconfig.split('-')
                    kernel_defconfig_base = ''.join(kernel_defconfig_full.split('+')[:1])
                    if kernel_defconfig_full == kernel_defconfig_base:
                        kernel_defconfig_full = None
                if utils.in_bundle_attributes(bundle_attributes, 'kernel.version'):
                    kernel_version = bundle_attributes['kernel.version']
                if utils.in_bundle_attributes(bundle_attributes, 'device.tree'):
                    device_tree = bundle_attributes['device.tree']
                if utils.in_bundle_attributes(bundle_attributes, 'kernel.endian'):
                    kernel_endian = bundle_attributes['kernel.endian']
                if utils.in_bundle_attributes(bundle_attributes, 'platform.fastboot'):
                    fastboot = bundle_attributes['platform.fastboot']
                if kernel_boot_time is None:
                    if utils.in_bundle_attributes(bundle_attributes, 'kernel-boot-time'):
                        kernel_boot_time = bundle_attributes['kernel-boot-time']
                if utils.in_bundle_attributes(bundle_attributes, 'kernel.tree'):
                    kernel_tree = bundle_attributes['kernel.tree']
                if utils.in_bundle_attributes(bundle_attributes, 'kernel-image'):
                    kernel_image = bundle_attributes['kernel-image']
                if utils.in_bundle_attributes(bundle_attributes, 'kernel-addr'):
                    kernel_addr = bundle_attributes['kernel-addr']
                if utils.in_bundle_attributes(bundle_attributes, 'initrd-addr'):
                    initrd_addr = bundle_attributes['initrd-addr']
                if utils.in_bundle_attributes(bundle_attributes, 'dtb-addr'):
                    dtb_addr = bundle_attributes['dtb-addr']
                if utils.in_bundle_attributes(bundle_attributes, 'dtb-append'):
                    dtb_append = bundle_attributes['dtb-append']
                if utils.in_bundle_attributes(bundle_attributes, 'boot_retries'):
                    boot_retries = int(bundle_attributes['boot_retries'])
                if utils.in_bundle_attributes(bundle_attributes, 'test.plan'):
                    test_plan = bundle_attributes['test.plan']
                if utils.in_bundle_attributes(bundle_attributes, 'test.set'):
                    test_set = bundle_attributes['test.set']
                if utils.in_bundle_attributes(bundle_attributes, 'test.suite'):
                    test_suite = bundle_attributes['test.suite']
                if utils.in_bundle_attributes(bundle_attributes, 'test.type'):
                    test_type = bundle_attributes['test.type']
                if utils.in_bundle_attributes(bundle_attributes, 'test.desc'):
                    test_desc = bundle_attributes['test.desc'].replace(" power test",'')
                    test_suite = re.sub("[ /]", '-', test_desc)
                    print "test_suite = %s (from test.desc)" % test_suite

            # Check if we found efi-rtc
            if test_plan == 'boot-kvm-uefi' and not efi_rtc:
                if device_type == 'dynamic-vm':
                    boot_failure_reason = 'Unable to read EFI rtc'
                    result = 'FAIL'
            # Record the boot log and result
            # TODO: Will need to map device_types to dashboard device types
            if kernel_defconfig and device_type and result:

                platform_name,device_type=get_platform_name(arch,device_tree,device_type,test_plan)

                print 'Creating test log for %s' % platform_name
                log = '%s-%s.txt' % (test_plan, platform_name)
                html = '%s-%s.html' % (test_plan, platform_name)
                if config.get("lab"):
                    directory = os.path.join(results_directory, kernel_defconfig + '/' + config.get("lab"))
                else:
                    directory = os.path.join(results_directory, kernel_defconfig)
                utils.ensure_dir(directory)
                utils.write_file(job_file, log, directory)
                if results.has_key(kernel_defconfig):
                    results[kernel_defconfig].append({'device_type': platform_name, 'test_plan': test_plan, 'test_cases': test_cases, 'result': result})
                else:
                    results[kernel_defconfig] = [{'device_type': platform_name, 'test_plan': test_plan, 'test_cases': test_cases, 'result': result}]

                # Create JSON format boot metadata
                print 'Creating JSON format test metadata'
                test_meta['version'] = '1.0'
                test_meta['name'] = test_suite
                if config.get('lab'):
                    test_meta['lab_name'] = config.get('lab')
                else:
                    test_meta['lab_name'] = None
                test_meta['arch'] = arch
                test_meta['defconfig'] = kernel_defconfig_base
                if kernel_defconfig_full is not None:
                    test_meta['defconfig_full'] = kernel_defconfig_full
                #if device_map[device_type][1]:
                    #test_meta['mach'] = device_map[device_type][1]
                test_meta['kernel'] = kernel_version
                test_meta['job'] = kernel_tree
                # Need to fetch the internal build id
                if config.get('lab') and config.get('api') and config.get('token'):
                    headers = {
                        'Authorization': config.get('token'),
                        'Content-Type': 'application/json'
                    }
                    query = '?kernel=%s' % test_meta['kernel']
                    query += '&arch=%s' % test_meta['arch']
                    query += '&job=%s' % test_meta['job']
                    query += '&limit=1'
                    query += '&defconfig=%s' % test_meta['defconfig']
                    if kernel_defconfig_full is not None:
                        query += '&defconfig_full=%s' % test_meta['defconfig_full']
                    else:
                        query += '&defconfig_full=%s' % test_meta['defconfig']

                    api_url = urlparse.urljoin(config.get('api'), '/build'+query)
                    response = requests.get(api_url, headers=headers)
                    data = json.loads(response.content)
                    if len(data['result']) != 0:
                        build_id = data['result'][0]['_id']['$oid']
                        print 'Retrieved build id: %s for %s' % (build_id, data['result'][0]['defconfig'])
                    else:
                        build_id = "abcde123456"

                test_meta['board'] = platform_name
                test_meta['build_id'] = build_id
                test_meta['test_set'] = [{
                    'name': test_set,
                    'version': '1.0',
                    'definition_uri': test_def_uri,
                    'vcs_commit': test_vcs_commit,
                    'test_case': test_cases
                }]
                json_file = '%s-%s.json' % (test_suite, platform_name)
                utils.write_json(json_file, directory, test_meta)
                if config.get('lab') and config.get('api') and config.get('token'):
                    print 'Sending test result to %s for %s' % (config.get('api'), platform_name)
                    headers = {
                        'Authorization': config.get('token'),
                        'Content-Type': 'application/json'
                    }
                    api_url = urlparse.urljoin(config.get('api'), '/test/suite')
                    response = requests.post(api_url, data=json.dumps(test_meta), headers=headers)

                    # DELME POWERCI
                    #print json.dumps(test_meta)

                    if response.status_code == 404:
                        print "ERROR: page not found"
                        exit(1)
                    if response.status_code == 403:
                        print "ERROR: access forbidden"
                        exit(1)
                    if response.status_code == 500:
                        print "ERROR: internal database error"
                        exit(1)
                    if response.status_code == (202 or 201 or 200):
                        print "OK"
                        print response.content

    if results and kernel_tree and kernel_version:
        print 'Creating test summary for %s' % kernel_version
        boot = '%s-test-report.txt' % kernel_version
        passed = 0
        failed = 0
        test_plan = None
        for defconfig, results_list in results.items():
            for result in results_list:
                test_plan = result['test_plan']
                if result['result'] == 'PASS':
                    passed += 1
                else:
                    failed += 1
        total = passed + failed
        if config.get("lab"):
            report_directory = os.path.join(results_directory, config.get("lab"))
            utils.mkdir(report_directory)
        else:
            report_directory = results_directory
        with open(os.path.join(report_directory, boot), 'a') as f:
            f.write('To: %s\n' % config.get("email"))
            f.write('From: bot@kernelci.org\n')
            f.write('Subject: %s %s: %s total, %s passed, %s failed (%s)\n' % (kernel_tree,
                                                                               test_plan,
                                                                               str(total),
                                                                               str(passed),
                                                                               str(failed),
                                                                               kernel_version))
            f.write('\n')
            f.write('Full Build Report: http://kernelci.org/build/%s/kernel/%s/\n' % (kernel_tree, kernel_version))
            f.write('Full Boot Report: http://kernelci.org/boot/all/job/%s/kernel/%s/\n' % (kernel_tree, kernel_version))
            f.write('Full Test Report: http://kernelci.org/test/%s/kernel/%s/\n' % (kernel_tree, kernel_version))
            f.write('\n')
            f.write('Total Duration: %.2f minutes\n' % (duration / 60.0))
            f.write('Tree/Branch: %s\n' % kernel_tree)
            f.write('Git Describe: %s\n' % kernel_version)
            first = True
            for defconfig, results_list in results.items():
                for result in results_list:
                    if result['result'] == 'OFFLINE':
                        if first:
                            f.write('\n')
                            f.write('Boards Offline:\n')
                            first = False
                        f.write('\n')
                        f.write(defconfig)
                        f.write('\n')
                        break
                for result in results_list:
                    if result['result'] == 'OFFLINE':
                        f.write('    %s   %s: %s\n' % (result['device_type'],
                                                       result['test_plan'],
                                                       result['result']))
                        f.write('\n')
            first = True
            for defconfig, results_list in results.items():
                for result in results_list:
                    if result['result'] == 'FAIL':
                        if first:
                            f.write('\n')
                            f.write('Failed Test Execution:\n')
                            first = False
                        f.write('\n')
                        f.write(defconfig)
                        f.write('\n')
                        break
                for result in results_list:
                    if result['result'] == 'FAIL':
                        f.write('    %s   %s: %s\n' % (result['device_type'],
                                                       result['test_plan'],
                                                       result['result']))
                        if config.get("lab"):
                            f.write('    http://storage.kernelci.org/kernel-ci/%s/%s/%s/%s/%s-%s.html' % (kernel_tree,
                                                                                                          kernel_version,
                                                                                                          defconfig,
                                                                                                          config.get("lab"),
                                                                                                          result['test_plan'],
                                                                                                          result['device_type']))
                        else:
                            f.write('    http://storage.kernelci.org/kernel-ci/%s/%s/%s/%s-%s.html' % (kernel_tree,
                                                                                                       kernel_version,
                                                                                                       defconfig,
                                                                                                       result['test_plan'],
                                                                                                       result['device_type']))
                        f.write('\n')
            f.write('\n')
            f.write('Full Test Report:\n')
            for defconfig, results_list in results.items():
                f.write('\n')
                f.write(defconfig)
                f.write('\n')
                for result in results_list:
                    f.write('    %s   %s: %s\n' % (result['device_type'], result['test_plan'], result['result']))
                    for test_case in result['test_cases']:
                        if 'measurements' in test_case:
                            f.write('         measurements:\n')
                            for measure in test_case['measurements']:
                                f.write('             %s: %s %s\n' % (measure['name'], measure['measure'], measure['units']))
                        else:
                            f.write('         %s: %s\n' % (test_case['name'], test_case['status']))
                    f.write('\n')
    # sendmail
    if config.get("email"):
        print 'Sending e-mail summary to %s' % config.get("email")
        if os.path.exists(report_directory):
            cmd = 'cat %s | sendmail -t' % os.path.join(report_directory, boot)
            subprocess.check_output(cmd, shell=True)

################################################################################
def main(args):
    config = configuration.get_config(args)
    for test_type in ["boot","test"]:
        type_report=getattr(sys.modules[__name__],test_type+'_report')
        if config.get(test_type):
            type_report(config)
    exit(0)

################################################################################
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", help="configuration for the LAVA server")
    parser.add_argument("--section", default="default", help="section in the LAVA config file")
    parser.add_argument("--result", help="Result name (default=results)")
    parser.add_argument("--boot", help="creates a kernel-ci boot report from a given json file")
    parser.add_argument("--test", nargs='+', help="creates a kernel-ci test report from a given json file")
    parser.add_argument("--lab", help="lab id")
    parser.add_argument("--api", help="api url")
    parser.add_argument("--token", help="authentication token")
    parser.add_argument("--email", help="email address to send report to")
    args = vars(parser.parse_args())
    main(args)
