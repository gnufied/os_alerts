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
    def __init__(self, profile):
        self.profile = profile
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
            output = subprocess.check_output(["aws", "ec2", "describe-volumes", "--volume-ids", ebs_id, "--profile", self.profile])
            ebs_data = json.loads(output)
            volume = ebs_data["Volumes"][0]
            state = volume["State"]
            if state == "in-use":
                attachment = volume["Attachments"][0]
                instance_id = attachment["InstanceId"]
                device_name = attachment["Device"]
                volume_info = VolumeInfo(pv_name, ebs_id, instance_id, device_name)
                self.check_for_mount(volume_info)
        except Exception, e:
            print "Volume not found"

    def check_for_mount(self, volume_info):
        try:
            # running command
            # ossh -o "StrictHostKeyChecking=no" -c "grep \/dev\/xvdbz /proc/mounts" i-foobar
            grep_command = "\"grep %s /proc/mounts\"" % (volume_info.ebs_id)
            exec_command = ["ossh", "-o", "StrictHostKeyChecking=no", "-c", grep_command, volume_info.instance_id]
            print exec_command
            output = subprocess.check_output(exec_command)
            if self.check_for_mount_point(output, volume_info):
                print "%s : %s : %s" % (volume_info.ebs_id, volume_info.instance_id, volume_info.device_name)
        except Exception, e:
            print "Error checking mount status for %s and host %s" % (volume_info.ebs_id, volume_info.instance_id)

    def check_for_mount_point(self, output, volume_info):
        return true



if __name__ == "__main__":
    a = AttachedVolume(sys.argv[1])
    a.run()
