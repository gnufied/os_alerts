#!/usr/bin/env python

import subprocess
import json
import datetime
import time
import re
import sys

class VolumeInfo(object):
    def __init__(self, pv_name, ebs_id, instance_id, device_name):
        self.pv_name = pv_name
        self.ebs_id = ebs_id
        self.instance_id = instance_id
        self.device_name = device_name

class AttachedVolume(object):
    def __init__(self, profile, region):
        self.profile = profile
       self.region = region
        self.pvc_regex = re.compile("^pvc")

    def run(self):
        for line in sys.stdin.readlines():
            if self.pvc_regex.match(line):
                line = line.strip()
                pv_array = line.split(":")
                pv_name = pv_array[0].strip()
                ebs_id = pv_array[1].strip()
                self.check_volume(ebs_id, pv_name)


    def check_volume(self, ebs_id, pv_name):
        try:
            output = subprocess.check_output(["aws", "ec2", "describe-volumes", "--volume-ids", ebs_id, "--profile", self.profile, "--region", self.region])
            ebs_data = json.loads(output)
            volume = ebs_data["Volumes"][0]
            state = volume["State"]
            if state == "in-use":
                attachment = volume["Attachments"][0]
                instance_id = attachment["InstanceId"]
                device_name = attachment["Device"]
                volume_info = VolumeInfo(pv_name, ebs_id, instance_id, device_name)
                if not self.check_for_mount(volume_info):
                    print "Detaching volume %s from node %s" % (ebs_id, volume_info.instance_id)
                    self.detach_volumes(ebs_id)
        except Exception, e:
            print "Volume not found"

    def detach_volumes(self, ebs_id):
        try:
            subprocess.check_output(["aws", "ec2", "detach-volume", "--volume-id", ebs_id, "--profile", self.profile, "--region", self.region])
        except Exception, e:
            print "Error while detaching volume %s" % (ebs_id)


    def check_for_mount(self, volume_info):
        try:
            # running command
            # ossh -o "StrictHostKeyChecking=no" -c "grep \/dev\/xvdbz /proc/mounts" i-foobar
            grep_command = "grep %s /proc/mounts" % (volume_info.ebs_id)
            exec_command = ["ossh", "-o", "StrictHostKeyChecking=no", "-c", grep_command, volume_info.instance_id]
            output = subprocess.check_output(exec_command)
            if volume_info.device_name in output:
                return True
            else:
                return False
        except Exception, e:
            return False






if __name__ == "__main__":
    a = AttachedVolume(sys.argv[1], sys.argv[2])
    a.run()
