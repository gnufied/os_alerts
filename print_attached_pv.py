#!/usr/bin/env python

import subprocess
import json
import datetime
import time
import re
import sys

class AttachedVolume(object):
    def __init__(self):
        self.pvc_regex = re.compile("^pvc")

    def run(self):
        for line in sys.stdin:
            if self.pvc_regex.match(line):
                pv_array = line.split(":")
                pv_name = pv_array[0].strip()
                ebs_id = pv_array[1].strip()
                self.check_volume(ebs_id, pv_name)


    def check_volume(self, ebs_id, pv_name):
        try:
            output = subprocess.check_output(["aws", "ec2", "describe-volumes", "--volume-ids", ebs_id, "--profile", "v3-paid-prod"])
            ebs_data = json.loads(output)
            volume = ebs_data["Volumes"][0]
            state = volume["State"]
            if state == "in-use":
                print "pv %s with volume %s is in use" % (pv_name, ebs_id)
        except Exception, e:
            print "Volume not found"



if __name__ == "__main__":
    a = AttachedVolume()
    a.run()
