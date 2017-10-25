#!/usr/bin/env python

import subprocess
import json
import datetime
import time
import re
import sys

class Volume(object):
    def __init__(self, ebs_id, device_path, hostname):
        self.ebs_id = ebs_id
        self.device_path = device_path
        self.hostname = hostname



class UmountVolume(object):
    def __init__(self):
        self.job_name = "HelloWorld"
        self.host_regexp = re.compile("^pro-us-east-1-node-compute-*")
        self.device_regexp = re.compile("^\/dev*")

    def run(self):
        current_host = ""
        for line in sys.stdin:
            line = line.strip()
            if self.host_regexp.match(line):
                t = line.split("|")[0].strip()
                current_host = t
            elif self.device_regexp.match(line):
                device_array = line.split(" ")
                device_string = device_array[1]
                volume_id = device_string.split("/")[-1]
                volume = Volume(volume_id, device_string, current_host)
                if self.check_ebs_status(volume_id):
                    self.print_volume(volume)

    def print_volume(self, volume):
        print "Volume %s on path %s on host %s" % (volume.ebs_id, volume.device_path, volume.hostname)

    def check_ebs_status(self, ebs_id):
        try:
            output = subprocess.check_output(["aws", "ec2", "describe-volumes", "--volume-ids", ebs_id, "--profile", "v3-paid-prod"])
            ebs_data = json.loads(output)
            volume = ebs_data["Volumes"][0]
            state = volume["State"]
            if state == "in-use":
                return False
            else:
                return True
        except Exception, e:
            return True


if __name__ == "__main__":
    a = UmountVolume()
    a.run()
